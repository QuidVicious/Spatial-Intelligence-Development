import os
import re
import json
import base64
import requests
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# 1. Environment & Key Management
env_paths = [
    Path(".env"),
    Path("../.env"),
    Path(r"C:\DEV\Squid\SquidBlack\.env")
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
CESIUM_ION_TOKEN = os.getenv("CESIUM_ION_TOKEN", "")

app = FastAPI(title="Spatial Intelligence Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load System Instruction
EYE_PROMPT_PATH = Path(__file__).parent / "eye_prompt.md"
def get_system_prompt() -> str:
    if EYE_PROMPT_PATH.exists():
        return EYE_PROMPT_PATH.read_text(encoding="utf-8")
    return "You are The Eye: a spatial and physical simulation intelligence engine."

# 2. Data Models
class ViewportRequest(BaseModel):
    lat: float
    lon: float
    heading: float = 0.0          # View direction in degrees (0=North, 90=East)
    pitch: float = -15.0         # Camera pitch
    altitude_agl: float = 4.5    # Observer height above ground in meters
    altitude_amsl: float = 50.0  # Height above sea level
    fov: float = 75.0            # Field of view
    temporal_anchor: Optional[str] = "Present Day"
    viewport_image: Optional[str] = None # Base64 screenshot from Cesium

# 3. Helper Functions
def reverse_geocode(lat: float, lon: float) -> str:
    """Resolves latitude/longitude into a precise street address using Google Maps API."""
    if not GOOGLE_MAPS_API_KEY:
        return f"{lat:.6f}, {lon:.6f}"
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("results"):
                return data["results"][0]["formatted_address"]
    except Exception as e:
        print(f"[Reverse Geocode Error]: {e}")
    return f"{lat:.6f}, {lon:.6f}"

def query_the_eye(telemetry: dict, address: str, temporal_anchor: str, viewport_image: Optional[str] = None) -> tuple[dict, str]:
    """Queries Gemini 3.7 Flash with Multimodal Vision Context + Telemetry."""
    system_instruction = get_system_prompt()
    
    user_payload = f"""
OBSERVER TELEMETRY & SPATIAL ANCHOR:
- Site Address / Landmark: {address}
- Coordinates: [{telemetry['lat']}, {telemetry['lon']}]
- Observer Elevation AGL: {telemetry['altitude_agl']:.1f} meters
- Observer Elevation AMSL: {telemetry['altitude_amsl']:.1f} meters
- View Direction (Heading): {telemetry['heading']:.1f}°
- Camera Pitch: {telemetry['pitch']:.1f}°
- Field of View (FOV): {telemetry['fov']:.1f}°
- Temporal Anchor: {temporal_anchor}

INSTRUCTION:
Observe the attached 3D viewport capture as the absolute spatial ground-truth for camera vantage, building silhouettes, unbroken crescent curves, and tree placement. Upgrade all photogrammetry meshes into 1:1 physical reality. Generate the full GeoJSON FeatureCollection followed by the documentary-style photographic prompt.
"""

    parts = []
    
    # Attach Viewport Screenshot if present
    if viewport_image:
        b64_clean = viewport_image.split(",")[1] if "," in viewport_image else viewport_image
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": b64_clean
            }
        })
        print("[The Eye]: Attached Cesium viewport screenshot to Gemini vision context.")

    parts.append({"text": user_payload})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {"Content-Type": "application/json"}
    body = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": parts
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
    
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Gemini API Error: {resp.text}")
    
    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    
    # Extract GeoJSON
    geojson_data = {}
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", raw_text)
    if json_match:
        try:
            geojson_data = json.loads(json_match.group(1))
        except Exception:
            pass
            
    # Extract Prompt text
    prompt_text = ""
    prompt_match = re.search(r"Prompt:\s*([\s\S]*)", raw_text, re.IGNORECASE)
    if prompt_match:
        prompt_text = prompt_match.group(1).strip()
    else:
        prompt_text = raw_text.strip()
        
    return geojson_data, prompt_text

