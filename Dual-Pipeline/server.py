"""
Server: FastAPI Orchestration Endpoint for the Spatial Intelligence Pipeline.
Linear execution: Viewport Ingest -> Cognitive Engine (The 4 Mothers) -> Lighting Engine (NOAA & Weather)
-> Prompt Compiler (Adapter) -> Synthesis Engine -> Archiver.
"""

import os
import time
from typing import Dict, Any, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Environment loader
env_path = Path(r"C:\DEV\Squid\SquidBlack\.env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[Server] Loaded environment from: {env_path}")
else:
    load_dotenv()
    print("[Server] Loaded environment from local directory .env")

# Internal modules
from cognitive_engine import query_the_eye, reverse_geocode
from lighting_engine import resolve_lighting_state, get_live_weather
from prompt_compiler import compile_conditioning
from synthesis_engine import synthesize_twin_image
from archiver import archive_run

app = FastAPI(
    title="Spatial Intelligence Pipeline API",
    description="Multimodal spatial cognition, deterministic lighting, and dynamic documentary twin synthesis.",
    version="4.1.0"
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
    """Serves non-secret tokens to the frontend."""
    cesium_token = (
        os.getenv("CESIUM_ION_TOKEN")
        or os.getenv("CESIUM_TOKEN")
        or os.getenv("CESIUM_ION_ACCESS_TOKEN")
        or ""
    )
    return {"cesium_ion_token": cesium_token}


@app.get("/api/weather")
async def get_weather(lat: float = Query(...), lon: float = Query(...)):
    """Fetches real-time live weather for the given coordinates."""
    return get_live_weather(lat, lon)


@app.get("/api/geocode")
async def get_geocode(lat: float = Query(...), lon: float = Query(...)):
    """Resolves coordinates into a human-readable postal address or locality."""
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    address = reverse_geocode(lat, lon, google_maps_key)
    return {"address": address}

# -------------------------------------------------------------------------
# Telemetry and Request Schemas
# -------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    latitude: float = Field(..., description="WGS84 Latitude")
    longitude: float = Field(..., description="WGS84 Longitude")
    altitude_agl: float = Field(0.0, description="Altitude AGL in meters")
    heading: float = Field(0.0, description="Camera Heading (degrees)")
    pitch: float = Field(-45.0, description="Camera Pitch (degrees)")
    fov: float = Field(45.0, description="Camera FOV (degrees)")
    tile_mode: str = Field("3D_TILES", description="3D_TILES or 2D_SATELLITE")
    date: Optional[str] = Field(None, description="YYYY-MM-DD date")
    time_of_day: Optional[float] = Field(None, description="24-hour decimal time (e.g. 14.5 = 14:30)")
    timestamp_utc: Optional[str] = Field(None, description="ISO 8601 UTC timestamp")
    lighting_mode: str = Field("SOLAR", description="SOLAR or FLOODLIGHT")
    weather_mode: str = Field("AUTO", description="AUTO, SUNNY, RAIN, FOG, SNOW, OVERCAST")


class ProcessViewRequest(BaseModel):
    screenshot_b64: str = Field(..., description="Base64 encoded JPEG viewport capture")
    telemetry: TelemetryPayload
    address: Optional[str] = Field(None, description="Optional pre-resolved address")


# -------------------------------------------------------------------------
# Main Pipeline Endpoint (/api/process_view)
# -------------------------------------------------------------------------
@app.post("/api/process_view")
async def process_view(request: ProcessViewRequest):
    pipeline_start = time.perf_counter()
    telemetry = request.telemetry
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if not gemini_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured in .env.")

    print("\n" + "=" * 65)
    print(f"[Pipeline Ingest] Target: ({telemetry.latitude:.5f}, {telemetry.longitude:.5f}) | Mode: {telemetry.tile_mode}")

    # 1. Address Resolution
    address = request.address
    if not address:
        address = reverse_geocode(telemetry.latitude, telemetry.longitude, google_maps_key)
    print(f"[Pipeline Ingest] Resolved Address: {address}")

    # 2. Stage 1: Cognitive Engine (Pure Structural Cognition)
    t0 = time.perf_counter()
    print("[Pipeline Stage 1/4] Querying Cognitive Engine (Gemini 3.7 Flash: 4 Mothers)...")
    cog_result = query_the_eye(
        address=address,
        telemetry=telemetry,
        screenshot_b64=request.screenshot_b64,
        gemini_api_key=gemini_key
    )
    print(f"[Pipeline Stage 1/4] Complete in {(time.perf_counter() - t0):.2f}s | Spatial Mode: {cog_result.spatial_mode}")

    # 3. Stage 2: Lighting & Atmospheric Physics
    t1 = time.perf_counter()
    print(f"[Pipeline Stage 2/4] Resolving Lighting ({telemetry.lighting_mode}) & Weather ({telemetry.weather_mode})...")
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
    print(f"[Pipeline Stage 2/4] Complete in {(time.perf_counter() - t1):.2f}s | Active Weather: {lighting_state.weather_mode}")

    # 4. Stage 3: Prompt Compiler Adapter
    compiled = compile_conditioning(
        cognitive_result=cog_result,
        lighting_state=lighting_state,
        telemetry=telemetry,
        target_model="gemini-3.1-flash-image"
    )
    print(f"[Pipeline Stage 3/4] Compiled Conditioning ({compiled.metadata['word_count']} words, Temp: {compiled.temperature})")

    # 5. Stage 4: Multimodal Synthesis Engine
    t2 = time.perf_counter()
    print(f"[Pipeline Stage 4/4] Dispatching to Synthesis Engine ({compiled.model_name})...")
    synthesis = synthesize_twin_image(
        conditioning=compiled,
        screenshot_b64=request.screenshot_b64,
        gemini_api_key=gemini_key
    )
    print(f"[Pipeline Stage 4/4] Synthesis Complete in {(time.perf_counter() - t2):.2f}s")

    total_latency_ms = (time.perf_counter() - pipeline_start) * 1000.0

    # 6. Persistence & Archive
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
        print(f"[Archiver Warning]: {e}")
        run_record = {"status": "unarchived", "error": str(e)}

    print(f"[Pipeline Complete] Total Pipeline Latency: {total_latency_ms:.1f} ms")
    print("=" * 65 + "\n")

    return {
        "status": "success",
        "spatial_mode": cog_result.spatial_mode,
        "address": address,
        "lighting_mode": telemetry.lighting_mode,
        "weather_mode": lighting_state.weather_mode,
        "lighting_state": lighting_state.to_dict(),
        "distilled_prompt": cog_result.distilled_prompt,
        "compiled_prompt": compiled.prompt,
        "twin_image_b64": synthesis.image_b64,
        "geojson": compiled.full_geojson,
        "latency_ms": round(total_latency_ms, 1),
        "run_record": run_record
    }


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