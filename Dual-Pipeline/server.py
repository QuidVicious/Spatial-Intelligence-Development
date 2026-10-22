"""
Server: FastAPI Orchestration Endpoint for the Spatial Intelligence Pipeline.
Linear execution with Unified NDJSON Lifecycle Streaming:
1. Atmosphere & Ephemeris (Lighting & Weather)
2. Domain Engine (4 Mothers Causal Spatial Cognition with Date/Phenology Grounding)
3. Spatial Scaffold Engine (7 Strata RFC 7946 GeoJSON Database)
4. Prompt Compiler (Conditioning Adapter with Static Decluttering & Phenology Contracts)
5. Vision Preprocessor (CUDA Delighting)
6. Synthesis Engine (Gemini 2D 2560x1440 2K QHD or World Labs Marble 3D)
7. Archiver (Persistence)
"""

import os
import re
import json
import base64
import time
import asyncio
import secrets
import calendar
import copy
import math
import threading
from datetime import datetime, timezone, date as _date, timedelta
import requests
import traceback
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Pipeline Lifecycle Telemetry
from pipeline_bus import (
    PipelineStage,
    stage_activate,
    emit_terminal_banner,
    emit_terminal_complete,
    format_ndjson
)

# Pipeline Modules
from domain_engine import analyze_spatial_domain, reverse_geocode, ViewScope, DomainAnalysisResult, generate_phenology, get_phenology_calendar, read_streetview, rewrite_condition_from_streetview, weave_lsa_into_scene
from lighting_engine import resolve_lighting_state, get_live_weather
from spatial_scaffold_engine import build_spatial_scaffold
from prompt_engine import compile_conditioning
from vision_preprocessor import delight_image
from synthesis_engine import synthesize_twin
from archiver import archive_run, DEFAULT_RUNS_DIR
from composite_engine import composite_canopy
import alignment_engine

# Load Environment
env_path = Path(r"C:\DEV\Squid\SquidBlack\.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[Server] Loaded environment from: {env_path}")
else:
    load_dotenv()
    print("[Server] Loaded environment from local directory .env")

app = FastAPI(
    title="Spatial Intelligence Pipeline API",
    description="Multimodal spatial cognition, deterministic lighting, 7-Strata 3D scaffold, and 2D/3D visual twin synthesis.",
    version="5.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
async def get_client_config():
    """Serves non-secret tokens and configuration to the frontend."""
    cesium_token = (
        os.getenv("CESIUM_ION_TOKEN")
        or os.getenv("CESIUM_TOKEN")
        or os.getenv("CESIUM_ION_ACCESS_TOKEN")
        or ""
    )
    return {"cesium_ion_token": cesium_token}


@app.get("/api/weather")
async def get_weather(lat: float = Query(...), lon: float = Query(...)):
    """Fetches real-time live weather and timezone for the given coordinates."""
    return get_live_weather(lat, lon)


@app.get("/api/geocode")
async def get_geocode(lat: float = Query(...), lon: float = Query(...)):
    """Resolves coordinates into a human-readable postal address or locality."""
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    address = reverse_geocode(lat, lon, google_maps_key)
    return {"address": address}


@app.get("/api/search")
async def search_place(q: str = Query(..., description="Address, place name, or postcode")):
    """Forward geocode a free-text place to coordinates."""
    key = os.getenv("GOOGLE_MAPS_API_KEY") or os.getenv("GOOGLE_MAPS_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        try:
            r = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": q, "key": key}, timeout=6
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    top = results[0]
                    loc = top["geometry"]["location"]
                    vp = top["geometry"].get("viewport") or {}
                    return {
                        "address": top.get("formatted_address"),
                        "latitude": loc["lat"],
                        "longitude": loc["lng"],
                        "viewport": vp,
                        "source": "google"
                    }
        except Exception as e:
            print(f"[Search Warning] Google: {e}")

    # Fallback: Nominatim needs a real User-Agent and is rate limited.
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "json", "limit": 1},
            headers={"User-Agent": "SquidBlackSpatial/1.0"}, timeout=6
        )
        if r.status_code == 200:
            hits = r.json()
            if hits:
                return {
                    "address": hits[0].get("display_name"),
                    "latitude": float(hits[0]["lat"]),
                    "longitude": float(hits[0]["lon"]),
                    "source": "nominatim"
                }
    except Exception as e:
        print(f"[Search Warning] Nominatim: {e}")

    raise HTTPException(status_code=404, detail=f"No match for '{q}'")


# -------------------------------------------------------------------------
# Request Schemas
# -------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude")
    longitude: float = Field(..., description="WGS84 Longitude")
    altitude_agl: float = Field(0.0, description="Altitude AGL in meters")
    heading: float = Field(0.0, description="Camera Heading (degrees)")
    pitch: float = Field(-45.0, description="Camera Pitch (degrees)")
    fov: float = Field(45.0, description="Camera FOV (degrees)")
    target_latitude: Optional[float] = Field(None, description="Latitude of the surface point at frame center")
    target_longitude: Optional[float] = Field(None, description="Longitude of the surface point at frame center")
    target_height_m: Optional[float] = Field(None, description="Ellipsoid height of the frame-center surface point (m)")
    target_distance_m: Optional[float] = Field(None, description="Camera-to-target distance (m)")
    target_method: Optional[str] = Field(None, description="PICK_POSITION or GLOBE_PICK; null if no surface was hit")
    tile_mode: str = Field("3D_TILES", description="3D_TILES, 2D_SATELLITE, or STANDALONE")
    ground_elevation_m: Optional[float] = Field(None, description="Sampled ground elevation in metres")
    altitude_method: Optional[str] = Field(None, description="TILESET_SAMPLE or ELLIPSOID_FALLBACK")
    date: Optional[str] = Field(None, description="YYYY-MM-DD date")
    time_of_day: Optional[float] = Field(None, description="24-hour decimal time (e.g. 14.5 = 14:30)")
    timestamp_utc: Optional[str] = Field(None, description="ISO 8601 UTC timestamp")
    lighting_mode: str = Field("SOLAR", description="SOLAR or FLOODLIGHT")
    weather_mode: str = Field("AUTO", description="AUTO, SUNNY, RAIN, FOG, SNOW, OVERCAST")


class ProcessViewRequest(BaseModel):
    screenshot_b64: Optional[str] = Field(None, description="Optional Base64 encoded viewport capture")
    shadow_pass_b64: Optional[str] = Field(None, description="Optional: the same capture with Cesium's sun and cast shadows on, "
                                           "at the frame's date and time. When present, its shadows are laid onto the delighted seed.")
    shadow_base_b64: Optional[str] = Field(None, description="Optional: the shadowless capture paired with shadow_pass_b64, when it is "
                                           "not screenshot_b64 (prints: the saved view rendered by the client at the print's time).")
    pano_b64: Optional[str] = Field(None, description="Optional Base64 equirectangular 2:1 panorama")
    marble_input_mode: str = Field("text", description="text, image, pano, or multi-image")
    gemini_budget: int = Field(3200, description="Total character budget for the Gemini prompt")
    multi_view_images: Optional[List[str]] = Field(None, description="Optional list of Base64 or URLs for multi-view synthesis")
    telemetry: TelemetryPayload
    address: Optional[str] = Field(None, description="Optional pre-resolved address")
    provider: str = Field("GEMINI", description="GEMINI or WORLD_LABS")
    target_model: Optional[str] = Field(None, description="Model SKU (e.g. gemini-3.1-flash-image, marble-1.1)")
    view_scope: str = Field("FRUSTUM", description="FRUSTUM, OMNI_360, or STANDALONE")
    disable_recaption: bool = Field(True, description="Enforce original prompt without API auto-rewrite")
    use_search_grounding: bool = Field(False, description="Attach Google Search grounding to the domain call")
    saved_view_id: Optional[str] = Field(None, description="Saved view the camera was at when captured")
    saved_view_name: Optional[str] = Field(None, description="Display name of that saved view")
    replay_of: Optional[str] = Field(None, description="Archived run id to replay: reuses its capture and domain text")
    documentary_prompt_override: Optional[str] = Field(None, description="Replay only: edited scene text replacing the frozen documentary prompt")
    mode: Optional[str] = Field(None, description="KEYSTONE (neutral master plate from replay_of) or PRINT (edit of a view's approved keystone)")
    print_view_id: Optional[str] = Field(None, description="PRINT only: saved view whose approved keystone is the seed")
    series_id: Optional[str] = Field(None, description="Set by the series runner: the series this frame belongs to")
    series_frame: Optional[int] = Field(None, description="Set by the series runner: 1-based frame number")
    seed: Optional[int] = Field(None, description="Render seed; blank picks a random one. Always recorded, so any run can be reproduced")
    composite: bool = Field(True, description="PRINT only: keep the keystone's pixels outside the changed canopy, when the print's weather matches the keystone's")
    streetview: Optional[dict] = Field(None, description="KEYSTONE only: {pano_id, heading, pitch, fov, date, distance_m, copyright}; the pano is fetched, used, and never stored")
    lsa_join: Optional[dict] = Field(None, description="Replay and KEYSTONE only: the LSA pass behind the edited scene text "
                                     "{run_id, label, instruction, ecology, added_structure, species_to_verify, set_aside, not_added, "
                                     "hand_edited_after, director_layout_used}. "
                                     "Its ecology replaces the run's ecology record, so seasonal prints age the same trees the text names.")
    ab: Optional[dict] = Field(None, description="Set by Make keystone A/B: {pair_id, arm, seed, lsa_run_id}")


# -------------------------------------------------------------------------
# Keystones: one approved master plate per saved view
# -------------------------------------------------------------------------
KEYSTONES_PATH = Path(__file__).parent / "keystones.json"


def _load_keystones() -> dict:
    if not KEYSTONES_PATH.exists():
        return {}
    try:
        data = json.loads(KEYSTONES_PATH.read_text(encoding="utf-8"))
        return data.get("views", {}) if isinstance(data, dict) else {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"keystones.json is unreadable: {e}")


def _write_keystones(views: dict) -> None:
    tmp = KEYSTONES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, "views": views}, indent=2), encoding="utf-8")
    tmp.replace(KEYSTONES_PATH)


# -------------------------------------------------------------------------
# Date plates (2026-10-14): keystone > date plate > hour print. A date plate is the approved keystone with one
# date's canopy, under the keystone's neutral light; every hour of that date is relit from it, so the leaves
# stay the same across the day. Keyed by view, then keystone run (a new keystone starts fresh plates), then date.
DATE_PLATES_PATH = Path(__file__).parent / "date_plates.json"


def _load_date_plates() -> dict:
    data = _read_json(DATE_PLATES_PATH) or {}
    plates = data.get("plates")
    return plates if isinstance(plates, dict) else {}


def _date_plate_for(view_id: Optional[str], keystone_run: Optional[str], date: Optional[str]) -> Optional[str]:
    if not (view_id and keystone_run and date):
        return None
    run_id = ((_load_date_plates().get(view_id) or {}).get(keystone_run) or {}).get(date[:10])
    if run_id and (DEFAULT_RUNS_DIR / run_id / "spatial_twin.png").exists():
        return run_id
    return None


def _register_date_plate(view_id: str, keystone_run: str, date: str, run_id: str) -> None:
    plates = _load_date_plates()
    plates.setdefault(view_id, {}).setdefault(keystone_run, {})[date[:10]] = run_id
    tmp = DATE_PLATES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, "plates": plates}, indent=2), encoding="utf-8")
    tmp.replace(DATE_PLATES_PATH)
    print(f"[DatePlate] registered {view_id} / keystone {keystone_run} / {date[:10]} -> {run_id}")


def _midwinter_date(lat: float) -> str:
    """Mid-January in the northern hemisphere, mid-July in the southern: deciduous trees bare, evergreens unchanged."""
    year = datetime.now(timezone.utc).year
    return f"{year}-01-15" if lat >= 0 else f"{year}-07-15"


# -------------------------------------------------------------------------
# Replay: frozen sources loaded back from archived runs
# -------------------------------------------------------------------------
RUN_ID_RE = re.compile(r"^[\w\-]+$")
DOMAIN_MD_SECTIONS = {
    "1": "geological_foundation",
    "2": "architectural_analysis",
    "3": "material_and_lithics",
    "4": "botanical_ecology",
    "5": "static_decluttering_summary",
}
RUN_FILES = {
    "viewport_capture.jpg": "image/jpeg",
    "delighted_reference.jpg": "image/jpeg",
    "spatial_twin.png": "image/png",
    "spatial_twin_raw.png": "image/png",
    "canopy_mask.png": "image/png",
    "spatial_twin_unaligned.png": "image/png",
}