def synthesize_image(prompt: str, viewport_image: Optional[str] = None) -> Optional[str]:
    """Generates the spatial twin image using Nano Banana 2 with multimodal spatial conditioning."""
    if not GEMINI_API_KEY:
        print("[Image Gen]: No GEMINI_API_KEY found.")
        return None
        
    models = [
        "gemini-3.1-flash-image",
        "gemini-3.1-flash-lite-image",
        "gemini-3-pro-image",
        "gemini-2.5-flash-image"
    ]
    
    parts = []
    
    # 1. Attach Cesium screenshot as direct geometric ground truth
    if viewport_image:
        b64_clean = viewport_image.split(",")[1] if "," in viewport_image else viewport_image
        parts.append({
            "inlineData": {
                "mimeType": "image/jpeg",
                "data": b64_clean
            }
        })
        conditioning_text = (
            "Using the attached image as strict spatial, geometric, and camera frustum ground truth, "
            "re-render the scene into a photorealistic 35mm photograph. Strictly lock the exact camera angle, "
            "horizontal eye-level pitch, tree canopy positions, and continuous unbroken crescent terrace facades. "
            f"Apply these authentic physical materials, lighting, and environmental details: {prompt}"
        )
    else:
        conditioning_text = prompt

    parts.append({"text": conditioning_text})
    
    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": 0.2,
            "topP": 0.2,
            "imageConfig": {
                "aspectRatio": "16:9"
            }
        }
    }
    
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            print(f"[Image Gen]: Generating visually conditioned twin with {model} (Temp 0.2, Top-P 0.2)...")
            resp = requests.post(url, headers=headers, json=body, timeout=90)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    for part in candidates[0].get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            mime = part["inlineData"].get("mimeType", "image/png")
                            b64 = part["inlineData"].get("data", "")
                            print(f"[Image Gen]: ✅ Successfully synthesized twin with {model}!")
                            return f"data:{mime};base64,{b64}"
                print(f"[Image Gen]: {model} returned 200 but no inline image data was returned.")
            else:
                print(f"[Image Gen - {model} Error {resp.status_code}]: {resp.text}")
        except Exception as e:
            print(f"[Image Gen Exception with {model}]: {e}")
            
    return None

# 4. Endpoints
@app.get("/")
def serve_index():
    return FileResponse(Path(__file__).parent / "viewfinder.html")

@app.get("/api/config")
def get_config():
    return {
        "cesium_ion_token": CESIUM_ION_TOKEN,
        "google_maps_api_key": GOOGLE_MAPS_API_KEY
    }

@app.post("/api/process_view")
def process_view(req: ViewportRequest):
    # 1. Reverse Geocode Coordinates
    address = reverse_geocode(req.lat, req.lon)
    
    # 2. Query The Eye with Multimodal Viewport Context
    telemetry = {
        "lat": req.lat,
        "lon": req.lon,
        "heading": req.heading,
        "pitch": req.pitch,
        "altitude_agl": req.altitude_agl,
        "altitude_amsl": req.altitude_amsl,
        "fov": req.fov
    }
    
    geojson_scaffold, prompt_text = query_the_eye(
        telemetry=telemetry,
        address=address,
        temporal_anchor=req.temporal_anchor or "Present Day",
        viewport_image=req.viewport_image
    )
    
    # 3. Synthesize Twin Image
    # 3. Synthesize Twin Image (passing viewport image for visual locking)
    synthesized_image_url = synthesize_image(prompt_text, viewport_image=req.viewport_image)
    
    return {
        "address": address,
        "telemetry": telemetry,
        "temporal_anchor": req.temporal_anchor,
        "geojson": geojson_scaffold,
        "prompt": prompt_text,
        "synthesized_image": synthesized_image_url
    }

app.mount("/", StaticFiles(directory=Path(__file__).parent, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)