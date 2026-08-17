import os
import re
import json
import base64
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# -----------------------------------------------------------------------------
# 1. Centralized Environment & Path Configuration
# -----------------------------------------------------------------------------
ENV_PATH = Path(r"C:\DEV\Squid\SquidBlack\.env")
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
CESIUM_ION_TOKEN = os.getenv("CESIUM_ION_TOKEN")

if not GEMINI_API_KEY:
    print("[WARNING] GEMINI_API_KEY is not set.")

BASE_DIR = Path(__file__).resolve().parent
RUNS_DIR = BASE_DIR / "spatial_twin_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_TEMPLATE_PATH = BASE_DIR / "eye_prompt.md"

# -----------------------------------------------------------------------------
# 2. FastAPI Initialization
# -----------------------------------------------------------------------------
app = FastAPI(title="Spatial Twin Intelligence Pipeline", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# 3. Schemas
# -----------------------------------------------------------------------------
class TelemetryData(BaseModel):
    latitude: float
    longitude: float
    altitude_agl: float
    heading: float
    pitch: float
    fov: float
    tile_mode: Optional[str] = "3D_TILES"

class SynthesisRequest(BaseModel):
    screenshot: str  # Base64 data URL
    temporal_anchor: Optional[str] = "Present Day"
    telemetry: TelemetryData

# -----------------------------------------------------------------------------
# 4. Core Pipeline Modules
# -----------------------------------------------------------------------------
def reverse_geocode(lat: float, lon: float) -> str:
    """Converts GPS coordinates into a precise street address."""
    if not GOOGLE_MAPS_API_KEY:
        return f"{lat:.5f}, {lon:.5f}"
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0].get("formatted_address", f"{lat:.5f}, {lon:.5f}")
    except Exception as e:
        print(f"[Reverse Geocode Error]: {e}")
    
    return f"{lat:.5f}, {lon:.5f}"

def query_the_eye(address: str, telemetry: TelemetryData, screenshot_b64: str, temporal_anchor: str) -> tuple[Dict[str, Any], str, str]:
    """Sends telemetry, image, and system instructions to Gemini 3.7 Flash."""
    system_instruction = ""
    if PROMPT_TEMPLATE_PATH.exists():
        system_instruction = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    
    # Strip base64 data prefix if present
    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64

    telemetry_summary = f"""
    TARGET LOCATION TELEMETRY:
    - Resolved Address: {address}
    - GPS Coordinates: {telemetry.latitude:.6f}, {telemetry.longitude:.6f}
    - Altitude (AGL): {telemetry.altitude_agl:.1f} meters
    - Camera Heading: {telemetry.heading:.1f}°
    - Camera Pitch: {telemetry.pitch:.1f}°
    - Camera Field of View (FOV): {telemetry.fov:.1f}°
    - Tile Rendering Mode: {telemetry.tile_mode}
    - Temporal Anchor: {temporal_anchor}
    """

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": telemetry_summary},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": raw_b64
                        }
                    },
                    {"text": "Analyze the spatial scene and output the RFC 7946 GeoJSON followed by '--- DOCUMENTARY PROMPT ---' and the 35mm documentary prompt."}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.25,
            "topP": 0.2,
            "thinkingConfig": {
                "thinkingBudget": 2048
            }
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={GEMINI_API_KEY}"
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"The Eye (Gemini 3.7 Flash) Error: {resp.text}")

    resp_json = resp.json()
    candidate_text = resp_json["candidates"][0]["content"]["parts"][0]["text"]

    # Parse GeoJSON block
    geojson_data = {}
    geojson_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate_text, re.DOTALL)
    if geojson_match:
        try:
            geojson_data = json.loads(geojson_match.group(1))
        except Exception as err:
            print(f"[GeoJSON Parse Warning]: {err}")

    # Parse Natural Language Documentary Prompt
    if "--- DOCUMENTARY PROMPT ---" in candidate_text:
        doc_prompt = candidate_text.split("--- DOCUMENTARY PROMPT ---")[-1].strip()
    else:
        doc_prompt = candidate_text

    # Extract spatial mode
    spatial_mode = geojson_data.get("properties", {}).get("spatial_mode", telemetry.tile_mode)
    if spatial_mode not in ["3D_RECTIFICATION", "2D_EXTRUSION"]:
        spatial_mode = "3D_RECTIFICATION" if telemetry.tile_mode == "3D_TILES" else "2D_EXTRUSION"

    return geojson_data, doc_prompt, spatial_mode