def _run_dir(run_id: str) -> Path:
    if not run_id or not RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=400, detail="Invalid run id.")
    d = DEFAULT_RUNS_DIR / run_id
    if not d.is_dir():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return d


def _read_json(path: Path) -> Optional[dict]:
    """The file's JSON object, or None if it is missing, unreadable, or not an object.
    Callers treat None as "no data", so one bad file never breaks a list or a page."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[JSON] {path} is unreadable: {e}")
        return None
    return data if isinstance(data, dict) else None


def _parse_domain_md(text: str) -> dict:
    """Fallback for runs archived before domain_result.json existed.
    The layout is fixed by archiver.py, so the sections can be read back reliably."""
    fields: dict = {}
    m = re.search(r"^# Spatial Domain Analysis:\s*(.+)$", text, re.M)
    fields["address"] = m.group(1).strip() if m else ""
    m = re.search(r"^\*\*View Scope:\*\*\s*(\w+)", text, re.M)
    fields["view_scope"] = m.group(1) if m else "FRUSTUM"
    for num, key in DOMAIN_MD_SECTIONS.items():
        m = re.search(rf"^## {num}\. [^\n]*\n(.*?)(?=^## \d\. |\Z)", text, re.S | re.M)
        fields[key] = m.group(1).strip() if m else ""
    m = re.search(r"^## 6\. [^\n]*\n```text\n(.*?)\n```", text, re.S | re.M)
    fields["documentary_prompt"] = m.group(1).strip() if m else ""
    return fields


def load_domain_from_run(d: Path):
    data = _read_json(d / "domain_result.json")
    source = "json"
    if data is None:
        md = d / "domain_analysis.md"
        if not md.exists():
            raise HTTPException(status_code=404, detail=f"Run {d.name} has no domain analysis.")
        data = _parse_domain_md(md.read_text(encoding="utf-8"))
        source = "markdown"
    try:
        scope = ViewScope(str(data.get("view_scope") or "FRUSTUM").split(".")[-1])
    except ValueError:
        scope = ViewScope.FRUSTUM
    result = DomainAnalysisResult(
        address=data.get("address") or "",
        view_scope=scope,
        documentary_prompt=data.get("documentary_prompt") or "",
        geological_foundation=data.get("geological_foundation") or "",
        architectural_analysis=data.get("architectural_analysis") or "",
        material_and_lithics=data.get("material_and_lithics") or "",
        botanical_ecology=data.get("botanical_ecology") or "",
        static_decluttering_summary=data.get("static_decluttering_summary") or "",
        raw_response=data.get("raw_response") or "",
        metadata=dict(data.get("metadata") or {}, loaded_from=source),
        phenology=data.get("phenology") or "",
        surface_condition=data.get("surface_condition") or "",
    )
    if not result.documentary_prompt:
        raise HTTPException(status_code=422, detail=f"Run {d.name} has no documentary prompt to replay.")
    return result, source


def _file_data_url(path: Path, mime: str) -> Optional[str]:
    if not path.exists():
        return None
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def load_replay_source(run_id: str) -> dict:
    d = _run_dir(run_id)
    meta = _read_json(d / "run_metadata.json")
    if meta is None:
        raise HTTPException(status_code=422, detail=f"Run {run_id} has no readable run_metadata.json.")
    screenshot = _file_data_url(d / "viewport_capture.jpg", "image/jpeg")
    if not screenshot:
        raise HTTPException(status_code=422, detail=f"Run {run_id} has no viewport capture to use as the seed.")
    domain, source = load_domain_from_run(d)
    return {
        "meta": meta,
        "domain": domain,
        "domain_source": source,
        "screenshot_b64": screenshot,
        "delighted_b64": _file_data_url(d / "delighted_reference.jpg", "image/jpeg"),
    }


# -------------------------------------------------------------------------
# Streaming Pipeline Generator
# -------------------------------------------------------------------------
async def execute_pipeline_stream(request: ProcessViewRequest):
    pipeline_start = time.perf_counter()
    telemetry = request.telemetry
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    world_labs_key = os.getenv("WORLD_LABS_API_KEY") or os.getenv("WLT_API_KEY")
    scene_edited = False
    run_seed = request.seed if request.seed is not None else secrets.randbelow(2**31 - 1)
    composite_info = None
    raw_render_b64 = None
    delight_setting = None
    sun_shadows_info = None
    seed_for_archive = None
    streetview_b64 = None
    streetview_record = None
    canopy_mask_b64 = None
    phenology_date = None
    phenology_source = None
    lsa_join_record = None

    mode = (request.mode or "").strip().upper() or None
    if mode not in (None, "KEYSTONE", "PRINT", "DATE_PLATE"):
        yield format_ndjson({"type": "ERROR", "message": f"Unknown mode: {request.mode}"})
        return
    keystone_run_id = None
    print_like = mode in ("PRINT", "DATE_PLATE")   # both start from the approved keystone of a view
    print_variant = "full"
    date_plate_run_id = None
    if print_like:
        ks = _load_keystones().get(request.print_view_id or "")
        if not ks:
            yield format_ndjson({"type": "ERROR", "message": "This view has no approved keystone yet."})
            return
        if request.provider.upper() == "WORLD_LABS":
            yield format_ndjson({"type": "ERROR", "message": "Prints from a keystone are Gemini-only."})
            return
        keystone_run_id = ks["run_id"]
        request.replay_of = keystone_run_id          # its capture, pose, and frozen text
        request.documentary_prompt_override = None   # a print never edits the art bible
    elif mode == "KEYSTONE" and not request.replay_of:
        yield format_ndjson({"type": "ERROR", "message": "Pick a source run to make a keystone from."})
        return

    # Replay: load the frozen negative (seed capture + domain text) before anything else.
    replay = None
    if request.replay_of:
        try:
            replay = load_replay_source(request.replay_of)
        except Exception as e:
            detail = getattr(e, "detail", None) or str(e)
            print(f"[Replay] could not load source {request.replay_of}: {detail}")
            yield format_ndjson({"type": "ERROR", "message": f"Replay source unavailable: {detail}"})
            return
        src_tel = replay["meta"].get("telemetry") or {}
        src_set = replay["meta"].get("settings") or {}
        # The camera pose always comes from the source run; only date, time, weather and lighting are new.
        pose = {k: src_tel[k] for k in (
            "latitude", "longitude", "altitude_agl", "heading", "pitch", "fov", "tile_mode",
            "target_latitude", "target_longitude"
        ) if src_tel.get(k) is not None}
        for k in ("target_distance_m", "target_method", "ground_elevation_m", "altitude_method"):
            v = src_tel.get(k) if src_tel.get(k) is not None else src_set.get(k)
            if v is not None:
                pose[k] = v
        telemetry = telemetry.model_copy(update=pose) if hasattr(telemetry, "model_copy") else telemetry.copy(update=pose)
        request.screenshot_b64 = replay["screenshot_b64"]
        if not request.saved_view_id:
            request.saved_view_id = src_set.get("saved_view_id")
            request.saved_view_name = src_set.get("saved_view_name")
        replay["source_date"] = src_set.get("date")

        if mode in ("KEYSTONE", "PRINT", "DATE_PLATE") and not (replay["domain"].metadata or {}).get("invariant_split"):
            yield format_ndjson({"type": "ERROR", "message": "Keystones need a run made after the phenology split."})
            return
        if mode == "KEYSTONE":
            if not request.saved_view_id:
                yield format_ndjson({"type": "ERROR", "message": "Keystones need a run tagged with a saved view (capture after using GO)."})
                return
            # The neutral master plate: bare deciduous trees, flat dry overcast, noon.
            neutral = {
                "date": _midwinter_date(telemetry.latitude),
                "time_of_day": 12.0,
                "timestamp_utc": None,
                "lighting_mode": "SOLAR",
                "weather_mode": "OVERCAST",
            }
            telemetry = telemetry.model_copy(update=neutral) if hasattr(telemetry, "model_copy") else telemetry.copy(update=neutral)
            print(f"[Keystone] neutral plate: {neutral['date']} 12:00 OVERCAST")
            replay["delighted_b64"] = None   # re-delight the source capture at the keystone setting
        if print_like:
            plate = _file_data_url(_run_dir(keystone_run_id) / "spatial_twin.png", "image/png")
            if not plate:
                yield format_ndjson({"type": "ERROR", "message": f"Keystone run {keystone_run_id} has no rendered plate."})
                return
            replay["delighted_b64"] = plate   # the synthesis seed is the approved plate itself
            print(f"[Print] seed is keystone plate from {keystone_run_id}")
        if mode == "DATE_PLATE":
            # Layer 2: the keystone with this date's canopy, under the keystone's own neutral light.
            if not telemetry.date:
                yield format_ndjson({"type": "ERROR", "message": "A date plate needs a set date (not the live clock)."})
                return
            neutral = {"time_of_day": 12.0, "timestamp_utc": None, "lighting_mode": "SOLAR", "weather_mode": "OVERCAST"}
            telemetry = telemetry.model_copy(update=neutral) if hasattr(telemetry, "model_copy") else telemetry.copy(update=neutral)
            print_variant = "season"
            print(f"[DatePlate] {request.print_view_id} {telemetry.date}: canopy only, 12:00 OVERCAST")
        elif mode == "PRINT" and telemetry.date:
            # Layer 3: an hour print starts from this date's plate, if one exists, and changes only the light.
            date_plate_run_id = _date_plate_for(request.print_view_id, keystone_run_id, telemetry.date)
            dp = _file_data_url(_run_dir(date_plate_run_id) / "spatial_twin.png", "image/png") if date_plate_run_id else None
            if dp:
                replay["delighted_b64"] = dp
                print_variant = "light"
                print(f"[Print] seed is the date plate {date_plate_run_id} for {telemetry.date}: light only")
            else:
                date_plate_run_id = None
                print(f"[Print] no date plate for {telemetry.date}: canopy and light in one print (original behaviour)")
        print(
            f"[Replay] source {request.replay_of} | domain from {replay['domain_source']} | "
            f"delighted seed {'reused' if replay['delighted_b64'] else 'will be recomputed'}"
        )

    # Subject resolution: geocode what is framed, not where the camera hovers.
    has_target = telemetry.target_latitude is not None and telemetry.target_longitude is not None
    if has_target:
        subj_lat, subj_lon = telemetry.target_latitude, telemetry.target_longitude
        address_source = "TARGET"
    else:
        subj_lat, subj_lon = telemetry.latitude, telemetry.longitude
        address_source = "CAMERA"
    target_desc = (
        f"({subj_lat:.5f}, {subj_lon:.5f}) via {telemetry.target_method}, {telemetry.target_distance_m or 0:.0f} m"
        if has_target else "none (using camera position)"
    )

    emit_terminal_banner(
        (f"{mode} " if mode else "") +
        (f"REPLAY of {request.replay_of} | " if replay else "") +
        f"Camera: ({telemetry.latitude:.5f}, {telemetry.longitude:.5f}) | Target: {target_desc} | "
        f"Date: {telemetry.date or 'Live'} | Scope: {request.view_scope}"
    )

    try:
        # 1. Address Resolution & Ephemeris
        stage, event_str = stage_activate(PipelineStage.INGEST_LIGHTING, f"Target: {target_desc}")
        yield event_str

        if replay:
            address = replay["domain"].address
            address_source = "REPLAY"
        else:
            address = request.address or reverse_geocode(subj_lat, subj_lon, google_maps_key)
            if request.address:
                address_source = "SUPPLIED"
        print(f"[Subject] address source: {address_source} -> {address}")
        yield stage.processing(f"Resolved Address ({address_source}): {address} | Calculating NOAA Solar Math...")

        lighting_state = resolve_lighting_state(
            lat=telemetry.latitude,
            lon=telemetry.longitude,
            camera_heading=telemetry.heading,
            camera_pitch=telemetry.pitch,
            date_str=telemetry.date,
            time_of_day_hours=telemetry.time_of_day,
            timestamp_utc=telemetry.timestamp_utc,
            mode=telemetry.lighting_mode,
            weather_mode=telemetry.weather_mode
        )
        yield stage.dispatching(f"Weather: {lighting_state.weather_mode} | Mode: {lighting_state.mode}")
        yield stage.finish(f"Solar Ephemeris & Lighting state resolved for {address}")

        # 2. Domain Engine (4 Mothers with Temporal Epoch Grounding)
        stage, event_str = stage_activate(PipelineStage.DOMAIN_ENGINE, f"Target: {address} [Date: {telemetry.date or 'Present'}]")
        yield event_str

        if replay:
            domain_result = replay["domain"]
            override = (request.documentary_prompt_override or "").strip()
            if override and override != domain_result.documentary_prompt.strip():
                domain_result.documentary_prompt = override
                scene_edited = True
            # The LSA pass (2026-10-15): its species go into the ecology record too, so a series ages the trees the text names.
            if request.lsa_join and scene_edited and not print_like:
                lj = request.lsa_join
                eco = str(lj.get("ecology") or "").strip()
                if eco:
                    domain_result.botanical_ecology = eco
                lsa_join_record = {k: lj.get(k) for k in ("run_id", "label", "instruction", "added_structure", "removed",
                                                          "species_to_verify", "set_aside", "not_added",
                                                          "hand_edited_after", "director_layout_used")}
                lsa_join_record["ecology_replaced"] = bool(eco)
                print(f"[LSA] scene text from the LSA pass of {lj.get('run_id')}"
                      f"{' (hand-edited after)' if lj.get('hand_edited_after') else ''}"
                      f"{'; ecology record replaced' if eco else ''}; species to verify: {lj.get('species_to_verify') or 'none'}")
                yield stage.dispatching(f"LSA pass from {lj.get('label') or lj.get('run_id')}")
            src_date = replay.get("source_date")
            pheno_note = ""
            is_split = bool((domain_result.metadata or {}).get("invariant_split"))
            if not is_split and telemetry.date and src_date and telemetry.date[:7] != str(src_date)[:7]:
                pheno_note = f" | NOTE: pre-split run, phenology text is frozen from source date {src_date}"
            yield stage.processing(
                f"Frozen domain text loaded from {request.replay_of} ({replay['domain_source']})"
                f"{' | scene text EDITED' if scene_edited else ''}{pheno_note}"
            )
            print(f"[Replay] scene text {'EDITED by user' if scene_edited else 'unchanged'}{pheno_note}")
            yield stage.dispatching(f"Documentary prompt frozen ({len(domain_result.documentary_prompt)} chars)")
            domain_finish_msg = "Domain text frozen (replay: no LSA call)"
        else:
            yield stage.processing(
                "Executing domain stack (Geology, Geography, Architecture, Civil Records, Botanical Phenology) | "
                f"Search grounding: {'ON' if request.use_search_grounding else 'OFF'}..."
            )
            scope = ViewScope(request.view_scope.upper()) if request.view_scope in ViewScope.__members__ else ViewScope.FRUSTUM

            domain_result = analyze_spatial_domain(
                address=address,
                coordinates=(subj_lat, subj_lon),
                view_scope=scope,
                telemetry=telemetry,
                screenshot_b64=request.screenshot_b64,
                temporal_epoch=telemetry.date,
                gemini_api_key=gemini_key,
                use_search_grounding=request.use_search_grounding
            )
            yield stage.dispatching(f"Documentary prompt synthesized ({len(domain_result.documentary_prompt)} chars)")
            domain_finish_msg = (
                "Domain analysis complete (search grounding ON)" if request.use_search_grounding
                else "Domain analysis complete (search grounding OFF)"
            )

        # 2.5 Phenology: the variant layer for THIS frame's date (split runs only)
        if (domain_result.metadata or {}).get("invariant_split"):
            if telemetry.date:
                phenology_date = telemetry.date
            elif telemetry.timestamp_utc:
                phenology_date = str(telemetry.timestamp_utc)[:10]
            else:
                phenology_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            src_date = replay.get("source_date") if replay else None
            if replay and domain_result.phenology and src_date == phenology_date:
                phenology_source = "source-run"
            else:
                domain_result.phenology, phenology_source = generate_phenology(
                    ecology_text=domain_result.botanical_ecology,
                    address=address,
                    lat=subj_lat,
                    lon=subj_lon,
                    date_str=phenology_date,
                    gemini_api_key=gemini_key,
                )
            print(f"[Phenology] {phenology_date}: {phenology_source} | {domain_result.phenology[:100]}")
            if phenology_source == "failed":
                print("[Phenology] WARNING: no seasonal state for this frame; trees fall back to time-invariant description only")
                yield stage.dispatching(f"WARNING: phenology for {phenology_date} failed; trees use time-invariant text only")
            else:
                yield stage.dispatching(f"Phenology for {phenology_date}: {phenology_source}")
        else:
            phenology_source = "pre-split"
            yield stage.dispatching("Pre-split run: seasonal state is embedded in the frozen text")
        yield stage.finish(domain_finish_msg)


        # 3. Spatial Scaffold Engine
        stage, event_str = stage_activate(PipelineStage.SPATIAL_SCAFFOLD, "Constructing RFC 7946 7-Strata GeoJSON")
        yield event_str

        yield stage.processing("Compiling subterranean, architectural, and ephemeris layers...")
        scaffold = build_spatial_scaffold(
            address=address,
            telemetry=telemetry,
            domain_result=domain_result,
            lighting_state=lighting_state
        )
        yield stage.dispatching("7 Strata FeatureCollection ready")
        yield stage.finish("Spatial Scaffold built successfully")

        # 4. Prompt Compiler
        stage, event_str = stage_activate(PipelineStage.PROMPT_ENGINE, f"Target Provider: {request.provider}")
        yield event_str

        yield stage.processing("Compiling System Contracts, Botanical Phenology, and Lithics...")
        # B10 (2026-10-22): the view's points of interest open the scene section, most important first. The run's own
        # scene text is not changed (a copy carries the block), so replays never add it twice.
        compile_domain = domain_result
        poi_record = None
        if request.saved_view_id and not print_like:
            _view = next((v for v in _load_views() if v.get("id") == request.saved_view_id), None)
            _block, poi_record = poi_block(_view)
            if _block:
                compile_domain = copy.copy(domain_result)
                compile_domain.documentary_prompt = _block + "\n\n" + (domain_result.documentary_prompt or "")
                yield stage.dispatching(f"Points of interest: {len(poi_record)} from the saved view, placed first in the scene section")
        compiled = compile_conditioning(
            domain_result=compile_domain,
            lighting_state=lighting_state,
            target_provider=request.provider,
            telemetry=telemetry,
            target_model=request.target_model,
            gemini_budget=request.gemini_budget,
            print_mode=print_like,
            print_variant=print_variant
        )
        _m = compiled.metadata
        yield stage.dispatching(
            f"Conditioning compiled: {_m.get('final_char_count', 0)} chars "
            f"(budget {_m.get('budget', '-')}"
            f"{' raised from ' + str(_m.get('budget_requested')) + ' to fit the scene text' if _m.get('budget_raised') else ''}"
            f", doc {_m.get('doc_chars', '-')}"
            f"{', TRIMMED: the scene text is longer than the ' + str(_m.get('budget')) + ' ceiling allows' if _m.get('doc_trimmed') or _m.get('eco_trimmed') else ''})"
        )
        yield stage.finish(f"Conditioning compiled for {compiled.target_model}")

        # 5. Vision Preprocessor (CUDA Delighting)
        stage, event_str = stage_activate(PipelineStage.VISION_PREPROCESSOR, "Guided filter albedo extraction")
        yield event_str

        if replay and replay["delighted_b64"]:
            yield stage.processing("Reusing archived delighted seed from the source run...")
            delighted_b64 = replay["delighted_b64"]
            delight_setting = ("date plate" if date_plate_run_id else "keystone plate") if print_like else "reused from source run"
        else:
            gamma = _keystone_delight_setting() if mode == "KEYSTONE" else DEFAULT_DELIGHT_GAMMA
            if gamma == "off":
                yield stage.processing("Keystone: delighting off, seeding with the raw capture...")
                delighted_b64 = request.screenshot_b64
                delight_setting = "off (raw capture)"
            else:
                yield stage.processing(f"Pushing viewport frame to PyTorch CUDA -> Delighting (gamma {gamma})...")
                delighted_b64 = delight_image(request.screenshot_b64, gamma=gamma) if request.screenshot_b64 else None
                delight_setting = f"gamma {gamma}"
        print(f"[Delight] {delight_setting}")
        # Sun shadows: fresh captures and prints, only when the client sent a shadow pass and the frame has direct sun.
        # A print's seed is the keystone plate; the pair comes from the client rendering the saved view at the print's time.
        sun_shadows_info = None
        shadow_base = request.shadow_base_b64 or (None if replay else request.screenshot_b64)
        if request.shadow_pass_b64 and shadow_base and delighted_b64 and (not replay or print_like):
            if not _direct_sun(lighting_state):
                sun_shadows_info = {"applied": False, "reason": f"no direct sun in this frame ({lighting_state.weather_mode}), so no cast shadows"}
            else:
                shadowed, sun_shadows_info = _apply_sun_shadows(delighted_b64, shadow_base, request.shadow_pass_b64)
                if shadowed and sun_shadows_info.get("applied"):
                    seed_for_archive = delighted_b64      # replays at other times need the shadow-free seed
                    delighted_b64 = shadowed
                    if print_like:
                        replay["delighted_b64"] = shadowed   # a canopy composite then pastes back the shadowed plate
                    _keep_shadows_in_prompt(compiled)
            print(f"[SunShadows] {'applied' if sun_shadows_info.get('applied') else 'skipped'}: {sun_shadows_info.get('reason')}"
                  + (f" | {sun_shadows_info['coverage']:.1%} of the frame in shadow" if 'coverage' in sun_shadows_info else ""))
            yield stage.dispatching(f"Sun shadows {'laid onto the seed' if sun_shadows_info.get('applied') else 'skipped'}: {sun_shadows_info.get('reason')}")
        yield stage.dispatching("Edge-preserved albedo tensor extracted")
        yield stage.finish("Albedo delighting complete")

        # 6. Synthesis Engine
        stage, event_str = stage_activate(PipelineStage.SYNTHESIS_ENGINE, f"Model: {compiled.target_provider} / {compiled.target_model}")
        yield event_str

        marble_mode = request.marble_input_mode
        marble_seed = None
        if compiled.target_provider == "WORLD_LABS":
            if marble_mode == "pano" and request.pano_b64:
                marble_seed = request.pano_b64
            elif marble_mode == "image":
                marble_seed = delighted_b64
            else:
                marble_mode = "text"
            yield stage.processing(f"Generating 3D world via Marble (input: {marble_mode})...")
        else:
            yield stage.processing(f"Generating 2560x1440 2K QHD visual twin via {compiled.target_provider}...")
        # Street View reference (keystones only): a second image for form and weathering.
        if mode == "KEYSTONE" and request.streetview and compiled.target_provider == "GEMINI":
            sv = request.streetview
            streetview_record = {k: sv.get(k) for k in ("pano_id", "heading", "pitch", "fov", "date", "distance_m", "copyright", "source_url", "lat", "lon")}
            streetview_record["size"] = SV_SIZE   # records made before 16:9 have no size: they were 640x640
            want_detail = (sv.get("reference") or "detail") == "detail"
            try:
                heading, pitch, fov = sv.get("heading", 0), sv.get("pitch", SV_DEFAULT_PITCH), sv.get("fov", SV_DEFAULT_FOV)
                streetview_record["reference"] = "full"
                if want_detail:
                    s_lat = sv.get("subject_lat") if sv.get("subject_lat") is not None else telemetry.target_latitude
                    s_lon = sv.get("subject_lon") if sv.get("subject_lon") is not None else telemetry.target_longitude
                    if s_lat is not None and s_lon is not None:
                        aim = _detail_aim(sv["pano_id"], s_lat, s_lon)
                        heading, fov = aim["heading"], aim["fov"]
                        streetview_record.update(reference="detail", detail_heading=heading, detail_fov=fov, detail_pitch=pitch)
                    else:
                        streetview_record["reference_note"] = "detail crop asked for, but the run has no subject point: full view sent"
                pano = _fetch_pano(sv["pano_id"], heading, pitch, fov)
                streetview_b64 = "data:image/jpeg;base64," + base64.b64encode(pano).decode("ascii")
                text = STREETVIEW_DETAIL_TEXT if streetview_record["reference"] == "detail" else STREETVIEW_REFERENCE_TEXT
                compiled.prompt += text.format(date=sv.get("date") or "recently")
                streetview_record["used"] = True
                print(f"[StreetView] keystone reference: pano {sv['pano_id']} ({sv.get('date')}), {streetview_record['reference']}, "
                      f"heading {heading}, pitch {pitch}, fov {fov}")
                yield stage.dispatching(f"Street View reference attached ({'detail crop' if streetview_record['reference'] == 'detail' else 'full view'}): "
                                        f"pano {sv.get('date') or ''} (not stored)")
            except Exception as e:
                streetview_record["used"] = False
                streetview_record["error"] = str(getattr(e, "detail", e))
                print(f"[StreetView] reference skipped: {streetview_record['error']}")
                yield stage.dispatching("Street View reference could not be fetched; rendering without it")
        # Direct handoff of CompiledPrompt enables systemInstruction / user_prompt separation
        synthesis = synthesize_twin(
            prompt=compiled,
            provider=compiled.target_provider,
            model_name=compiled.target_model,
            screenshot_b64=(marble_seed if compiled.target_provider == "WORLD_LABS" else delighted_b64),
            marble_input_mode=marble_mode if compiled.target_provider == "WORLD_LABS" else "text",
            display_name=address[:64],
            multi_view_images=request.multi_view_images,
            disable_recaption=request.disable_recaption,
            gemini_api_key=gemini_key,
            world_labs_api_key=world_labs_key,
            seed=run_seed,
            reference_b64=streetview_b64
        )
        print(f"[Synthesis] seed {run_seed}{' (fixed)' if request.seed is not None else ' (random)'}")
        yield stage.dispatching(f"Twin artifact received (seed {run_seed})")
        # 6.5 Canopy composite (prints only): everything outside the changed canopy comes from the keystone,
        # so buildings and windows can't shimmy. Only when the print's light matches the keystone's.
        if print_like and synthesis.image_b64:
            ks_rec = next((k for k in _load_keystones().values() if k.get("run_id") == keystone_run_id), {}) or {}
            ks_weather = ((ks_rec.get("conditions") or {}).get("weather")
                          or ((replay["meta"].get("lighting_resolved") or {}).get("weather"))
                          or (replay["meta"].get("settings") or {}).get("weather_mode") or "").upper()
            print_weather = (getattr(lighting_state, "weather_mode", None) or telemetry.weather_mode or "").upper()
            if not request.composite:
                composite_info = {"applied": False, "reason": "turned off for this print"}
            elif print_weather != ks_weather:
                composite_info = {"applied": False, "reason": f"print weather {print_weather} differs from keystone weather {ks_weather}"}
            else:
                comp_b64, canopy_mask_b64, composite_info = composite_canopy(replay["delighted_b64"], synthesis.image_b64)
                if comp_b64:
                    raw_render_b64 = synthesis.image_b64
                    synthesis.image_b64 = comp_b64
            print(f"[Composite] {'applied' if composite_info.get('applied') else 'skipped'}: {composite_info.get('reason')}"
                  + (f" | canopy {composite_info['mask_coverage']:.0%}, structure change {composite_info['structure_change']:.0%}"
                     if 'mask_coverage' in composite_info and 'structure_change' in composite_info else ""))
            yield stage.dispatching(
                f"Canopy composite {'applied' if composite_info.get('applied') else 'skipped'}: {composite_info.get('reason')}")
        yield stage.finish("Visual twin generated")

        total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0

        # 7. Archiver & Persistence
        stage, event_str = stage_activate(PipelineStage.ARCHIVER, "Persisting digital twin artifact bundle")
        yield event_str

        yield stage.processing("Writing raw images, scrubbed tensors, GeoJSON, and markdown dossier...")
        try:
            run_folder_path = archive_run(
                telemetry=telemetry,
                domain_result=domain_result,
                scaffold=scaffold,
                conditioning=compiled,
                synthesis_result=synthesis,
                screenshot_b64=request.screenshot_b64,
                delighted_b64=None if print_like else (seed_for_archive or delighted_b64),  # a print's seed is the keystone plate, recorded by id; sun-shadowed seeds archive shadow-free
                pano_b64=request.pano_b64,
                lighting_state=lighting_state,
                request_settings={
                    "provider": request.provider,
                    "view_scope": request.view_scope,
                    "gemini_budget": request.gemini_budget,
                    "marble_input_mode": marble_mode if compiled.target_provider == "WORLD_LABS" else None,
                    "disable_recaption": request.disable_recaption,
                    "target_model_requested": request.target_model,
                    "use_search_grounding": request.use_search_grounding,
                    "address_source": address_source,
                    "saved_view_id": request.saved_view_id,
                    "saved_view_name": request.saved_view_name,
                    "replay_of": request.replay_of,
                    "scene_text_edited": scene_edited,
                    "seed": run_seed,
                    "seed_fixed": request.seed is not None,
                    "composite": composite_info,
                    "sun_shadows": {k: v for k, v in (sun_shadows_info or {}).items() if k != "mask_png_b64"} or None,
                    "streetview": streetview_record,
                    "lsa_join": lsa_join_record,
                    "points_of_interest": poi_record,
                    "ab": request.ab,
                    "delight": delight_setting,
                    "mode": mode,
                    "keystone_candidate": mode == "KEYSTONE",
                    "keystone_print_of": request.print_view_id if mode == "PRINT" else None,
                    "date_plate_of": request.print_view_id if mode == "DATE_PLATE" else None,
                    "date_plate_run": date_plate_run_id,
                    "print_variant": print_variant if print_like else None,
                    "keystone_run": keystone_run_id,
                    "series_id": request.series_id,
                    "series_frame": request.series_frame,
                    "phenology_date": phenology_date,
                    "phenology_source": phenology_source,
                    "target_method": telemetry.target_method,
                    "target_distance_m": telemetry.target_distance_m,
                    "pano_seed_supplied": bool(request.pano_b64),
                    "screenshot_supplied": bool(request.screenshot_b64)
                }
            )
            if sun_shadows_info and sun_shadows_info.get("mask_png_b64"):
                try:
                    (Path(run_folder_path) / "sun_shadow_mask.png").write_bytes(base64.b64decode(sun_shadows_info["mask_png_b64"]))
                except Exception as e:
                    print(f"[SunShadows] could not write the mask: {e}")
            # Keep the untouched render and the canopy mask beside the composite, for inspection.
            if raw_render_b64 or canopy_mask_b64:
                for fname, data in (("spatial_twin_raw.png", raw_render_b64), ("canopy_mask.png", canopy_mask_b64)):
                    if data:
                        try:
                            (Path(run_folder_path) / fname).write_bytes(base64.b64decode(data.split(",", 1)[1]))
                        except Exception as e:
                            print(f"[Composite] could not write {fname}: {e}")
            if mode == "DATE_PLATE" and synthesis.image_b64:
                try:
                    _register_date_plate(request.print_view_id, keystone_run_id, telemetry.date, Path(run_folder_path).name)
                except Exception as e:
                    print(f"[DatePlate] could not register: {e}")
            run_record = {
                "status": "persisted",
                "path": run_folder_path,
                "total_latency_ms": round(total_latency_ms, 1)
            }
        except Exception as e:
            print(f"[Archiver Warning]: {e}")
            run_record = {"status": "unarchived", "error": str(e)}

        yield stage.dispatching(f"Archived to {run_record.get('path', 'local')}")
        yield stage.finish("Flight recorder closed")

        emit_terminal_complete(total_latency_ms)

        # 8. FINAL RESULT CHUNK
        result_payload = {
            "type": "RESULT",
            "data": {
                "status": "success",
                "provider": synthesis.provider.value,
                "model_name": synthesis.model_name,
                "address": address,
                "view_scope": domain_result.view_scope.value,
                "documentary_prompt": domain_result.documentary_prompt,
                "compiled_prompt": compiled.prompt,
                "system_instruction": compiled.system_instruction,
                "user_prompt": compiled.user_prompt,
                "twin_image_b64": synthesis.image_b64,
                "world_id": synthesis.world_id,
                "world_viewer_url": synthesis.world_viewer_url,
                "marble_input_mode": marble_mode if compiled.target_provider == "WORLD_LABS" else None,
                "splat_url": synthesis.splat_url,
                "collider_mesh_url": synthesis.collider_mesh_url,
                "pano_url": synthesis.pano_url,
                "geojson": scaffold.to_geojson(),
                "latency_ms": round(total_latency_ms, 1),
                "replay_of": request.replay_of,
                "mode": mode,   # A10 (2026-10-21): the page captions the frame by what this run is
                "run_record": run_record
            }
        }
        yield format_ndjson(result_payload)

    except Exception as e:
        print("\n[Pipeline Fault Occurred]:")
        traceback.print_exc()
        error_payload = {
            "type": "ERROR",
            "message": str(e)
        }
        yield format_ndjson(error_payload)


# -------------------------------------------------------------------------
# Saved Camera Views (/api/views)
# Stored server-side as JSON beside server.py so views survive browser cache
# clears and can be committed to git alongside the code.
# -------------------------------------------------------------------------
SAVED_VIEWS_PATH = Path(__file__).parent / "saved_views.json"


class SavedCamera(BaseModel):
    # Exact ECEF position: restores the pose bit-for-bit.
    x: float
    y: float
    z: float
    # Human-readable copy of the same position (not used for restore).
    latitude: float
    longitude: float
    height_m: float = Field(..., description="Ellipsoid height (m)")
    heading_deg: float
    pitch_deg: float
    roll_deg: float = 0.0
    fov_deg: float
    capture_w: Optional[int] = None
    capture_h: Optional[int] = None


class SaveViewRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    camera: SavedCamera
    note: Optional[str] = Field(None, max_length=500)
    overwrite: bool = False
    subject: Optional[dict] = Field(None, description="The point the view is about: ECEF x/y/z plus lat/lon/height, set by clicking in the viewer")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "view"


def _load_views() -> list:
    if not SAVED_VIEWS_PATH.exists():
        return []
    try:
        data = json.loads(SAVED_VIEWS_PATH.read_text(encoding="utf-8"))
        return data.get("views", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"[Views] could not read {SAVED_VIEWS_PATH}: {e}")
        raise HTTPException(status_code=500, detail=f"saved_views.json is unreadable: {e}")


def _write_views(views: list) -> None:
    tmp = SAVED_VIEWS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"version": 1, "views": views}, indent=2), encoding="utf-8")
    tmp.replace(SAVED_VIEWS_PATH)  # atomic swap: a crash never leaves a half-written file


@app.get("/api/views")
async def list_views():
    return {"views": sorted(_load_views(), key=lambda v: v.get("name", "").lower())}


@app.post("/api/views")
async def save_view(req: SaveViewRequest):
    views = _load_views()
    view_id = _slug(req.name)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    existing = next((v for v in views if v.get("id") == view_id), None)
    if existing and not req.overwrite:
        raise HTTPException(status_code=409, detail=f"A view named '{existing.get('name')}' already exists.")
    record = {
        "id": view_id,
        "name": req.name.strip(),
        "note": req.note,
        "camera": req.camera.model_dump() if hasattr(req.camera, "model_dump") else req.camera.dict(),
        "subject": req.subject,
        "points": (existing or {}).get("points") or [],
        "created_utc": existing.get("created_utc", now) if existing else now,
        "updated_utc": now,
    }
    views = [v for v in views if v.get("id") != view_id] + [record]
    _write_views(views)
    print(f"[Views] {'updated' if existing else 'saved'}: {record['name']} ({view_id})")
    return record


@app.delete("/api/views/{view_id}")
async def delete_view(view_id: str):
    views = _load_views()
    kept = [v for v in views if v.get("id") != view_id]
    if len(kept) == len(views):
        raise HTTPException(status_code=404, detail="View not found.")
    _write_views(kept)
    print(f"[Views] deleted: {view_id}")
    return {"deleted": view_id}


# -------------------------------------------------------------------------
# Points of interest (B10, 2026-10-22): up to five ranked points per saved view, each with the director's own
# description. The prompt compiler opens the scene section with them, most important first, each placed by where
# it sits in the frame. Ranks and labels stay in the UI: the model sees only the order and the descriptions.
# -------------------------------------------------------------------------
MAX_POINTS = 5


class PointOfInterest(BaseModel):
    id: str = Field(..., min_length=1, max_length=40)
    label: str = Field("", max_length=60, description="The director's own name for it; shown in the UI only")
    description: str = Field("", max_length=600, description="What the image model reads")
    x: float
    y: float
    z: float
    latitude: float
    longitude: float
    height_m: float
    nx: Optional[float] = None   # which way the clicked surface faces (ECEF unit vector), when the viewer could tell
    ny: Optional[float] = None
    nz: Optional[float] = None


class SavePointsRequest(BaseModel):
    points: List[PointOfInterest] = Field(default_factory=list)


def _frame_position(cam: dict, p: dict) -> dict:
    """Where a point sits in the saved view's frame: x and y from -1 to 1 (left/bottom to right/top) and distance."""
    dx, dy, dz = p["x"] - cam["x"], p["y"] - cam["y"], p["z"] - cam["z"]
    lat, lon = math.radians(cam["latitude"]), math.radians(cam["longitude"])
    east = -math.sin(lon) * dx + math.cos(lon) * dy
    north = -math.sin(lat) * math.cos(lon) * dx - math.sin(lat) * math.sin(lon) * dy + math.cos(lat) * dz
    up = math.cos(lat) * math.cos(lon) * dx + math.cos(lat) * math.sin(lon) * dy + math.sin(lat) * dz
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    az = math.degrees(math.atan2(east, north))
    rel = (az - cam.get("heading_deg", 0.0) + 540.0) % 360.0 - 180.0
    elev = math.degrees(math.atan2(up, math.hypot(east, north))) - cam.get("pitch_deg", 0.0)
    hfov = math.radians(cam.get("fov_deg") or 60.0)          # Cesium's fov spans the wider side (the width at 16:9)
    aspect = (cam.get("capture_w") or 16) / (cam.get("capture_h") or 9)
    vfov = 2 * math.atan(math.tan(hfov / 2) / aspect)
    x = math.tan(math.radians(rel)) / math.tan(hfov / 2) if abs(rel) < 89 else (9.0 if rel > 0 else -9.0)
    y = math.tan(math.radians(elev)) / math.tan(vfov / 2)
    out = {"x": round(x, 3), "y": round(y, 3), "distance_m": round(dist, 1)}
    # 2026-10-22: which way the surface faces relative to the camera, so two faces of one corner building are never
    # confused (the model takes the face it sees head-on for the front).
    if all(isinstance(p.get(k), (int, float)) for k in ("nx", "ny", "nz")):
        n_e = -math.sin(lon) * p["nx"] + math.cos(lon) * p["ny"]
        n_n = -math.sin(lat) * math.cos(lon) * p["nx"] - math.sin(lat) * math.sin(lon) * p["ny"] + math.cos(lat) * p["nz"]
        n_u = math.cos(lat) * math.cos(lon) * p["nx"] + math.cos(lat) * math.sin(lon) * p["ny"] + math.sin(lat) * p["nz"]
        if abs(n_u) > 0.8:
            out["facing"] = "on a level surface"
        else:
            n_rel = (math.degrees(math.atan2(n_e, n_n)) - cam.get("heading_deg", 0.0) + 540.0) % 360.0 - 180.0
            out["facing"] = ("on a face turned toward the camera" if abs(n_rel) >= 135 else
                             "on a face running away from the camera, facing left" if n_rel <= -45 else
                             "on a face running away from the camera, facing right" if n_rel >= 45 else
                             "on a face turned away from the camera")
    return out


