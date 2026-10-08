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


# ------------------------------------------------------------------ config

def load_models() -> dict:
    if not MODELS_PATH.is_file():
        raise HTTPException(status_code=500, detail=(
            f"Missing {MODELS_PATH}. Copy the lsa folder (models.json, instructions, addenda) "
            f"into {BASE}, beside lsa_server.py."))
    return json.loads(MODELS_PATH.read_text(encoding="utf-8"))


def compass_point(deg: float) -> str:
    return COMPASS[int(((deg % 360) + 11.25) // 22.5) % 16]


class Shot(BaseModel):
    place: str
    standpoint: str
    bearing: float
    subject: str
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
        return json.loads(f'"{m.group(1)}"'), "RENDER_PROMPT field in JSON"
    return None, None


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
    try:
        return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


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
    PRESETS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"saved": p.name.strip()}


@app.delete("/api/presets/{name}")
def delete_preset(name: str):
    data = _presets()
    if data.pop(name, None) is None:
        raise HTTPException(status_code=404, detail=f"No preset named {name}")
    PRESETS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
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
    }
    (d / "shot.json").write_text(req.shot.model_dump_json(indent=2), encoding="utf-8")
    (d / "user_prompt.txt").write_text(user_prompt, encoding="utf-8")
    (d / "instruction_used.md").write_text(instruction, encoding="utf-8")

    def save_settings():
        (d / "settings.json").write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")

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
            yield _event("analysis", text=analysis, seconds=settings["analysis_seconds"])

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
            s = json.loads(_read(d / "settings.json") or "{}")
            shot = json.loads(_read(d / "shot.json") or "{}")
            out.append({"run_id": d.name, "created": s.get("created"), "place": shot.get("place"),
                        "subject": shot.get("subject"), "label": s.get("label"),
                        "has_image": bool(s.get("image_file")), "error": s.get("error"),
                        "addendum": s.get("addendum")})
    return out


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str):
    d = _run_dir(run_id)
    s = json.loads(_read(d / "settings.json") or "{}")
    return {
        "settings": s, "shot": json.loads(_read(d / "shot.json") or "{}"),
        "user_prompt": _read(d / "user_prompt.txt"), "instruction": _read(d / "instruction_used.md"),
        "analysis": _read(d / "analysis.md"), "render_prompt": _read(d / "render_prompt.txt"),
        "render_notes": _read(d / "render_notes.txt"),
        "renders": s.get("renders") or ([s["image_file"]] if s.get("image_file") else []),
        "image": f"/api/runs/{run_id}/image" if s.get("image_file") else None,
    }


@app.get("/api/runs/{run_id}/image")
def run_image(run_id: str, f: Optional[str] = None):
    d = _run_dir(run_id)
    s = json.loads(_read(d / "settings.json") or "{}")
    name = f if f in (s.get("renders") or []) else s.get("image_file")
    if not name or not (d / name).exists():
        raise HTTPException(status_code=404, detail="This run has no image.")
    return FileResponse(d / name)


@app.post("/api/runs/{run_id}/render")
def rerender(run_id: str):
    """Render again from the saved render prompt. Earlier images are kept."""
    d = _run_dir(run_id)
    s = json.loads(_read(d / "settings.json") or "{}")
    prompt = _read(d / "render_prompt.txt")
    if not prompt:
        raise HTTPException(status_code=422, detail="This run has no render prompt to render from.")
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
    s.pop("error", None)
    (d / "settings.json").write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"image": f"/api/runs/{run_id}/image?f={f}", "file": f, "renders": s["renders"]}