def synthesize_twin_image(prompt: str, screenshot_b64: str, spatial_mode: str, telemetry: TelemetryData) -> str:
    """Dispatches descriptive prompt and viewport image to gemini-3.1-flash-image."""
    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64

    if spatial_mode == "2D_EXTRUSION":
        temp = 0.4
        top_p = 0.4
        wrapper = (
            f"DIRECTIVE: VOLUMETRIC EXTRUSION FROM 2D SATELLITE FOOTPRINT.\n"
            f"Treat the attached image as a flat 2D site-plan / satellite footprint. "
            f"Extrude 3D building masses, vertical facades, and realistic roof structures upward perpendicular to the ground plane, "
            f"strictly matching the camera pitch ({telemetry.pitch:.1f}°) and heading ({telemetry.heading:.1f}°). "
            f"Do not paint textures flat on the ground. Plumb vertical walls.\n\n"
            f"SCENE DESCRIPTION:\n{prompt}"
        )
    else:
        temp = 0.2
        top_p = 0.2
        wrapper = (
            f"DIRECTIVE: UNIVERSAL GEOMETRIC RECTIFICATION.\n"
            f"Treat the attached image as a true 3D geometric wireframe with photogrammetry noise. "
            f"Plumb all vertical walls, establish continuous planar surfaces, sharpen 90-degree corner intersections, "
            f"and eliminate mesh wobble while strictly maintaining the exact building volumes and camera perspective.\n\n"
            f"SCENE DESCRIPTION:\n{prompt}"
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": wrapper},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": raw_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": temp,
            "topP": top_p
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={GEMINI_API_KEY}"
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Image Synthesis Error: {resp.text}")

    resp_json = resp.json()
    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=500, detail=f"Synthesis model returned no candidates: {resp_json}")

    parts = candidates[0].get("content", {}).get("parts", [])
    
    # Iterate through parts and find image data (supporting both camelCase and snake_case)
    for part in parts:
        if "inlineData" in part:
            img_b64 = part["inlineData"]["data"]
            return f"data:image/png;base64,{img_b64}"
        elif "inline_data" in part:
            img_b64 = part["inline_data"]["data"]
            return f"data:image/png;base64,{img_b64}"
    
    # If the model only returned text, log the text to console for troubleshooting
    text_responses = [p.get("text") for p in parts if "text" in p]
    print(f"[Image Synthesis Text Output (No Image Bytes)]: {text_responses}")
    raise HTTPException(status_code=500, detail=f"Synthesis model did not return image data. Response text: {text_responses}")

def archive_run(address: str, telemetry: TelemetryData, spatial_mode: str, temporal_anchor: str, 
                screenshot_b64: str, synthesized_b64: str, geojson_data: Dict[str, Any], prompt: str) -> str:
    """Saves all 5 pipeline artifacts into an isolated timestamped folder."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_addr = re.sub(r'[^a-zA-Z0-9_-]', '_', address)[:35].strip('_')
    folder_name = f"{clean_addr}_{timestamp}"
    run_path = RUNS_DIR / folder_name
    run_path.mkdir(parents=True, exist_ok=True)

    # 1. viewport_capture.jpg
    raw_viewport = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    (run_path / "viewport_capture.jpg").write_bytes(base64.b64decode(raw_viewport))

    # 2. synthesized_twin.png
    raw_synth = synthesized_b64.split(",")[-1] if "," in synthesized_b64 else synthesized_b64
    (run_path / "synthesized_twin.png").write_bytes(base64.b64decode(raw_synth))

    # 3. spatial_scaffold.json
    (run_path / "spatial_scaffold.json").write_text(json.dumps(geojson_data, indent=2), encoding="utf-8")

    # 4. prompt.txt
    (run_path / "prompt.txt").write_text(prompt, encoding="utf-8")

    # 5. telemetry_metadata.json
    meta = {
        "timestamp": timestamp,
        "resolved_address": address,
        "spatial_mode": spatial_mode,
        "temporal_anchor": temporal_anchor,
        "telemetry": telemetry.dict()
    }
    (run_path / "telemetry_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[Archived Run]: {run_path}")
    return folder_name

# -----------------------------------------------------------------------------
# 5. API Endpoints
# -----------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    """Provides client tokens securely to the Cesium HUD."""
    return {
        "cesium_ion_token": CESIUM_ION_TOKEN or "",
        "google_maps_api_key": GOOGLE_MAPS_API_KEY or ""
    }

@app.post("/api/process_view")
def process_view(req: SynthesisRequest):
    """Main pipeline execution endpoint."""
    print(f"\n[Run Triggered] Mode: {req.telemetry.tile_mode} | Pitch: {req.telemetry.pitch:.1f}° | Time: {req.temporal_anchor}")

    # 1. Reverse Geocode Coordinates
    address = reverse_geocode(req.telemetry.latitude, req.telemetry.longitude)
    print(f"[Resolved Address]: {address}")

    # 2. The Eye Spatial Cognitive Reasoning
    geojson_data, prompt, spatial_mode = query_the_eye(
        address=address,
        telemetry=req.telemetry,
        screenshot_b64=req.screenshot,
        temporal_anchor=req.temporal_anchor
    )
    print(f"[The Eye Complete] Mode: {spatial_mode}")

    # 3. Generative Twin Image Synthesis
    twin_image_b64 = synthesize_twin_image(
        prompt=prompt,
        screenshot_b64=req.screenshot,
        spatial_mode=spatial_mode,
        telemetry=req.telemetry
    )
    print("[Synthesis Complete] Image generated.")

    # 4. Run Archiving
    archive_folder = archive_run(
        address=address,
        telemetry=req.telemetry,
        spatial_mode=spatial_mode,
        temporal_anchor=req.temporal_anchor,
        screenshot_b64=req.screenshot,
        synthesized_b64=twin_image_b64,
        geojson_data=geojson_data,
        prompt=prompt
    )

    return {
        "status": "success",
        "address": address,
        "spatial_mode": spatial_mode,
        "prompt": prompt,
        "geojson": geojson_data,
        "synthesized_image_url": twin_image_b64,
        "archive_folder": archive_folder
    }

# -----------------------------------------------------------------------------
# 6. Static File Serving (Root HUD Viewport)
# -----------------------------------------------------------------------------
if (BASE_DIR / "viewfinder.html").exists():
    @app.get("/")
    def serve_index():
        return FileResponse(BASE_DIR / "viewfinder.html")

app.mount("/", StaticFiles(directory=str(BASE_DIR)), name="static")