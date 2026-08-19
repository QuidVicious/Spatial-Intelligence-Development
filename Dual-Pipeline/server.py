"""
Main Server Application: Streamlined FastAPI transport coordinator.
Routes requests across depth_engine, cognitive_engine, synthesis_engine, and archiver modules.
"""
import io
import os
import base64
from pathlib import Path
from typing import Optional
from PIL import Image

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# Internal Pipeline Modules (Perception, Reasoning, Synthesis, Archive)
from depth_engine import DepthEngine
from cognitive_engine import query_the_eye, reverse_geocode
from synthesis_engine import synthesize_twin_image
from archiver import archive_run

# -----------------------------------------------------------------------------
# 1. Environment Configuration
# -----------------------------------------------------------------------------
ENV_PATH = Path(r"C:\DEV\Squid\SquidBlack\.env")
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
CESIUM_ION_TOKEN = os.getenv("CESIUM_ION_TOKEN")

BASE_DIR = Path(__file__).resolve().parent

# -----------------------------------------------------------------------------
# 2. FastAPI & Model Initialization
# -----------------------------------------------------------------------------
app = FastAPI(title="Spatial Twin Intelligence Pipeline", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Depth Engine (Perception Layer loaded once into RTX 4070 VRAM)
depth_engine = DepthEngine()

# -----------------------------------------------------------------------------
# 3. Request Schemas
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
# 4. API Endpoints
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
    print(f"\n[Pipeline Triggered] Mode: {req.telemetry.tile_mode} | Pitch: {req.telemetry.pitch:.1f}° | Time: {req.temporal_anchor}")

    # 1. Reverse Geocode Coordinates
    address = reverse_geocode(req.telemetry.latitude, req.telemetry.longitude, GOOGLE_MAPS_API_KEY)
    print(f"[Resolved Address]: {address}")

    # 2. PERCEPTION: Run Depth Anything V2 on the Viewport Capture
    raw_b64 = req.screenshot.split(",")[-1] if "," in req.screenshot else req.screenshot
    viewport_pil = Image.open(io.BytesIO(base64.b64decode(raw_b64))).convert("RGB")
    depth_result = depth_engine.estimate(viewport_pil)
    print(f"[Depth Perception Complete] Latency: {depth_result.latency_ms:.1f}ms on {depth_result.device}")

    # 3. REASONING: Cognitive Reasoning & 4D GeoJSON Scaffold
    geojson_data, prompt, spatial_mode = query_the_eye(
        address=address,
        telemetry=req.telemetry,
        screenshot_b64=req.screenshot,
        temporal_anchor=req.temporal_anchor,
        gemini_api_key=GEMINI_API_KEY
    )
    print(f"[The Eye Complete] Mode: {spatial_mode}")

    # 4. SYNTHESIS: Generative Twin Image Synthesis
    twin_image_b64 = synthesize_twin_image(
        prompt=prompt,
        screenshot_b64=req.screenshot,
        spatial_mode=spatial_mode,
        telemetry=req.telemetry,
        geojson_data=geojson_data,
        gemini_api_key=GEMINI_API_KEY
    )
    print("[Synthesis Complete] Image generated.")

    # 5. ARCHIVE: Save All 6 Run Artifacts
    archive_folder = archive_run(
        address=address,
        telemetry=req.telemetry,
        spatial_mode=spatial_mode,
        temporal_anchor=req.temporal_anchor,
        screenshot_b64=req.screenshot,
        synthesized_b64=twin_image_b64,
        geojson_data=geojson_data,
        prompt=prompt,
        depth_image=depth_result.depth_image  # <-- Artifact #6
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
# 5. Static File Serving (HUD Viewport)
# -----------------------------------------------------------------------------
if (BASE_DIR / "viewfinder.html").exists():
    @app.get("/")
    def serve_index():
        return FileResponse(BASE_DIR / "viewfinder.html")

app.mount("/", StaticFiles(directory=str(BASE_DIR)), name="static")