"""
Server: FastAPI Orchestration Endpoint for the Spatial Intelligence Pipeline.
Linear execution: Viewport Ingest -> Cognitive Engine (The 4 Mothers) -> Prompt Compiler (Delighting) -> Synthesis Engine -> Archiver.
"""

import os
import time
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# -------------------------------------------------------------------------
# Environment Configuration (.env Loader)
# -------------------------------------------------------------------------
env_path = Path(r"C:\DEV\Squid\SquidBlack\.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[Server] Loaded environment from: {env_path}")
else:
    load_dotenv()
    print("[Server] Loaded environment from local directory .env")

# Internal modules
from cognitive_engine import query_the_eye, reverse_geocode
from prompt_compiler import compile_conditioning
from synthesis_engine import synthesize_twin_image
from archiver import archive_run

app = FastAPI(
    title="Spatial Intelligence Pipeline API",
    description="Multimodal spatial cognition, delighting, and dynamic documentary twin synthesis.",
    version="4.0.0"
)

# CORS middleware for Cesium client HUD
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------------------
# Dynamic Client Config Endpoint (Reads Cesium Token from .env)
# -------------------------------------------------------------------------
@app.get("/api/config")
async def get_client_config():
    """Dynamically serves non-secret client tokens from .env to the frontend."""
    cesium_token = (
        os.getenv("CESIUM_ION_TOKEN")
        or os.getenv("CESIUM_TOKEN")
        or os.getenv("CESIUM_ION_ACCESS_TOKEN")
        or ""
    )
    return {
        "cesium_ion_token": cesium_token
    }


# -------------------------------------------------------------------------
# Telemetry and Request Schemas
# -------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude")
    longitude: float = Field(..., description="WGS84 Longitude")
    altitude_agl: float = Field(0.0, description="Altitude Above Ground Level (meters)")
    heading: float = Field(0.0, description="Camera Heading (degrees, 0=North)")
    pitch: float = Field(-45.0, description="Camera Pitch (degrees, -90=Down)")
    fov: float = Field(45.0, description="Camera Horizontal Field of View (degrees)")
    tile_mode: str = Field("3D_TILES", description="Rendering mode: 3D_TILES or 2D_SATELLITE")
    temporal_anchor: str = Field("Present Day", description="Historical epoch or temporal target")
    timestamp_utc: Optional[str] = Field(None, description="ISO 8601 UTC timestamp for solar ephemeris")
    lighting_mode: str = Field("SOLAR", description="Lighting rig mode: SOLAR or FLOODLIGHT")


class ProcessViewRequest(BaseModel):
    screenshot_b64: str = Field(..., description="Base64 encoded JPEG viewport capture")
    telemetry: TelemetryPayload
    address: Optional[str] = Field(None, description="Optional pre-resolved address")


# -------------------------------------------------------------------------
# Main Pipeline Endpoint (/api/process_view)
# -------------------------------------------------------------------------
@app.post("/api/process_view")
async def process_view(request: ProcessViewRequest):
    """
    Executes the 4-stage pipeline linearly:
    1. Reverse Geocode (if needed)
    2. Cognitive Engine (The 4 Mothers + Deterministic Lighting + GeoJSON)
    3. Prompt Compiler (Delighting Barrier + Dynamic Lighting Directive)
    4. Synthesis Engine (Gemini 3.1 Flash Image)
    5. Archiver & Persistence
    """
    pipeline_start = time.perf_counter()
    telemetry = request.telemetry
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured in .env.")

    # Step 1: Address Resolution
    address = request.address
    if not address:
        address = reverse_geocode(telemetry.latitude, telemetry.longitude, google_maps_key)

    # Step 2: Stage 1 - Cognitive Engine (The 4 Mothers + Lighting Rig)
    cog_result = query_the_eye(
        address=address,
        telemetry=telemetry,
        screenshot_b64=request.screenshot_b64,
        temporal_anchor=telemetry.temporal_anchor,
        gemini_api_key=gemini_key
    )

    # Step 3: Stage 2 - Prompt Compiler (Delighting & Dynamic Relighting Assembly)
    compiled = compile_conditioning(
        cognitive_result=cog_result,
        telemetry=telemetry,
        target_model="gemini-3.1-flash-image"
    )

    # Step 4: Stage 3 - Multimodal Synthesis Engine
    synthesis = synthesize_twin_image(
        conditioning=compiled,
        screenshot_b64=request.screenshot_b64,
        gemini_api_key=gemini_key
    )

    total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0

    # Step 5: Stage 4 - Archiver & Spatial Graph Persistence
    try:
        run_folder_path = archive_run(
            telemetry=telemetry,
            cognitive_result=cog_result,
            conditioning=compiled,
            synthesis_result=synthesis,
            screenshot_b64=request.screenshot_b64
        )
        run_record = {
            "status": "persisted",
            "path": run_folder_path,
            "total_latency_ms": round(total_latency_ms, 1)
        }
    except Exception as e:
        print(f"[Archiver Warning]: Failed to persist run: {e}")
        run_record = {"status": "unarchived", "error": str(e)}

    return {
        "status": "success",
        "spatial_mode": cog_result.spatial_mode,
        "address": address,
        "lighting_mode": telemetry.lighting_mode,
        "lighting_state": cog_result.lighting_state,
        "distilled_prompt": cog_result.distilled_prompt,
        "compiled_prompt": compiled.prompt,
        "twin_image_b64": synthesis.image_b64,
        "geojson": cog_result.geojson,
        "latency_ms": round(total_latency_ms, 1),
        "run_record": run_record
    }


# -------------------------------------------------------------------------
# Viewfinder Frontend Route & Static Assets
# -------------------------------------------------------------------------
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
    raise HTTPException(status_code=404, detail="viewfinder.html could not be located on disk.")


static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)