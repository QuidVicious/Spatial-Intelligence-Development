"""
LSA Studio server: pure latent space archaeology runs, no Cesium.

One run = the shot form becomes a prompt, the text model excavates the view with your system
instruction (SI3.8 plus an optional per-model addendum), its RENDER_PROMPT section goes to
the image model, and everything is saved in lsa/runs/<run id>/.

Start: python -m uvicorn lsa_server:app --reload --port 8001   (start_server.bat does this)
Page:  http://localhost:8001
"""

import base64
import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from google import genai
from google.genai import types
from pydantic import BaseModel

ENV_PATH = Path(r"C:\DEV\Squid\SquidBlack\.env")
load_dotenv(dotenv_path=ENV_PATH) if ENV_PATH.exists() else load_dotenv()

BASE = Path(__file__).resolve().parent
LSA = BASE / "lsa"
INSTRUCTIONS = LSA / "instructions"
ADDENDA = LSA / "addenda"
RUNS = LSA / "runs"
MODELS_PATH = LSA / "models.json"
PRESETS_PATH = LSA / "presets.json"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")

COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
COMPASS_WORDS = {
    "N": "north", "NNE": "north-north-east", "NE": "north-east", "ENE": "east-north-east",
    "E": "east", "ESE": "east-south-east", "SE": "south-east", "SSE": "south-south-east",
    "S": "south", "SSW": "south-south-west", "SW": "south-west", "WSW": "west-south-west",
    "W": "west", "WNW": "west-north-west", "NW": "north-west", "NNW": "north-north-west",
}

app = FastAPI(title="LSA Studio")


# ------------------------------------------------------------------ JSON on disk
# Every JSON file is read so that one bad file can never take down a page, and written so that a
# crash mid-write can never leave a half-written file: write to a temporary file, then swap it in.

def read_json(path: Path, default=None, kind=dict):
    """The file's JSON if it parses to the expected kind, else `default` (and a note on the console)."""
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[JSON] {path} is unreadable ({e}); using the default")
        return default
    if kind is not None and not isinstance(data, kind):
        print(f"[JSON] {path} holds a {type(data).__name__}, not a {kind.__name__}; using the default")
        return default
    return data


def write_json(path: Path, data) -> None:
    """Atomic write: the old file stays whole until the new one is complete."""
    text = json.dumps(data, indent=2, ensure_ascii=False)
    json.loads(text)                                   # never write something that will not read back
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ------------------------------------------------------------------ config