def _position_words(pos: dict) -> str:
    x, y, d = pos["x"], pos["y"], pos["distance_m"]
    if x < -1:
        side = "just outside the frame on the left"
    elif x > 1:
        side = "just outside the frame on the right"
    else:
        side = ("at the far left" if x < -0.6 else "on the left" if x < -0.2 else "in the centre" if x <= 0.2
                else "on the right" if x <= 0.6 else "at the far right")
    height = "high in the frame" if y > 0.4 else "low in the frame" if y < -0.4 else "at mid height"
    dist = "close to the camera" if d < 20 else "in the middle distance" if d < 60 else "in the distance"
    return f"{side}, {height}, {dist}" + (f", {pos['facing']}" if pos.get("facing") else "")


def poi_block(view: Optional[dict]):
    """The priority block for a saved view's points, and a record of what was sent. ("", None) when there are none."""
    if not view or not view.get("camera"):
        return "", None
    pts = [p for p in (view.get("points") or []) if (p.get("description") or "").strip()]
    if not pts:
        return "", None
    lines, record = [], []
    for rank, p in enumerate(pts[:MAX_POINTS], start=1):
        pos = _frame_position(view["camera"], p)
        words = _position_words(pos)
        desc = re.sub(r"\s+", " ", p["description"]).strip().rstrip(".")
        lines.append(f"- {words[0].upper() + words[1:]}: {desc}.")
        record.append({"rank": rank, "id": p.get("id"), "label": p.get("label", ""), "position": words, "frame": pos,
                       "description": desc})
    block = ("[POINTS OF INTEREST, most important first. Render each exactly as described; where the scene text below "
             "says otherwise about the same element, these entries are correct.]\n" + "\n".join(lines))
    return block, record


