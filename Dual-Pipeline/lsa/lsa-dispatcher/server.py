"""
LSA Dispatcher
Local, system-instruction-only dispatch to the image model.
Every run is logged in full: SI file and its hash, prompt, settings, seed,
returned text, thought text (if requested), image, model version, timing.
Each batch gets an auto-generated contact sheet with selects and error tags.

Run:  conda activate depth_env
      python server.py
Open: http://127.0.0.1:5057
"""
import base64
import datetime as dt
import hashlib
import json
import os
import re
import threading
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_from_directory
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

# One shared SI library for every series (default: lsa\si, beside this folder).
SI_DIR = (ROOT / CONFIG.get("si_dir", "../si")).resolve()
RUNS_DIR = ROOT / "runs"
STATIC_DIR = ROOT / "static"
if not SI_DIR.is_dir():
    raise SystemExit(f"SI library not found: {SI_DIR}. Create it or fix si_dir in config.json.")
RUNS_DIR.mkdir(exist_ok=True)

# Find the nearest .env walking up from this folder, so the existing
# project-level .env is used without copying keys around.
for folder in [ROOT, *ROOT.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env")
        ENV_PATH = folder / ".env"
        break
else:
    ENV_PATH = None

API_KEY = next((os.getenv(n) for n in CONFIG["api_key_env_names"] if os.getenv(n)), None)
CLIENT = genai.Client(api_key=API_KEY) if API_KEY else None

ERROR_TAGS = CONFIG["error_tags"]
JOBS = {}          # batch_id -> {"state": ..., "done": n, "total": n}
LOCK = threading.Lock()
LOG_LOCK = threading.Lock()

app = Flask(__name__, static_folder=None)


# ---------------------------------------------------------------- helpers

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return s[:n] or "run"


def batch_dir(batch_id: str) -> Path:
    p = (RUNS_DIR / batch_id).resolve()
    if RUNS_DIR.resolve() not in p.parents:
        abort(400)
    return p


def read_batch(batch_id: str) -> dict:
    f = batch_dir(batch_id) / "batch.json"
    if not f.exists():
        abort(404)
    return json.loads(f.read_text(encoding="utf-8"))


def write_batch(batch_id: str, data: dict) -> None:
    f = batch_dir(batch_id) / "batch.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def append_global_log(record: dict) -> None:
    with LOG_LOCK:
        with open(RUNS_DIR / "log.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_config(si_text: str, s: dict, seed):
    kwargs = dict(
        system_instruction=si_text,
        temperature=s["temperature"],
        top_p=s["top_p"],
        response_modalities=["TEXT", "IMAGE"],
    )
    if seed is not None:
        kwargs["seed"] = seed
    img = {}
    if s.get("aspect_ratio"):
        img["aspect_ratio"] = s["aspect_ratio"]
    if s.get("image_size"):
        img["image_size"] = s["image_size"]
    if img:
        kwargs["image_config"] = types.ImageConfig(**img)
    if s.get("thinking_level") or s.get("include_thoughts"):
        tc = {}
        if s.get("thinking_level"):
            tc["thinking_level"] = s["thinking_level"].upper()
        if s.get("include_thoughts"):
            tc["include_thoughts"] = True
        kwargs["thinking_config"] = types.ThinkingConfig(**tc)
    return types.GenerateContentConfig(**kwargs)


def dump(obj):
    try:
        return obj.model_dump(mode="json", exclude_none=True)
    except Exception:
        return str(obj) if obj is not None else None


# ---------------------------------------------------------------- contact sheet

def load_font(size: int):
    for name in ("arialn.ttf", "arial.ttf", "DejaVuSansCondensed.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_contact_sheet(batch_id: str) -> None:
    data = read_batch(batch_id)
    runs = data["runs"]
    if not runs:
        return
    thumb_w = 420
    cols = 4 if len(runs) > 6 else min(3, len(runs))
    pad, label_h, rebate = 28, 64, 14
    font = load_font(18)
    small = load_font(15)
    red = (196, 44, 32)

    thumbs = []
    for r in runs:
        img = None
        if r.get("image_file"):
            try:
                img = Image.open(batch_dir(batch_id) / r["image_file"]).convert("RGB")
            except Exception:
                img = None
        if img is None:
            img = Image.new("RGB", (thumb_w, int(thumb_w * 0.66)), (40, 40, 42))
            ImageDraw.Draw(img).text((16, 16), "no image" if not r.get("error") else "error", fill=(200, 200, 200), font=font)
        ratio = thumb_w / img.width
        thumbs.append(img.resize((thumb_w, int(img.height * ratio))))

    cell_h = max(t.height for t in thumbs) + 2 * rebate + label_h
    cell_w = thumb_w + 2 * rebate
    rows = (len(thumbs) + cols - 1) // cols
    header = 70
    W = cols * cell_w + (cols + 1) * pad
    H = header + rows * cell_h + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), (214, 216, 212))
    d = ImageDraw.Draw(sheet)
    meta = data["meta"]
    d.text((pad, 18), f"{batch_id}   {meta['si_file']}  sha {meta['si_sha256'][:12]}", fill=(28, 29, 31), font=font)
    d.text((pad, 42), f"{meta['model']}  temp {meta['settings']['temperature']}  top-p {meta['settings']['top_p']}  "
                      f"thinking {meta['settings'].get('thinking_level') or 'default'}", fill=(70, 72, 76), font=small)

    for i, (r, t) in enumerate(zip(runs, thumbs)):
        cx = pad + (i % cols) * (cell_w + pad)
        cy = header + pad + (i // cols) * (cell_h + pad)
        d.rectangle([cx, cy, cx + cell_w, cy + t.height + 2 * rebate], fill=(22, 22, 24))
        sheet.paste(t, (cx + rebate, cy + rebate))
        review = r.get("review", {})
        if review.get("select"):
            for k in range(5):
                d.rectangle([cx - 6 - k, cy - 6 - k, cx + cell_w + 6 + k, cy + t.height + 2 * rebate + 6 + k], outline=red)
        ly = cy + t.height + 2 * rebate + 8
        label = f"{r['index']:02d}"
        if r.get("sweep_value"):
            label += f"  {r['sweep_value']}"
        if r.get("seed") is not None:
            label += f"  seed {r['seed']}"
        d.text((cx, ly), label, fill=(28, 29, 31), font=font)
        tags = review.get("tags") or []
        if tags:
            d.text((cx, ly + 24), ", ".join(tags), fill=red, font=small)
        elif r.get("error"):
            d.text((cx, ly + 24), "run failed", fill=red, font=small)

    sheet.save(batch_dir(batch_id) / "contact_sheet.jpg", quality=90)


# ---------------------------------------------------------------- batch worker

def run_batch(batch_id: str, si_text: str, plan: list, settings: dict, model: str):
    total = len(plan)
    with LOCK:
        JOBS[batch_id] = {"state": "running", "done": 0, "total": total}
    try:
        config_cache = {}
        for i, item in enumerate(plan, start=1):
            seed = item["seed"]
            if seed not in config_cache:
                config_cache[seed] = build_config(si_text, settings, seed)
            cfg = config_cache[seed]
            rec = {
                "index": i,
                "sweep_value": item["sweep_value"],
                "repeat": item["repeat"],
                "prompt": item["prompt"],
                "seed": seed,
                "started": dt.datetime.now().isoformat(timespec="seconds"),
            }
            t0 = time.time()
            try:
                resp = CLIENT.models.generate_content(model=model, contents=item["prompt"], config=cfg)
                texts, thoughts, images = [], [], []
                finish = None
                for cand in resp.candidates or []:
                    finish = str(cand.finish_reason) if cand.finish_reason else finish
                    parts = (cand.content.parts if cand.content else None) or []
                    for part in parts:
                        if getattr(part, "thought", False) and part.text:
                            thoughts.append(part.text)
                        elif part.text:
                            texts.append(part.text)
                        elif part.inline_data and part.inline_data.data:
                            images.append(part.inline_data)
                rec["text"] = "\n\n".join(texts)
                rec["thoughts"] = "\n\n".join(thoughts)
                rec["finish_reason"] = finish
                rec["model_version"] = getattr(resp, "model_version", None)
                rec["usage"] = dump(resp.usage_metadata)
                if resp.prompt_feedback:
                    rec["prompt_feedback"] = dump(resp.prompt_feedback)
                rec["image_count"] = len(images)
                if images:
                    blob = images[-1]
                    raw = blob.data if isinstance(blob.data, bytes) else base64.b64decode(blob.data)
                    ext = ".png" if "png" in (blob.mime_type or "") else ".jpg"
                    name = f"r{i:02d}_{slug(item['sweep_value'] or 'run', 24)}{ext}"
                    (batch_dir(batch_id) / name).write_bytes(raw)
                    rec["image_file"] = name
                    if len(images) > 1:
                        rec["note"] = f"{len(images)} images returned, last one kept"
                else:
                    rec["error"] = "No image returned (see text / finish_reason)."
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
                rec["trace"] = traceback.format_exc(limit=3)
            rec["seconds"] = round(time.time() - t0, 1)
            rec["review"] = {"select": False, "tags": [], "note": ""}

            data = read_batch(batch_id)
            data["runs"].append(rec)
            write_batch(batch_id, data)
            append_global_log({"batch_id": batch_id, **{k: v for k, v in rec.items() if k != "trace"},
                               "si_file": data["meta"]["si_file"], "si_sha256": data["meta"]["si_sha256"],
                               "settings": settings, "model": model})
            with LOCK:
                JOBS[batch_id]["done"] = i
        make_contact_sheet(batch_id)
        with LOCK:
            JOBS[batch_id]["state"] = "done"
    except Exception as e:
        with LOCK:
            JOBS[batch_id] = {"state": "failed", "error": f"{type(e).__name__}: {e}", "done": JOBS[batch_id]["done"], "total": total}
    finally:
        data = read_batch(batch_id)
        data["meta"]["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        data["meta"]["state"] = JOBS[batch_id]["state"]
        write_batch(batch_id, data)


# ---------------------------------------------------------------- routes

@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/status")
def status():
    return jsonify({
        "api_key_found": bool(API_KEY),
        "env_file": str(ENV_PATH) if ENV_PATH else None,
        "model": CONFIG["model"],
        "si_dir": str(SI_DIR),
        "defaults": CONFIG["defaults"],
        "error_tags": ERROR_TAGS,
    })


@app.get("/api/si")
def list_si():
    out = []
    for f in sorted(SI_DIR.iterdir()):
        if f.suffix.lower() in (".md", ".txt") and f.is_file():
            text = f.read_text(encoding="utf-8")
            out.append({"file": f.name, "sha256": sha256_text(text), "chars": len(text)})
    return jsonify(out)


@app.post("/api/batch")
def start_batch():
    if CLIENT is None:
        return jsonify({"error": "No API key found. Check config.json api_key_env_names against your .env."}), 400
    body = request.get_json(force=True)
    si_file = body.get("si_file", "")
    si_path = (SI_DIR / si_file).resolve()
    if SI_DIR.resolve() not in si_path.parents or not si_path.exists():
        return jsonify({"error": f"System instruction file not found in si/: {si_file}"}), 400
    si_text = si_path.read_text(encoding="utf-8")

    template = (body.get("prompt") or "").strip()
    if not template:
        return jsonify({"error": "Prompt is empty."}), 400
    values = [v.strip() for v in (body.get("sweep_values") or "").splitlines() if v.strip()]
    if values and "{sweep}" not in template:
        return jsonify({"error": "Sweep values given but the prompt has no {sweep} placeholder."}), 400
    if not values:
        values = [None]
    repeats = max(1, min(int(body.get("repeats", 1)), 20))
    base_seed = body.get("seed")
    base_seed = int(base_seed) if str(base_seed).strip().lstrip("-").isdigit() else None
    fixed_seed = bool(body.get("fixed_seed"))

    settings = {
        "temperature": float(body.get("temperature", CONFIG["defaults"]["temperature"])),
        "top_p": float(body.get("top_p", CONFIG["defaults"]["top_p"])),
        "thinking_level": body.get("thinking_level") or None,
        "include_thoughts": bool(body.get("include_thoughts")),
        "aspect_ratio": body.get("aspect_ratio") or None,
        "image_size": body.get("image_size") or None,
    }
    try:
        build_config(si_text, settings, None)
    except Exception as e:
        return jsonify({"error": f"Settings rejected by the SDK: {e}"}), 400

    plan, n = [], 0
    for v in values:
        for r in range(1, repeats + 1):
            seed = None
            if base_seed is not None:
                seed = base_seed if fixed_seed else base_seed + n
            plan.append({"sweep_value": v, "repeat": r, "seed": seed,
                         "prompt": template.replace("{sweep}", v) if v else template})
            n += 1

    label = slug(body.get("label") or "", 30)
    batch_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + (f"_{label}" if label != "run" else "")
    batch_dir(batch_id).mkdir(parents=True)
    (batch_dir(batch_id) / "si_snapshot.txt").write_text(si_text, encoding="utf-8")
    write_batch(batch_id, {
        "meta": {
            "batch_id": batch_id,
            "label": body.get("label") or "",
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "model": CONFIG["model"],
            "si_file": si_file,
            "si_sha256": sha256_text(si_text),
            "prompt_template": template,
            "sweep_values": [v for v in values if v],
            "repeats": repeats,
            "settings": settings,
            "base_seed": base_seed,
            "fixed_seed": fixed_seed,
            "planned_runs": len(plan),
            "state": "running",
        },
        "runs": [],
    })
    threading.Thread(target=run_batch, args=(batch_id, si_text, plan, settings, CONFIG["model"]), daemon=True).start()
    return jsonify({"batch_id": batch_id, "planned_runs": len(plan)})


@app.get("/api/batches")
def list_batches():
    out = []
    for d in sorted(RUNS_DIR.iterdir(), reverse=True):
        f = d / "batch.json"
        if d.is_dir() and f.exists():
            m = json.loads(f.read_text(encoding="utf-8"))["meta"]
            out.append({"batch_id": m["batch_id"], "label": m.get("label", ""), "planned_runs": m["planned_runs"],
                        "state": m.get("state")})
    return jsonify(out)


@app.get("/api/batch/<batch_id>")
def get_batch(batch_id):
    data = read_batch(batch_id)
    with LOCK:
        job = dict(JOBS.get(batch_id, {}))
    data["job"] = job or {"state": data["meta"].get("state", "done")}
    data["has_contact_sheet"] = (batch_dir(batch_id) / "contact_sheet.jpg").exists()
    return jsonify(data)


@app.post("/api/batch/<batch_id>/review")
def review(batch_id):
    body = request.get_json(force=True)
    idx = int(body["index"])
    data = read_batch(batch_id)
    for r in data["runs"]:
        if r["index"] == idx:
            r["review"] = {
                "select": bool(body.get("select")),
                "tags": [t for t in body.get("tags", []) if t in ERROR_TAGS],
                "note": body.get("note", "")[:2000],
                "reviewed": dt.datetime.now().isoformat(timespec="seconds"),
            }
            break
    else:
        abort(404)
    write_batch(batch_id, data)
    with LOCK:
        running = JOBS.get(batch_id, {}).get("state") == "running"
    if not running:
        make_contact_sheet(batch_id)
    return jsonify({"ok": True})


@app.get("/runs/<batch_id>/<path:name>")
def run_file(batch_id, name):
    return send_from_directory(batch_dir(batch_id), name, max_age=0)


if __name__ == "__main__":
    print(f"LSA Dispatcher  model={CONFIG['model']}  key={'found' if API_KEY else 'MISSING'}  env={ENV_PATH}")
    print(f"SI library: {SI_DIR}")
    app.run(host="127.0.0.1", port=5057, debug=False, threaded=True)