def load_models() -> dict:
    if not MODELS_PATH.is_file():
        raise HTTPException(status_code=500, detail=(
            f"Missing {MODELS_PATH}. Copy the lsa folder (models.json, instructions, addenda) "
            f"into {BASE}, beside lsa_server.py."))
    try:
        data = json.loads(MODELS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{MODELS_PATH.name} is not valid JSON: {e}")
    missing = [k for k in ("text_model", "image_models", "aspect_ratios", "image_sizes") if k not in data]
    if missing:
        raise HTTPException(status_code=500, detail=f"{MODELS_PATH.name} is missing: {', '.join(missing)}")
    return data


def compass_point(deg: float) -> str:
    return COMPASS[int(((deg % 360) + 11.25) // 22.5) % 16]


class Shot(BaseModel):
    place: str
    standpoint: str
    bearing: float
    subject: str
    layout: Optional[str] = None
    distance_m: Optional[float] = None
    framing: str = "medium"
    camera_height: str = "eye level"
    focal_mm: Optional[int] = None
    date: Optional[str] = None
    time: Optional[str] = None
    weather: Optional[str] = None
    focus: Optional[str] = None


class RunRequest(BaseModel):
    shot: Shot
    instruction: str = "SI3.8.md"
    image_model: str = "nb2"
    use_addendum: bool = True
    aspect_ratio: str = "16:9"
    image_size: str = "2K"
    label: Optional[str] = None
    # Stamped by the page when the run is made with the Cesium camera linked at a saved view (2026-10-15),
    # so the pipeline's LSA pass can pick the newest LSA run for that view.
    saved_view_id: Optional[str] = None
    saved_view_name: Optional[str] = None


def build_prompt(s: Shot) -> str:
    """The single source of the user prompt: the page previews exactly this."""
    facing = compass_point(s.bearing)
    seen = compass_point(s.bearing + 180)
    lines = [
        "SCENE REQUEST",
        f"Place: {s.place.strip()}",
        f"Standpoint: {s.standpoint.strip()}",
        f"Facing: {COMPASS_WORDS[facing]} ({facing}, {s.bearing:.0f} degrees). From here you see the "
        f"{COMPASS_WORDS[seen]}-facing sides of the tree trunks, walls and other objects in front of you.",
        f"Looking at: {s.subject.strip()}",
    ]
    if s.layout:
        lines.append(f"Scene layout: {s.layout.strip()}")
    if s.distance_m:
        lines.append(f"Distance to subject: about {s.distance_m:.0f} m")
    frame = f"Framing: {s.framing} view, camera at {s.camera_height}"
    if s.focal_mm:
        frame += f", {s.focal_mm} mm lens"
    lines.append(frame)
    when = " ".join(x for x in (s.date, s.time) if x)
    if when:
        lines.append(f"Date and time: {when}")
    if s.weather:
        lines.append(f"Weather: {s.weather.strip()}")
    if s.focus:
        lines.append(f"Focus: {s.focus.strip()}")
    lines += [
        "",
        "Excavate this view through the domain lenses"
        + (", with particular attention to the focus above." if s.focus else "."),
        "",
        "End your response with a section headed exactly ---RENDER_PROMPT--- containing one prompt "
        "for an image model that renders this view as a photograph.",
    ]
    return "\n".join(lines)


def build_instruction(instruction_file: str, model: dict, use_addendum: bool) -> str:
    base = (INSTRUCTIONS / instruction_file)
    if not base.is_file():
        raise HTTPException(status_code=400, detail=f"Instruction file not found: {instruction_file}")
    text = base.read_text(encoding="utf-8").rstrip()
    if use_addendum and model.get("addendum"):
        add = ADDENDA / model["addendum"]
        if not add.is_file():
            raise HTTPException(status_code=400, detail=f"Addendum not found: {model['addendum']}")
        text += "\n\n---\n\n" + add.read_text(encoding="utf-8").strip()
    return text + "\n"


def extract_render_prompt(text: str):
    m = re.search(r"-{3}\s*RENDER_PROMPT\s*-{3}\s*(.+)$", text, re.S)
    if m:
        out = re.sub(r"^```[a-z]*\s*|\s*```\s*$", "", m.group(1).strip()).strip()
        if out:
            return out, "RENDER_PROMPT section"
    m = re.search(r'"RENDER_PROMPT"\s*:\s*"((?:[^"\\]|\\.)+)"', text)
    if m:
        try:
            return json.loads(f'"{m.group(1)}"'), "RENDER_PROMPT field in JSON"
        except Exception:
            return m.group(1).replace('\\"', '"').replace("\\n", "\n"), "RENDER_PROMPT field in JSON (loosely decoded)"
    return None, None


def parse_lsa_metadata(text: str) -> dict:
    """SI3.x opens its analysis with an LSA_METADATA JSON block naming the lenses it chose.
    Read it strictly if it parses; otherwise pull the fields out loosely, so a stray bracket in the
    model's JSON never hides which lenses ran. `parsed` says which way it was read."""
    out = {"project": None, "centroid": None, "lenses": [], "parsed": "none"}
    if not text:
        return out
    blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    head = text.find("LSA_METADATA")
    if head >= 0:
        start = text.rfind("{", 0, head)
        if start >= 0:
            depth = 0
            for i in range(start, len(text)):
                depth += {"{": 1, "}": -1}.get(text[i], 0)
                if depth == 0:
                    blocks.append(text[start:i + 1]); break
    for b in blocks:
        try:
            meta = json.loads(b)
        except Exception:
            continue
        meta = meta.get("LSA_METADATA", meta) if isinstance(meta, dict) else {}
        keys = meta.get("ACTIVE_DOMAIN_KEYS") if isinstance(meta, dict) else None
        if isinstance(keys, list):
            out.update(project=meta.get("PROJECT_NAME"), centroid=meta.get("CENTROID_SUPPRESSED"),
                       lenses=[str(k).strip() for k in keys if str(k).strip()], parsed="json")
            return out
    m = re.search(r'"ACTIVE_DOMAIN_KEYS"\s*:\s*\[(.*?)\]', text, re.S)
    if m:
        out["lenses"] = [x.strip() for x in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)) if x.strip()]
        for field, key in (("project", "PROJECT_NAME"), ("centroid", "CENTROID_SUPPRESSED")):
            f = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if f:
                out[field] = f.group(1)
        out["parsed"] = "loose"
    return out


def render_image(client, d: Path, model: str, prompt: str, aspect_ratio: str, image_size: str) -> str:
    """Render one image from a prompt into run folder d. Returns the new file name."""
    cfg = dict(response_modalities=["TEXT", "IMAGE"])
    if hasattr(types, "ImageConfig"):
        cfg["image_config"] = types.ImageConfig(aspect_ratio=aspect_ratio, image_size=image_size)
    img = client.models.generate_content(model=model, contents=[prompt], config=types.GenerateContentConfig(**cfg))
    n = len(list(d.glob("image*.*"))) + 1
    image_file, notes = None, []
    for cand in (img.candidates or []):
        for part in (cand.content.parts if cand.content else []):
            if getattr(part, "inline_data", None) and part.inline_data.data and not image_file:
                mime = part.inline_data.mime_type or "image/png"
                ext = {"image/jpeg": "jpg", "image/webp": "webp"}.get(mime, "png")
                image_file = f"image.{ext}" if n == 1 else f"image_{n}.{ext}"
                (d / image_file).write_bytes(part.inline_data.data)
            elif getattr(part, "text", None):
                notes.append(part.text)
    if notes:
        with open(d / "render_notes.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(notes) + "\n")
    if not image_file:
        reason = getattr((img.candidates or [None])[0], "finish_reason", None)
        raise RuntimeError(f"The image model returned no image (finish reason: {reason}). "
                           "The analysis and render prompt are saved: use Render again.")
    return image_file


def slug(s: str, n: int = 40) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")[:n] or "run"


# ------------------------------------------------------------------ pages and config

@app.get("/")
def page():
    return FileResponse(BASE / "lsa_studio.html")


@app.get("/pipeline.js")
def pipeline_js():
    # The Cesium pipeline client: talks to the pipeline server on port 8000.
    return FileResponse(BASE / "pipeline.js", media_type="text/javascript")


@app.get("/api/config")
def config():
    models = load_models()
    return {
        "text_model": models["text_model"],
        "image_models": [{"id": k, **{x: v[x] for x in ("label", "model", "addendum") if x in v}}
                         for k, v in models["image_models"].items()],
        "instructions": sorted(p.name for p in INSTRUCTIONS.glob("*.md")),
        "aspect_ratios": models["aspect_ratios"],
        "image_sizes": models["image_sizes"],
    }


@app.post("/api/preview")
def preview(shot: Shot):
    s = compass_point(shot.bearing)
    return {"prompt": build_prompt(shot), "facing": s, "seen": compass_point(shot.bearing + 180)}


# ------------------------------------------------------------------ presets

def _presets() -> dict:
    return read_json(PRESETS_PATH, default={})


class Preset(BaseModel):
    name: str
    shot: Shot


@app.get("/api/presets")
def presets():
    return _presets()


@app.post("/api/presets")
def save_preset(p: Preset):
    data = _presets()
    data[p.name.strip()] = p.shot.model_dump()
    write_json(PRESETS_PATH, data)
    return {"saved": p.name.strip()}


@app.delete("/api/presets/{name}")
def delete_preset(name: str):
    data = _presets()
    if data.pop(name, None) is None:
        raise HTTPException(status_code=404, detail=f"No preset named {name}")
    write_json(PRESETS_PATH, data)
    return {"deleted": name}


# ------------------------------------------------------------------ runs

def _event(kind: str, **kw) -> str:
    return json.dumps({"event": kind, **kw}) + "\n"


@app.post("/api/run")
def run(req: RunRequest):
    models = load_models()
    img_model = models["image_models"].get(req.image_model)
    if not img_model:
        raise HTTPException(status_code=400, detail=f"Unknown image model: {req.image_model}")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set in .env.")
    user_prompt = build_prompt(req.shot)
    instruction = build_instruction(req.instruction, img_model, req.use_addendum)

    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{slug(req.label or req.shot.place)}"
    d = RUNS / run_id
    d.mkdir(parents=True, exist_ok=True)
    settings = {
        "run_id": run_id, "created": datetime.now().isoformat(timespec="seconds"),
        "text_model": models["text_model"], "image_model": img_model["model"],
        "image_model_label": img_model.get("label", req.image_model),
        "instruction": req.instruction, "addendum": img_model.get("addendum") if req.use_addendum else None,
        "aspect_ratio": req.aspect_ratio, "image_size": req.image_size, "label": req.label,
        "saved_view_id": req.saved_view_id, "saved_view_name": req.saved_view_name,
    }
    (d / "shot.json").write_text(req.shot.model_dump_json(indent=2), encoding="utf-8")
    (d / "user_prompt.txt").write_text(user_prompt, encoding="utf-8")
    (d / "instruction_used.md").write_text(instruction, encoding="utf-8")

    def save_settings():
        write_json(d / "settings.json", settings)

    def stream():
        client = genai.Client(api_key=api_key)
        try:
            save_settings()
            yield _event("stage", stage="analysis", message=f"Excavating with {models['text_model']}...", run_id=run_id)
            t0 = time.time()
            resp = client.models.generate_content(
                model=models["text_model"], contents=[user_prompt],
                config=types.GenerateContentConfig(system_instruction=instruction),
            )
            analysis = resp.text or ""
            settings["analysis_seconds"] = round(time.time() - t0, 1)
            (d / "analysis.md").write_text(analysis, encoding="utf-8")
            if not analysis.strip():
                raise RuntimeError("The text model returned nothing. Try the run again.")
            meta = parse_lsa_metadata(analysis)
            settings["lsa_metadata"] = meta
            save_settings()
            yield _event("analysis", text=analysis, seconds=settings["analysis_seconds"], lsa_metadata=meta)

            render_prompt, source = extract_render_prompt(analysis)
            if not render_prompt:
                render_prompt, source = analysis, "whole analysis (no RENDER_PROMPT section found)"
            settings["render_prompt_source"] = source
            (d / "render_prompt.txt").write_text(render_prompt, encoding="utf-8")
            yield _event("render_prompt", text=render_prompt, source=source)

            yield _event("stage", stage="render", message=f"Rendering with {img_model.get('label', img_model['model'])}...")
            t1 = time.time()
            image_file = render_image(client, d, img_model["model"], render_prompt, req.aspect_ratio, req.image_size)
            settings["render_seconds"] = round(time.time() - t1, 1)
            settings["image_file"] = image_file
            settings["renders"] = [image_file]
            save_settings()
            yield _event("done", run_id=run_id, image=f"/api/runs/{run_id}/image",
                         seconds=round(time.time() - t0, 1))
        except Exception as e:
            traceback.print_exc()
            settings["error"] = str(e)
            save_settings()
            yield _event("error", message=str(e), run_id=run_id)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


def _run_dir(run_id: str) -> Path:
    if not RUN_ID_RE.match(run_id or ""):
        raise HTTPException(status_code=400, detail="Invalid run id.")
    d = RUNS / run_id
    if not d.is_dir():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return d


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


@app.get("/api/runs")
def runs():
    out = []
    if RUNS.exists():
        for d in sorted(RUNS.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            s = read_json(d / "settings.json", default={})
            shot = read_json(d / "shot.json", default={})
            a = d / "analysis.md"
            out.append({"run_id": d.name, "created": s.get("created"), "place": shot.get("place"),
                        "subject": shot.get("subject"), "label": s.get("label"),
                        "has_image": bool(s.get("image_file")), "error": s.get("error"),
                        # 2026-10-16: the LSA pass lists runs by this, not by error: a run whose render failed
                        # can still have a good analysis.
                        "has_analysis": a.is_file() and a.stat().st_size > 0,
                        "has_layout": bool((shot.get("layout") or "").strip()),
                        "addendum": s.get("addendum"), "instruction": s.get("instruction"),
                        "saved_view_id": s.get("saved_view_id"), "saved_view_name": s.get("saved_view_name")})
    return out


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    d = _run_dir(run_id)
    s = read_json(d / "settings.json", default={})
    analysis = _read(d / "analysis.md")
    return {
        "settings": s, "shot": read_json(d / "shot.json", default={}),
        "lsa_metadata": s.get("lsa_metadata") or parse_lsa_metadata(analysis),
        "user_prompt": _read(d / "user_prompt.txt"), "instruction": _read(d / "instruction_used.md"),
        "analysis": analysis, "render_prompt": _read(d / "render_prompt.txt"),
        "render_prompt_model": _read(d / "render_prompt_model.txt") or _read(d / "render_prompt.txt"),
        "render_notes": _read(d / "render_notes.txt"),
        "renders": s.get("renders") or ([s["image_file"]] if s.get("image_file") else []),
        "image": f"/api/runs/{run_id}/image" if s.get("image_file") else None,
    }


@app.get("/api/runs/{run_id}/image")
def run_image(run_id: str, f: Optional[str] = None):
    d = _run_dir(run_id)
    s = read_json(d / "settings.json", default={})
    name = f if f in (s.get("renders") or []) else s.get("image_file")
    if not name or not (d / name).exists():
        raise HTTPException(status_code=404, detail="This run has no image.")
    return FileResponse(d / name)


class RerenderRequest(BaseModel):
    prompt: Optional[str] = None   # a render prompt edited by hand (Pro Mode); None = the saved one


@app.post("/api/runs/{run_id}/render")
def rerender(run_id: str, req: Optional[RerenderRequest] = None):
    """Render again from the saved render prompt, or from a hand-edited one. Earlier images are kept.
    A hand edit never overwrites the model's prompt: the model's text stays in render_prompt_model.txt,
    each edited version is saved as render_prompt_vN.txt, and render_log records which prompt made which image."""
    d = _run_dir(run_id)
    s = read_json(d / "settings.json", default={})
    saved = _read(d / "render_prompt.txt")
    if not saved:
        raise HTTPException(status_code=422, detail="This run has no render prompt to render from.")
    model_prompt = _read(d / "render_prompt_model.txt") or saved
    prompt, prompt_file, edited = saved, "render_prompt.txt", bool(s.get("render_prompt_edited"))
    new = (req.prompt or "").strip() if req else ""
    if new and new != saved.strip():
        if not (d / "render_prompt_model.txt").exists():
            (d / "render_prompt_model.txt").write_text(model_prompt, encoding="utf-8")
        n = len(list(d.glob("render_prompt_v*.txt"))) + 1
        prompt_file = f"render_prompt_v{n}.txt"
        (d / prompt_file).write_text(new, encoding="utf-8")
        write_text_atomic(d / "render_prompt.txt", new)   # the current prompt
        prompt, edited = new, new != model_prompt.strip()
        s["render_prompt_edited"] = edited
    elif s.get("render_prompt_edited"):
        log = s.get("render_log") if isinstance(s.get("render_log"), list) else []
        prompt_file = (log[-1] if log and isinstance(log[-1], dict) else {}).get("prompt_file", "render_prompt.txt")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set in .env.")
    try:
        f = render_image(genai.Client(api_key=api_key), d, s["image_model"], prompt,
                         s.get("aspect_ratio", "16:9"), s.get("image_size", "2K"))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    s["image_file"] = f
    s["renders"] = (s.get("renders") or []) + [f]
    log = s.get("render_log") if isinstance(s.get("render_log"), list) and s.get("render_log") else [{"image": x, "prompt_file": "render_prompt.txt", "edited": False}
                                   for x in (s["renders"][:-1])]
    log.append({"image": f, "prompt_file": prompt_file, "edited": edited})
    s["render_log"] = log
    s.pop("error", None)
    write_json(d / "settings.json", s)
    return {"image": f"/api/runs/{run_id}/image?f={f}", "file": f, "renders": s["renders"], "edited": edited}