@app.put("/api/views/{view_id}/points")
async def save_view_points(view_id: str, req: SavePointsRequest):
    if len(req.points) > MAX_POINTS:
        raise HTTPException(status_code=400, detail=f"A view holds at most {MAX_POINTS} points of interest.")
    views = _load_views()
    view = next((v for v in views if v.get("id") == view_id), None)
    if not view:
        raise HTTPException(status_code=404, detail="View not found.")
    view["points"] = [p.model_dump() if hasattr(p, "model_dump") else p.dict() for p in req.points]
    view["updated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write_views(views)
    block, record = poi_block(view)
    print(f"[Views] points of interest for {view_id}: {len(view['points'])}")
    return {"view": view, "block": block, "points": record or []}


@app.get("/api/views/{view_id}/points/preview")
async def preview_view_points(view_id: str):
    view = next((v for v in _load_views() if v.get("id") == view_id), None)
    if not view:
        raise HTTPException(status_code=404, detail="View not found.")
    block, record = poi_block(view)
    return {"block": block, "points": record or []}


# -------------------------------------------------------------------------
# Archived Runs (/api/runs): list, scene text, and preview images for replay
# -------------------------------------------------------------------------
_RUN_STAMP_RE = re.compile(r"(\d{8})_(\d{6})")


def _run_created(d: Path, meta: dict) -> str:
    """When the run was made, as local ISO time, whatever format the archive used.
    Tries the metadata timestamp (compact or ISO), then a YYYYMMDD_HHMMSS stamp in the folder
    name, then the metadata file's modified time. Sorting on this keeps the list in true order."""
    ts = str(meta.get("timestamp") or "").strip()
    for text, fmt in ((ts[:15], "%Y%m%d_%H%M%S"), (ts[:19], "%Y-%m-%dT%H:%M:%S"), (ts[:19], "%Y-%m-%d %H:%M:%S")):
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            pass
    m = _RUN_STAMP_RE.search(d.name)
    if m:
        try:
            return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").isoformat(timespec="seconds")
        except ValueError:
            pass
    f = d / "run_metadata.json"
    return datetime.fromtimestamp((f if f.exists() else d).stat().st_mtime).isoformat(timespec="seconds")


def _run_summary(d: Path) -> dict:
    meta = _read_json(d / "run_metadata.json") or {}
    settings = meta.get("settings") or {}
    tel = meta.get("telemetry") or {}
    has_seed = (d / "viewport_capture.jpg").exists()
    has_domain = (d / "domain_result.json").exists() or (d / "domain_analysis.md").exists()
    return {
        "id": d.name,
        "timestamp": meta.get("timestamp") or "",
        "created": _run_created(d, meta),
        "address": meta.get("address"),
        "saved_view_id": settings.get("saved_view_id"),
        "saved_view_name": settings.get("saved_view_name"),
        "replay_of": settings.get("replay_of"),
        "scene_text_edited": settings.get("scene_text_edited"),
        "keystone_candidate": bool(settings.get("keystone_candidate")) or settings.get("mode") == "KEYSTONE",
        "keystone_print_of": settings.get("keystone_print_of"),
        "mode": settings.get("mode"),
        "date_plate_of": settings.get("date_plate_of"),
        "date_plate_run": settings.get("date_plate_run"),
        "series_id": settings.get("series_id"),
        "series_frame": settings.get("series_frame"),
        "seed": settings.get("seed"),
        "composite_applied": bool((settings.get("composite") or {}).get("applied")),
        "streetview": settings.get("streetview"),   # keystones: the pano reference used (ID and angles only)
        "lsa_run": (settings.get("lsa_join") or {}).get("run_id"),
        "lsa_label": (settings.get("lsa_join") or {}).get("label"),
        "ab": settings.get("ab"),
        "has_raw": (d / "spatial_twin_raw.png").exists(),
        "alignment": _cached_alignment(d),            # None until measured (GET /api/runs/{id}/alignment)
        "realigned_from": (settings.get("realigned_from") or {}).get("run_id"),
        "date": settings.get("date"),
        "time_of_day": settings.get("time_of_day"),
        "weather_mode": settings.get("weather_mode"),
        "provider": meta.get("provider"),
        "latitude": tel.get("latitude"),
        "longitude": tel.get("longitude"),
        "target_latitude": tel.get("target_latitude"),
        "target_longitude": tel.get("target_longitude"),
        "has_twin": (d / "spatial_twin.png").exists(),
        "split": bool(((_read_json(d / "domain_result.json") or {}).get("metadata") or {}).get("invariant_split")),
        "weather_resolved": (meta.get("lighting_resolved") or {}).get("weather"),
        "replayable": has_seed and has_domain,
    }


@app.get("/api/runs")
async def list_runs(view_id: Optional[str] = None, limit: int = 300):
    if not DEFAULT_RUNS_DIR.exists():
        return {"runs": []}
    runs = [_run_summary(d) for d in DEFAULT_RUNS_DIR.iterdir() if d.is_dir()]
    if view_id:
        runs = [r for r in runs if r["saved_view_id"] == view_id]
    runs.sort(key=lambda r: (r["created"], r["id"]), reverse=True)   # newest first, by when each run was made
    return {"runs": runs[:limit]}


@app.get("/api/date_plate")
async def get_date_plate(view_id: str, date: str):
    """The date plate for a view's current keystone on a date, if one has been made."""
    ks = _load_keystones().get(view_id) or {}
    run_id = _date_plate_for(view_id, ks.get("run_id"), date)
    return {"view_id": view_id, "date": date[:10], "keystone_run": ks.get("run_id"), "run_id": run_id}


@app.get("/api/keystones")
async def list_keystones():
    return {"views": _load_keystones()}


class ApproveKeystoneRequest(BaseModel):
    run_id: str
    warnings_acknowledged: list = Field(default_factory=list, description="Non-neutral conditions the user saw and accepted")


@app.post("/api/keystones")
async def approve_keystone(req: ApproveKeystoneRequest):
    d = _run_dir(req.run_id)
    meta = _read_json(d / "run_metadata.json") or {}
    settings = meta.get("settings") or {}
    # Any good plate can become the keystone; the user judges it. Prints are excluded
    # so a keystone never descends from another keystone.
    if settings.get("keystone_print_of"):
        raise HTTPException(status_code=422, detail="A print cannot become a keystone; approve the run it came from instead.")
    domain_meta = ((_read_json(d / "domain_result.json") or {}).get("metadata") or {})
    if not domain_meta.get("invariant_split"):
        raise HTTPException(status_code=422, detail="Keystones need a run made after the phenology split.")
    view_id = settings.get("saved_view_id")
    if not view_id:
        raise HTTPException(status_code=422, detail="This candidate is not tagged with a saved view.")
    if not (d / "spatial_twin.png").exists():
        raise HTTPException(status_code=422, detail="This candidate has no rendered plate.")
    views = _load_keystones()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prev = views.get(view_id)
    history = list(prev.get("history", [])) if prev else []
    if prev and prev.get("run_id") != req.run_id:
        history.append({"run_id": prev["run_id"], "approved_utc": prev.get("approved_utc"), "replaced_utc": now})
    views[view_id] = {
        "run_id": req.run_id,
        "view_name": settings.get("saved_view_name"),
        "source_run": settings.get("replay_of"),
        "approved_from": "candidate" if settings.get("keystone_candidate") else "run",
        "conditions": {
            "date": settings.get("date"),
            "time_of_day": settings.get("time_of_day"),
            "weather": (meta.get("lighting_resolved") or {}).get("weather") or settings.get("weather_mode"),
        },
        "warnings_acknowledged": req.warnings_acknowledged,
        "approved_utc": now,
        "history": history,
    }
    _write_keystones(views)
    print(f"[Keystone] approved {req.run_id} for view {view_id}" + (f" (replaces {prev['run_id']})" if prev and prev.get('run_id') != req.run_id else ""))
    return views[view_id]


# -------------------------------------------------------------------------
# Series (/api/series): batches of prints (or phenology text) from a view's keystone.
# Jobs run on a server thread, one at a time, so they survive a closed browser tab.
# -------------------------------------------------------------------------
SERIES_DIR = Path(__file__).parent / "spatial_twin_series"
SERIES_HARD_CAP = 400        # refuse anything larger outright
SERIES_CONFIRM_ABOVE = 30    # larger series need an explicit second confirmation
_series_state = {"active_id": None, "last_id": None, "cancel": False}
_series_lock = threading.Lock()


class SeriesRequest(BaseModel):
    view_id: str
    kind: str = Field("prints", description="prints, or phenology (text preview only, no renders)")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    step: str = Field("day", description="day, week, or month")
    dates: Optional[List[str]] = Field(None, description="Explicit dates; overrides start/end/step")
    time_mode: str = Field("fixed", description="fixed or range")
    time_fixed: float = 12.0
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    time_step_hours: float = 1.0
    weather_mode: str = "OVERCAST"
    lighting_mode: str = "SOLAR"
    gemini_budget: int = 4400
    target_model: Optional[str] = "gemini-3.1-flash-image"
    disable_recaption: bool = True
    confirm_large: bool = False
    seed: Optional[int] = Field(None, description="One seed for every frame; blank picks a random one, recorded in the manifest")
    composite: bool = True


def _parse_date(s: str) -> _date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        raise HTTPException(status_code=422, detail=f"Not a date (YYYY-MM-DD): {s}")


def _add_months(d: _date, months: int, anchor_day: int) -> _date:
    y, m = divmod(d.month - 1 + months, 12)
    y, m = d.year + y, m + 1
    return _date(y, m, min(anchor_day, calendar.monthrange(y, m)[1]))   # clamp to month end


def _series_dates(req: SeriesRequest) -> List[str]:
    if req.dates:
        return [_parse_date(x).isoformat() for x in req.dates]
    if not req.start_date or not req.end_date:
        raise HTTPException(status_code=422, detail="Set a start and end date, or pick a preset.")
    start, end = _parse_date(req.start_date), _parse_date(req.end_date)
    if end < start:
        raise HTTPException(status_code=422, detail="End date is before start date.")
    if req.step not in ("day", "week", "month"):
        raise HTTPException(status_code=422, detail="Step must be day, week, or month.")
    out, d, k = [], start, 0
    while d <= end and len(out) <= SERIES_HARD_CAP:
        out.append(d.isoformat())
        k += 1
        if req.step == "day":
            d = start + timedelta(days=k)
        elif req.step == "week":
            d = start + timedelta(weeks=k)
        else:
            d = _add_months(start, k, start.day)   # anchored to the start day: Jan 31 -> Feb 28 -> Mar 31
    return out


def _series_times(req: SeriesRequest) -> List[float]:
    if req.time_mode == "fixed":
        return [round(req.time_fixed, 2)]
    if req.time_start is None or req.time_end is None or req.time_step_hours <= 0:
        raise HTTPException(status_code=422, detail="A time range needs a start, an end, and a positive step.")
    if req.time_end < req.time_start:
        raise HTTPException(status_code=422, detail="End time is before start time.")
    out, t = [], req.time_start
    while t <= req.time_end + 1e-6 and len(out) <= SERIES_HARD_CAP:
        out.append(round(t, 2))
        t += req.time_step_hours
    return out


def _series_frames(req: SeriesRequest) -> List[dict]:
    dates = _series_dates(req)
    if req.kind == "phenology":
        frames = [{"date": d, "time": None} for d in dates]
    else:
        frames = [{"date": d, "time": t} for d in dates for t in _series_times(req)]
    if len(frames) > SERIES_HARD_CAP:
        raise HTTPException(status_code=422, detail=f"That is over {SERIES_HARD_CAP} frames; narrow the range.")
    return frames


def _seconds_per_frame(kind: str) -> float:
    if kind == "phenology":
        return 4.0
    lat = []
    if DEFAULT_RUNS_DIR.exists():
        for d in sorted(DEFAULT_RUNS_DIR.iterdir(), key=lambda p: p.name, reverse=True)[:40]:
            v = (_read_json(d / "run_metadata.json") or {}).get("latency_ms")
            if isinstance(v, (int, float)) and v > 0:
                lat.append(v / 1000.0)
    lat.sort()
    return (lat[len(lat) // 2] * 1.15 + 5) if lat else 60.0


def _manifest_path(series_id: str) -> Path:
    if not RUN_ID_RE.match(series_id or ""):
        raise HTTPException(status_code=400, detail="Invalid series id.")
    return SERIES_DIR / series_id / "manifest.json"


def _load_manifest(series_id: str) -> dict:
    p = _manifest_path(series_id)
    m = _read_json(p)
    if m is None:
        raise HTTPException(status_code=404, detail=f"Series not found: {series_id}")
    return m


def _save_manifest(m: dict) -> None:
    p = _manifest_path(m["id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _consume_pipeline(req) -> tuple:
    """Run one pipeline request to the end; returns (run folder path or None, error or None)."""
    run_path, error = None, None
    async for chunk in execute_pipeline_stream(req):
        try:
            msg = json.loads(chunk)
        except Exception:
            continue
        if msg.get("type") == "RESULT":
            rec = (msg.get("data") or {}).get("run_record") or {}
            if rec.get("path"):
                run_path = rec["path"]
            else:
                error = f"rendered but not archived: {rec.get('error', 'unknown')}"
        elif msg.get("type") == "ERROR":
            error = msg.get("message") or "pipeline error"
    return run_path, error


async def _run_print_frame(m: dict, fr: dict) -> tuple:
    spec = m["spec"]
    # Layer 2 first: if this frame's date has no plate for the current keystone, make it (once per date).
    ks = _load_keystones().get(m["view_id"]) or {}
    if fr.get("date") and ks.get("run_id") and not _date_plate_for(m["view_id"], ks["run_id"], fr["date"]):
        plate_req = ProcessViewRequest(
            telemetry=TelemetryPayload(latitude=0.0, longitude=0.0, date=fr["date"], time_of_day=12.0, timestamp_utc=None,
                                       lighting_mode="SOLAR", weather_mode="OVERCAST"),
            provider="GEMINI", target_model=spec.get("target_model"), gemini_budget=spec.get("gemini_budget", 4400),
            disable_recaption=spec.get("disable_recaption", True), mode="DATE_PLATE", print_view_id=m["view_id"],
            seed=m.get("seed"), composite=spec.get("composite", True),
        )
        _, plate_err = await _consume_pipeline(plate_req)
        if plate_err:
            print(f"[Series] date plate for {fr['date']} failed ({plate_err}); printing canopy and light together")
    req = ProcessViewRequest(
        telemetry=TelemetryPayload(
            latitude=0.0, longitude=0.0,               # replaced by the keystone run's pose
            date=fr["date"], time_of_day=fr["time"], timestamp_utc=None,
            lighting_mode=spec["lighting_mode"], weather_mode=spec["weather_mode"],
        ),
        provider="GEMINI",
        target_model=spec.get("target_model"),
        gemini_budget=spec.get("gemini_budget", 4400),
        disable_recaption=spec.get("disable_recaption", True),
        mode="PRINT",
        print_view_id=m["view_id"],
        series_id=m["id"],
        series_frame=fr["n"],
        seed=m.get("seed"),
        composite=spec.get("composite", True),
    )
    return await _consume_pipeline(req)


def _series_worker(series_id: str, frame_numbers: List[int]) -> None:
    gemini_key = os.getenv("GEMINI_API_KEY")
    m = _load_manifest(series_id)
    m["status"] = "running"
    _save_manifest(m)
    # The keystone's tree description and location drive the phenology calendar for every frame.
    kd = _run_dir(m["keystone_run"])
    ks_domain, _ = load_domain_from_run(kd)
    tel = (_read_json(kd / "run_metadata.json") or {}).get("telemetry") or {}
    ks_lat = tel.get("target_latitude") or tel.get("latitude") or 0.0
    ks_lon = tel.get("target_longitude") or tel.get("longitude") or 0.0
    try:
        cal, cal_src = get_phenology_calendar(ks_domain.botanical_ecology, ks_domain.address, ks_lat, ks_lon, gemini_key)
        m["calendar"], m["calendar_source"] = cal, cal_src
        _save_manifest(m)
        print(f"[Series] phenology calendar: {cal_src}")
    except Exception as e:
        print(f"[Series] phenology calendar unavailable: {e}")
    cancelled = False
    try:
        for n in frame_numbers:
            if _series_state["cancel"]:
                cancelled = True
                break
            fr = m["frames"][n - 1]
            fr.update(status="running", started_utc=_now_utc(), error=None)
            _save_manifest(m)
            print(f"[Series] {series_id} frame {n}/{len(m['frames'])}: {fr['date']} {fr['time'] if fr['time'] is not None else ''}")
            try:
                if m["kind"] == "phenology":
                    text, src = generate_phenology(
                        ecology_text=ks_domain.botanical_ecology, address=ks_domain.address,
                        lat=ks_lat, lon=ks_lon, date_str=fr["date"], gemini_api_key=gemini_key,
                    )
                    fr.update(phenology=text, phenology_source=src, status="failed" if src == "failed" else "done")
                    if src == "failed":
                        fr["error"] = "phenology generation failed"
                else:
                    run_path, error = asyncio.run(_run_print_frame(m, fr))
                    if run_path and not error:
                        run_id = Path(run_path).name
                        dom = _read_json(DEFAULT_RUNS_DIR / run_id / "domain_result.json") or {}
                        fr.update(status="done", run_id=run_id, phenology=dom.get("phenology"))
                    else:
                        fr.update(status="failed", error=error or "no result returned")
            except Exception as e:
                traceback.print_exc()
                fr.update(status="failed", error=str(e))
            fr["finished_utc"] = _now_utc()
            _save_manifest(m)
    finally:
        failed = sum(1 for f in m["frames"] if f.get("status") == "failed")
        pending = sum(1 for f in m["frames"] if f.get("status") in ("pending", "running"))
        m["status"] = "cancelled" if cancelled else ("done_with_failures" if failed else ("done" if not pending else "incomplete"))
        for f in m["frames"]:
            if f.get("status") == "running":
                f["status"] = "pending"
        m["finished_utc"] = _now_utc()
        _save_manifest(m)
        with _series_lock:
            _series_state["active_id"] = None
            _series_state["cancel"] = False
        print(f"[Series] {series_id} finished: {m['status']} ({failed} failed)")


def _start_series_thread(series_id: str, frame_numbers: List[int]) -> None:
    with _series_lock:
        if _series_state["active_id"]:
            raise HTTPException(status_code=409, detail=f"A series is already running: {_series_state['active_id']}")
        _series_state.update(active_id=series_id, last_id=series_id, cancel=False)
    threading.Thread(target=_series_worker, args=(series_id, frame_numbers), daemon=True).start()


@app.post("/api/series/plan")
async def plan_series(req: SeriesRequest):
    frames = _series_frames(req)
    spf = _seconds_per_frame(req.kind)
    return {
        "count": len(frames),
        "dates": len({f["date"] for f in frames}),
        "times": len({f["time"] for f in frames}),
        "first": frames[:3],
        "last": frames[-1:] if frames else [],
        "needs_confirm": len(frames) > SERIES_CONFIRM_ABOVE,
        "estimate_minutes": round(len(frames) * spf / 60.0, 1),
        "has_keystone": bool(_load_keystones().get(req.view_id)),
    }


@app.post("/api/series")
async def start_series(req: SeriesRequest):
    if req.kind not in ("prints", "phenology"):
        raise HTTPException(status_code=422, detail="kind must be prints or phenology.")
    ks = _load_keystones().get(req.view_id)
    if not ks:
        raise HTTPException(status_code=422, detail="This view has no approved keystone yet.")
    if req.kind == "prints" and req.weather_mode.upper() == "AUTO":
        raise HTTPException(status_code=422, detail="Pick an explicit weather preset for a series; live weather only applies to today.")
    frames = _series_frames(req)
    if not frames:
        raise HTTPException(status_code=422, detail="That range produces no frames.")
    if len(frames) > SERIES_CONFIRM_ABOVE and not req.confirm_large:
        raise HTTPException(status_code=422, detail=f"{len(frames)} frames needs explicit confirmation.")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    series_id = f"{req.view_id}_{req.kind}_{stamp}"
    spec = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    m = {
        "id": series_id,
        "kind": req.kind,
        "view_id": req.view_id,
        "view_name": ks.get("view_name"),
        "keystone_run": ks["run_id"],
        "created_utc": _now_utc(),
        "status": "queued",
        "seed": req.seed if req.seed is not None else secrets.randbelow(2**31 - 1),
        "spec": spec,
        "frames": [dict(n=i + 1, status="pending", **f) for i, f in enumerate(frames)],
    }
    _save_manifest(m)
    _start_series_thread(series_id, [f["n"] for f in m["frames"]])
    print(f"[Series] started {series_id}: {len(frames)} {req.kind} frame(s)")
    return m


@app.get("/api/series/active")
async def active_series():
    sid = _series_state["active_id"] or _series_state["last_id"]
    if not sid:
        return {"series": None, "running": False}
    return {"series": _load_manifest(sid), "running": _series_state["active_id"] == sid}


@app.get("/api/series/{series_id}")
async def get_series(series_id: str):
    return _load_manifest(series_id)


@app.post("/api/series/{series_id}/cancel")
async def cancel_series(series_id: str):
    if _series_state["active_id"] != series_id:
        raise HTTPException(status_code=409, detail="That series is not running.")
    _series_state["cancel"] = True
    return {"cancelling": series_id, "note": "Stops after the frame in progress."}


@app.post("/api/series/{series_id}/rerun_failed")
async def rerun_failed(series_id: str):
    m = _load_manifest(series_id)
    todo = [f["n"] for f in m["frames"] if f.get("status") in ("failed", "pending")]
    if not todo:
        raise HTTPException(status_code=422, detail="No failed or unfinished frames to rerun.")
    for f in m["frames"]:
        if f["n"] in todo:
            f.update(status="pending", error=None)
    _save_manifest(m)
    _start_series_thread(series_id, todo)
    return {"rerunning": todo}


# -------------------------------------------------------------------------
# Street View reference (/api/streetview): propose a pano aimed at the subject,
# preview it, read it into notes. Images pass through and are never stored;
# only the pano ID, view settings and notes are kept (Street View policy exempts pano IDs).
# -------------------------------------------------------------------------
SV_META_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
SV_IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"
PANO_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{10,120}$")
STREETVIEW_DETAIL_TEXT = (
    "\n\n[STREET-LEVEL REFERENCE: THE SECOND IMAGE]\n"
    "The second image is a close-up detail photograph of the subject building, taken {date}. It is NOT a view of this "
    "scene: it shows only part of one building, from another position, cropped tight. Use it ONLY for the form of "
    "architectural details (openings, doors, ironwork, wall surfaces) and for the colour, pattern and placement of "
    "weathering and soiling on that building. The first image alone defines composition, camera position, viewing angle, "
    "field of view, geometry and the position of every object. Never copy the reference's vehicles, people, signs, foliage, "
    "weather, wet surfaces, sky, light, shadows, season, camera position or framing."
)

STREETVIEW_REFERENCE_TEXT = (
    "\n\n[STREET-LEVEL REFERENCE: THE SECOND IMAGE]\n"
    "The second image is a street-level reference photograph of the subject, taken {date} from a different position. "
    "Use it ONLY for the form of architectural details and for the pattern, strength and placement of weathering and "
    "soiling on facades that appear in both images; the reference notes in the SCENE section say which facade is which. "
    "The first image still defines composition, geometry, camera and the position of every object. Never copy the "
    "reference's vehicles, people, signs, foliage, weather, wet surfaces, sky, light, shadows, season, camera position or framing."
)


# Delighting: the guided-filter lift brightens broad dark areas, soot included (see vision_preprocessor).
# Fresh captures keep the original gamma. Keystones re-delight their source capture more gently.
DEFAULT_DELIGHT_GAMMA = 0.72


def _keystone_delight_setting():
    """KEYSTONE_DELIGHT_GAMMA in .env: a gamma between 0.5 and 1.0 (default 0.85), or "off" for the raw capture.
    Lower lifts more. 1.0 still sharpens detail slightly; only "off" sends the capture untouched."""
    raw = (os.getenv("KEYSTONE_DELIGHT_GAMMA") or "0.85").strip().lower()
    if raw == "off":
        return "off"
    try:
        return min(max(float(raw), 0.5), 1.0)
    except ValueError:
        print(f"[Delight] KEYSTONE_DELIGHT_GAMMA={raw!r} is not a number or 'off'; using 0.85")
        return 0.85


# ---------------------------------------------------------------------------------------------
# Sun shadows from Cesium (2026-10-13). The image model keeps the light in its seed and does not follow
# light-direction words, and Google's tiles carry the sun of their aerial photos. So the client captures
# the view twice, without and with Cesium's own sun and cast shadows, at the frame's date and time.
# The shadowless capture is delighted as usual; the shadow mask (shadowed / shadowless brightness) is then
# laid onto the delighted seed, after delighting, so the delight pass cannot weaken it.
SUN_SHADOW_FLOOR = 0.35      # never darken below this fraction of the delighted seed's brightness
SUN_SHADOW_KEEP_RULE = ("- SHADOW RULE: The cast shadows in the reference plate are correct for this date and time: "
                        "keep their positions, shapes and directions exactly, and light every surface consistently with them.")


def _b64_to_array(data_url: str):
    import io
    import numpy as np
    from PIL import Image
    raw = data_url.split(",", 1)[1] if data_url.startswith("data:") else data_url
    return np.asarray(Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")).astype("float32")


def _apply_sun_shadows(seed_b64: str, off_b64: str, on_b64: str):
    """Returns (new seed data URL or None, info dict). Never raises: on any problem the seed is left alone."""
    try:
        import io
        import numpy as np
        from PIL import Image, ImageFilter
        off, on = _b64_to_array(off_b64), _b64_to_array(on_b64)
        if off.shape != on.shape:
            return None, {"applied": False, "reason": f"capture sizes differ {off.shape[:2]} vs {on.shape[:2]}"}
        lum = lambda a: 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
        ratio = (lum(on) + 4.0) / (lum(off) + 4.0)
        mask = np.clip(ratio, SUN_SHADOW_FLOOR, 1.0)
        mask[mask > 0.95] = 1.0                       # ignore JPEG noise: only real shadows darken
        m_img = Image.fromarray((mask * 255).astype("uint8"), "L").filter(ImageFilter.MedianFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
        seed = _b64_to_array(seed_b64)
        if seed.shape[:2] != off.shape[:2]:
            m_img = m_img.resize((seed.shape[1], seed.shape[0]), Image.BILINEAR)
        m = np.asarray(m_img).astype("float32") / 255.0
        out = np.clip(seed * m[..., None], 0, 255).astype("uint8")
        buf = io.BytesIO(); Image.fromarray(out, "RGB").save(buf, "JPEG", quality=92)
        coverage = float((m < 0.9).mean())
        mbuf = io.BytesIO(); m_img.save(mbuf, "PNG")
        return ("data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii"),
                {"applied": coverage > 0.002, "coverage": round(coverage, 4),
                 "reason": "shadows laid onto the delighted seed" if coverage > 0.002 else "no shadows found in the shadow pass",
                 "mask_png_b64": base64.b64encode(mbuf.getvalue()).decode("ascii")})
    except Exception as e:
        traceback.print_exc()
        return None, {"applied": False, "reason": f"error: {e}"}


def _keep_shadows_in_prompt(compiled) -> None:
    """The lighting directive tells the model to erase every shadow in the plate (written for the tiles' baked-in,
    wrong shadows). With Cesium's correct shadows laid in, that line must say the opposite. Print prompts drop
    the erase line altogether, so there the keep rule is added at the end of the light block."""
    pat = re.compile(r"^- SHADOW OVERWRITE RULE:.*$", re.M)
    for attr in ("prompt", "user_prompt"):
        text = getattr(compiled, attr, None)
        if not text:
            continue
        if pat.search(text):
            text = pat.sub(SUN_SHADOW_KEEP_RULE, text)
        elif SUN_SHADOW_KEEP_RULE not in text:
            tail = "\n\nSharp focus near to far."
            text = text.replace(tail, "\n" + SUN_SHADOW_KEEP_RULE + tail, 1) if tail in text else text + "\n" + SUN_SHADOW_KEEP_RULE
        setattr(compiled, attr, text)


def _direct_sun(lighting_state) -> bool:
    """True only when the frame is lit by direct sun (not overcast, fog, rain, snow, twilight or night):
    the only case where cast shadows belong in the seed."""
    return "SOLAR RELIGHTING DIRECTIVE" in (getattr(lighting_state, "prompt_directive", "") or "")


def _maps_key() -> str:
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="GOOGLE_MAPS_API_KEY is not configured.")
    return key


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Street View frames are fetched at 16:9 so they match the Maps view and the Cesium capture.
# The API's fov is HORIZONTAL; a Maps URL's "y" value is VERTICAL (verified 2026-10-09):
# horizontal = 2 * atan(tan(vertical / 2) * 16 / 9). Maps' default 75 vertical is about 107 horizontal.
SV_SIZE = "640x360"
SV_SIZES = ("640x360", "640x640")   # 640x640 only to re-show keystones made before the switch
SV_DEFAULT_PITCH = 0.0
SV_DEFAULT_FOV = 107.5
# Detail crop (2026-10-17): the reference is aimed from the pano at the view's subject point with a narrow field of
# view, so it carries the subject's surfaces but little street or perspective to copy. The full pano view pulled
# renders toward Street View's camera position (DECISIONS 2026-10-17). 45 across is Don's choice for the first test.
SV_DETAIL_FOV = 45.0


def _fetch_pano(pano_id: str, heading: float, pitch: float, fov: float, size: str = SV_SIZE) -> bytes:
    if not PANO_ID_RE.match(pano_id or ""):
        raise HTTPException(status_code=400, detail="Invalid pano ID.")
    if size not in SV_SIZES:
        raise HTTPException(status_code=400, detail=f"Unsupported Street View size: {size}")
    r = requests.get(SV_IMAGE_URL, params={
        "size": size, "pano": pano_id, "heading": round(float(heading), 1),
        "pitch": round(float(pitch), 1), "fov": round(max(10.0, min(120.0, float(fov))), 1),
        "return_error_code": "true", "key": _maps_key(),
    }, timeout=20)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image"):
        raise HTTPException(status_code=502, detail=f"Street View image request failed ({r.status_code}).")
    return r.content


def _pano_location(pano_id: str) -> tuple:
    """The pano's own lat/lon, from the (free) metadata endpoint."""
    if not PANO_ID_RE.match(pano_id or ""):
        raise HTTPException(status_code=400, detail="Invalid pano ID.")
    meta = requests.get(SV_META_URL, params={"key": _maps_key(), "pano": pano_id}, timeout=15).json()
    if meta.get("status") != "OK":
        raise HTTPException(status_code=404, detail=f"Pano metadata not found ({meta.get('status')}).")
    return meta["location"]["lat"], meta["location"]["lng"]


def _detail_aim(pano_id: str, subj_lat: float, subj_lon: float) -> dict:
    """Heading and distance from the pano to the subject point, for the detail crop."""
    plat, plon = _pano_location(pano_id)
    return {"heading": round(_bearing(plat, plon, subj_lat, subj_lon), 1),
            "distance_m": round(_distance_m(plat, plon, subj_lat, subj_lon), 1), "fov": SV_DETAIL_FOV}


@app.get("/api/streetview/detail")
def streetview_detail(pano: str, lat: float, lon: float, pitch: float = 10.0):
    """Preview of the detail crop MAKE KEYSTONE will send: aimed from the pano at the subject point, 45 degrees across.
    Passed straight through; never written to disk."""
    aim = _detail_aim(pano, lat, lon)
    img = _fetch_pano(pano, aim["heading"], pitch, aim["fov"])
    return Response(content=img, media_type="image/jpeg",
                    headers={"Cache-Control": "no-store", "X-Detail-Heading": str(aim["heading"]),
                             "X-Detail-Fov": str(aim["fov"]), "Access-Control-Expose-Headers": "X-Detail-Heading, X-Detail-Fov"})


class StreetViewProposeRequest(BaseModel):
    lat: float
    lon: float
    pano_id: Optional[str] = None
    radius: int = 50


@app.post("/api/streetview/propose")
def streetview_propose(req: StreetViewProposeRequest):
    params = {"key": _maps_key(), "source": "outdoor"}
    if req.pano_id:
        if not PANO_ID_RE.match(req.pano_id):
            raise HTTPException(status_code=400, detail="Invalid pano ID.")
        params["pano"] = req.pano_id
    else:
        params.update(location=f"{req.lat},{req.lon}", radius=max(10, min(200, req.radius)))
    try:
        meta = requests.get(SV_META_URL, params=params, timeout=15).json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Street View metadata request failed: {e}")
    if meta.get("status") != "OK":
        raise HTTPException(status_code=404, detail=f"No Street View pano found ({meta.get('status')}). Try a larger radius or a pano ID.")
    plat, plon = meta["location"]["lat"], meta["location"]["lng"]
    return {
        "pano_id": meta.get("pano_id"),
        "date": meta.get("date"),
        "copyright": meta.get("copyright"),
        "lat": plat, "lon": plon,
        "heading": round(_bearing(plat, plon, req.lat, req.lon), 1),
        "pitch": SV_DEFAULT_PITCH,
        "fov": SV_DEFAULT_FOV,
        "size": SV_SIZE,
        "distance_m": round(_distance_m(plat, plon, req.lat, req.lon), 1),
    }


@app.get("/api/streetview/image")
def streetview_image(pano: str, heading: float = 0.0, pitch: float = SV_DEFAULT_PITCH, fov: float = SV_DEFAULT_FOV,
                     size: str = SV_SIZE):
    # Passed straight through for preview; never written to disk.
    return Response(content=_fetch_pano(pano, heading, pitch, fov, size), media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


class StreetViewReadRequest(BaseModel):
    run_id: str
    pano_id: str
    heading: float
    pitch: float = 10.0
    fov: float = 80.0
    date: Optional[str] = None
    scene_text: Optional[str] = None


@app.post("/api/streetview/read")
def streetview_read(req: StreetViewReadRequest):
    d = _run_dir(req.run_id)
    capture = _file_data_url(d / "viewport_capture.jpg", "image/jpeg")
    if not capture:
        raise HTTPException(status_code=422, detail="This run has no capture to compare against.")
    scene = req.scene_text or load_domain_from_run(d)[0].documentary_prompt
    pano = _fetch_pano(req.pano_id, req.heading, req.pitch, req.fov)
    notes = read_streetview(capture, pano, scene, req.date, os.getenv("GEMINI_API_KEY"))
    print(f"[StreetView] read pano {req.pano_id} for {req.run_id}: {len(notes)} chars")
    return {"notes": notes, "pano_id": req.pano_id, "date": req.date}


@app.post("/api/streetview/rewrite")
def streetview_rewrite(req: StreetViewReadRequest):
    """Finishing pass (weft rules, 2026-10-18): surfaces, painted colours and opening shapes set from the pano;
    the scene text's structure is kept; structural additions listed, contradictions reported (never applied), and
    any structural term the pass dropped found by comparing the texts. Nothing is saved here."""
    d = _run_dir(req.run_id)
    capture = _file_data_url(d / "viewport_capture.jpg", "image/jpeg")
    if not capture:
        raise HTTPException(status_code=422, detail="This run has no capture to compare against.")
    scene = req.scene_text or load_domain_from_run(d)[0].documentary_prompt
    pano = _fetch_pano(req.pano_id, req.heading, req.pitch, req.fov)
    res = rewrite_condition_from_streetview(capture, pano, scene, req.date, os.getenv("GEMINI_API_KEY"))
    revised = res["scene_text"]
    print(f"[StreetView] finishing pass from pano {req.pano_id} for {req.run_id}: {len(scene)} -> {len(revised)} chars"
          f" | added {len(res['added'])} | conflicts {len(res['conflicts'])}"
          f"{' | REMOVED: ' + ', '.join(res['removed']) if res['removed'] else ''}")
    return {**res, "original": scene, "pano_id": req.pano_id, "date": req.date,
            "changed": revised.strip() != scene.strip()}


class LsaWeaveRequest(BaseModel):
    run_id: str
    analysis: str
    scene_text: Optional[str] = None
    lsa_run_id: Optional[str] = None
    # 2026-10-16: the LSA run's brief (place, standpoint, looking at, scene layout), in Don's words.
    # Its structure counts as confirmed; its street names are translated into position words.
    director_layout: Optional[str] = None


@app.post("/api/lsa/weave")
def lsa_weave(req: LsaWeaveRequest):
    """The LSA pass: the scene text back with an LSA Studio analysis's materials, condition and biology woven in,
    the director's layout applied, and every structural addition listed with its status (confirmed or proposed).
    Nothing is saved here; the page puts the text in the editor and sends it with Replay or Make keystone."""
    d = _run_dir(req.run_id)
    capture = _file_data_url(d / "viewport_capture.jpg", "image/jpeg")
    if not capture:
        raise HTTPException(status_code=422, detail="This run has no capture to weave against.")
    if not (req.analysis or "").strip():
        raise HTTPException(status_code=422, detail="The LSA run has no analysis.")
    domain, _ = load_domain_from_run(d)
    scene = (req.scene_text or "").strip() or domain.documentary_prompt
    out = weave_lsa_into_scene(capture, scene, domain.botanical_ecology, req.analysis, os.getenv("GEMINI_API_KEY"),
                               director_layout=req.director_layout)
    added = out.get("added_structure") or []
    print(f"[Weft] pass from {req.lsa_run_id} on {req.run_id}: {len(scene)} -> {len(out['scene_text'])} chars"
          f" | layout {'sent' if (req.director_layout or '').strip() else 'none'}"
          f" | structure added: {sum(a['status'] == 'confirmed' for a in added)} confirmed, "
          f"{sum(a['status'] == 'proposed' for a in added)} proposed"
          f"{' | check: ' + ', '.join(out['warnings']) if out['warnings'] else ''}"
          f"{' | REMOVED: ' + ', '.join(out.get('removed') or []) if out.get('removed') else ''}")
    return {**out, "original": scene, "lsa_run_id": req.lsa_run_id}


def _find_compiled_prompt(d: Path) -> tuple:
    """The prompt the image model was sent for this run, wherever the archiver put it.
    Every compiled prompt opens with "[TASK:", so look for that: first in run_metadata.json (any string
    value, at any depth), then in the run's text files. Returns (prompt, where it was found)."""
    def walk(v, path):
        if isinstance(v, str) and v.lstrip().startswith("[TASK:"):
            return v, path
        if isinstance(v, dict):
            for k, x in v.items():
                hit = walk(x, f"{path}.{k}")
                if hit:
                    return hit
        if isinstance(v, list):
            for i, x in enumerate(v):
                hit = walk(x, f"{path}[{i}]")
                if hit:
                    return hit
        return None
    meta = _read_json(d / "run_metadata.json")
    if meta:
        hit = walk(meta, "run_metadata.json")
        if hit:
            return hit
    for f in sorted(d.glob("*")):
        if f.suffix.lower() not in (".txt", ".md") or f.stat().st_size > 400_000:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        i = text.find("[TASK:")
        if i >= 0:
            return text[i:].strip(), f.name
    return None, None


# -------------------------------------------------------------------------
# Alignment (2026-10-17): has a rendered plate kept the capture's framing? Measured on request, cached in the run
# folder (alignment.json, tied to the plate file's time and size so a changed plate is measured again).
# -------------------------------------------------------------------------
def _plate_stamp(d: Path) -> str:
    st = (d / "spatial_twin.png").stat()
    return f"{st.st_mtime_ns}:{st.st_size}"


def _cached_alignment(d: Path) -> Optional[dict]:
    a = _read_json(d / "alignment.json")
    if not a or not (d / "spatial_twin.png").exists():
        return None
    try:
        if a.get("plate_stamp") != _plate_stamp(d) or a.get("version") != alignment_engine.VERSION:
            return None
    except OSError:
        return None
    return {k: a.get(k) for k in ("verdict", "summary", "can_realign", "coverage", "score", "scale", "rotation", "dx", "dy")}


def _measure_alignment(d: Path) -> dict:
    if not (d / "viewport_capture.jpg").exists() or not (d / "spatial_twin.png").exists():
        raise HTTPException(status_code=422, detail="This run needs both a capture and a rendered plate to measure alignment.")
    a = _read_json(d / "alignment.json")
    stamp = _plate_stamp(d)
    if a and a.get("plate_stamp") == stamp and a.get("version") == alignment_engine.VERSION:
        return a
    est = alignment_engine.measure(d / "viewport_capture.jpg", d / "spatial_twin.png")
    if est is None:
        raise HTTPException(status_code=501, detail="Alignment needs numpy and Pillow in the server's environment.")
    est["plate_stamp"] = stamp
    est["measured_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    tmp = d / "alignment.json.tmp"
    tmp.write_text(json.dumps(est, indent=2), encoding="utf-8")
    tmp.replace(d / "alignment.json")
    print(f"[Alignment] {d.name}: {est['verdict']}, {est['summary']} (score {est['score']}, coverage {est['coverage']})")
    return est


@app.get("/api/runs/{run_id}/alignment")
async def run_alignment(run_id: str):
    """How the run's plate differs from its capture: verdict (aligned, drifted, uncertain), plain-words summary,
    and the numbers. Takes a few seconds the first time; cached after that."""
    d = _run_dir(run_id)
    return await asyncio.to_thread(_measure_alignment, d)


@app.post("/api/runs/{run_id}/realign")
async def realign_run(run_id: str):
    """Make a NEW keystone candidate whose plate is this run's plate warped back onto the capture's framing.
    The original run is never changed, so an approved keystone, its date plates and prints stay as they were.
    Not for prints or date plates (they follow their keystone), and only when the gap left at the edges is small."""
    d = _run_dir(run_id)
    meta = _read_json(d / "run_metadata.json") or {}
    settings = meta.get("settings") or {}
    if settings.get("keystone_print_of") or settings.get("date_plate_of"):
        raise HTTPException(status_code=422, detail="Prints and date plates follow their keystone's framing; realign the keystone instead.")
    est = await asyncio.to_thread(_measure_alignment, d)
    if est["verdict"] != "drifted":
        raise HTTPException(status_code=422, detail=f"Nothing to realign: the plate measures {est['verdict']} ({est['summary']}).")
    if not est.get("can_realign"):
        raise HTTPException(status_code=422, detail=(
            f"Too far to realign cleanly: the moved render covers only {est['coverage'] * 100:.0f}% of the frame, "
            f"so {100 - est['coverage'] * 100:.0f}% would have to be filled in at the edges. Render another candidate instead."))
    now = datetime.now()
    base = _RUN_STAMP_RE.sub("", d.name).rstrip("_") or "run"
    new_id = f"{base}_{now:%Y%m%d_%H%M%S}"
    nd = DEFAULT_RUNS_DIR / new_id
    if nd.exists():
        raise HTTPException(status_code=409, detail="A run with that name already exists; try again in a second.")
    skip = {"alignment.json", "spatial_twin.png", "spatial_twin_unaligned.png", "canopy_mask.png", "spatial_twin_raw.png"}
    def _build():
        import shutil
        nd.mkdir(parents=True)
        for f in d.iterdir():
            if f.is_file() and f.name not in skip and not f.name.endswith(".tmp"):
                shutil.copy2(f, nd / f.name)
        shutil.copy2(d / "spatial_twin.png", nd / "spatial_twin_unaligned.png")
        return alignment_engine.realign(d / "viewport_capture.jpg", d / "spatial_twin.png", est, nd / "spatial_twin.png")
    try:
        info = await asyncio.to_thread(_build)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Realign failed: {e}")
    s2 = dict(settings)
    s2.pop("ab", None)                               # a realigned copy is not an A/B arm
    s2["keystone_candidate"] = True
    s2["realigned_from"] = {"run_id": run_id,
                            "moved": {k: est[k] for k in ("scale", "rotation", "dx", "dy", "summary", "coverage")},
                            "filled_fraction": info["filled_fraction"]}
    meta["settings"] = s2
    meta["timestamp"] = f"{now:%Y%m%d_%H%M%S}"
    mtmp = nd / "run_metadata.json.tmp"
    mtmp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    mtmp.replace(nd / "run_metadata.json")
    after = await asyncio.to_thread(_measure_alignment, nd)
    print(f"[Alignment] realigned {run_id} -> new candidate {new_id}: was {est['summary']}; now {after['verdict']} "
          f"({after['summary']}); {info['filled_fraction'] * 100:.1f}% of the frame filled at the edges")
    return {"run_id": new_id, "before": est, "after": after, "filled_fraction": info["filled_fraction"]}

@app.get("/api/runs/{run_id}/prompt")
async def run_prompt(run_id: str):
    """The prompt sent to the image model for one archived run, for the Pipeline result tab."""
    d = _run_dir(run_id)
    prompt, source = _find_compiled_prompt(d)
    meta = _read_json(d / "run_metadata.json") or {}
    settings = meta.get("settings") or {}
    return {"run_id": run_id, "prompt": prompt, "source": source,
            "provider": meta.get("provider"), "mode": settings.get("mode"),
            "date": settings.get("date"), "time_of_day": settings.get("time_of_day"),
            "weather": (meta.get("lighting_resolved") or {}).get("weather") or settings.get("weather_mode"),
            "composite": settings.get("composite")}


@app.get("/api/runs/{run_id}/scene")
async def run_scene(run_id: str):
    domain, source = load_domain_from_run(_run_dir(run_id))
    return {
        "id": run_id,
        "address": domain.address,
        "documentary_prompt": domain.documentary_prompt,
        "loaded_from": source,
    }


@app.get("/api/runs/{run_id}/file/{name}")
async def run_file(run_id: str, name: str):
    if name not in RUN_FILES:
        raise HTTPException(status_code=404, detail="Unknown run file.")
    path = _run_dir(run_id) / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not in run {run_id}.")
    return FileResponse(path, media_type=RUN_FILES[name])


# -------------------------------------------------------------------------
# Main Pipeline Endpoint (/api/process_view)
# -------------------------------------------------------------------------
@app.post("/api/process_view")
async def process_view(request: ProcessViewRequest):
    return StreamingResponse(
        execute_pipeline_stream(request),
        media_type="application/x-ndjson"
    )


# Static and Viewfinder routes
@app.get("/")
@app.get("/viewfinder.html")
async def serve_viewfinder():
    candidates = [
        Path(__file__).parent / "static" / "viewfinder.html",
        Path(__file__).parent / "static" / "index.html",
        Path(__file__).parent / "viewfinder.html",
        Path(__file__).parent / "index.html",
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="viewfinder.html not found.")


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)