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
import time
import traceback
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
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
from domain_engine import analyze_spatial_domain, reverse_geocode, ViewScope
from lighting_engine import resolve_lighting_state, get_live_weather
from spatial_scaffold_engine import build_spatial_scaffold
from prompt_engine import compile_conditioning
from vision_preprocessor import delight_image
from synthesis_engine import synthesize_twin
from archiver import archive_run

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
    tile_mode: str = Field("3D_TILES", description="3D_TILES, 2D_SATELLITE, or STANDALONE")
    date: Optional[str] = Field(None, description="YYYY-MM-DD date")
    time_of_day: Optional[float] = Field(None, description="24-hour decimal time (e.g. 14.5 = 14:30)")
    timestamp_utc: Optional[str] = Field(None, description="ISO 8601 UTC timestamp")
    lighting_mode: str = Field("SOLAR", description="SOLAR or FLOODLIGHT")
    weather_mode: str = Field("AUTO", description="AUTO, SUNNY, RAIN, FOG, SNOW, OVERCAST")


class ProcessViewRequest(BaseModel):
    screenshot_b64: Optional[str] = Field(None, description="Optional Base64 encoded viewport capture")
    multi_view_images: Optional[List[str]] = Field(None, description="Optional list of Base64 or URLs for multi-view synthesis")
    telemetry: TelemetryPayload
    address: Optional[str] = Field(None, description="Optional pre-resolved address")
    provider: str = Field("GEMINI", description="GEMINI or WORLD_LABS")
    target_model: Optional[str] = Field(None, description="Model SKU (e.g. gemini-3.1-flash-image, marble-1.1)")
    view_scope: str = Field("FRUSTUM", description="FRUSTUM, OMNI_360, or STANDALONE")
    disable_recaption: bool = Field(True, description="Enforce original prompt without API auto-rewrite")


# -------------------------------------------------------------------------
# Streaming Pipeline Generator
# -------------------------------------------------------------------------
async def execute_pipeline_stream(request: ProcessViewRequest):
    pipeline_start = time.perf_counter()
    telemetry = request.telemetry
    google_maps_key = os.getenv("GOOGLE_MAPS_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    world_labs_key = os.getenv("WORLD_LABS_API_KEY") or os.getenv("WLT_API_KEY")

    emit_terminal_banner(
        f"Target: ({telemetry.latitude:.5f}, {telemetry.longitude:.5f}) | Date: {telemetry.date or 'Live'} | Scope: {request.view_scope}"
    )

    try:
        # 1. Address Resolution & Ephemeris
        stage, event_str = stage_activate(PipelineStage.INGEST_LIGHTING, f"Target: ({telemetry.latitude:.5f}, {telemetry.longitude:.5f})")
        yield event_str

        address = request.address or reverse_geocode(telemetry.latitude, telemetry.longitude, google_maps_key)
        yield stage.processing(f"Resolved Address: {address} | Calculating NOAA Solar Math...")

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

        yield stage.processing("Executing 4 Mothers Grounding (Geology, Geography, Architecture, Civil Records & Botanical Phenology)...")
        scope = ViewScope(request.view_scope.upper()) if request.view_scope in ViewScope.__members__ else ViewScope.FRUSTUM

        domain_result = analyze_spatial_domain(
            address=address,
            coordinates=(telemetry.latitude, telemetry.longitude),
            view_scope=scope,
            telemetry=telemetry,
            screenshot_b64=request.screenshot_b64,
            temporal_epoch=telemetry.date,
            gemini_api_key=gemini_key
        )
        yield stage.dispatching(f"Documentary prompt synthesized ({len(domain_result.documentary_prompt)} chars)")
        yield stage.finish(f"Domain analysis verified with Search Grounding")

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
        compiled = compile_conditioning(
            domain_result=domain_result,
            lighting_state=lighting_state,
            target_provider=request.provider,
            target_model=request.target_model
        )
        user_chars = compiled.metadata.get("user_prompt_chars", len(compiled.user_prompt))
        yield stage.dispatching(f"Conditioning compiled: System ({compiled.metadata.get('system_contract_chars', 0)} chars), User ({user_chars} chars)")
        yield stage.finish(f"Conditioning compiled for {compiled.target_model}")

        # 5. Vision Preprocessor (CUDA Delighting)
        stage, event_str = stage_activate(PipelineStage.VISION_PREPROCESSOR, "Guided filter albedo extraction")
        yield event_str

        yield stage.processing("Pushing viewport frame to PyTorch CUDA -> Delighting...")
        delighted_b64 = delight_image(request.screenshot_b64) if request.screenshot_b64 else None
        yield stage.dispatching("Edge-preserved albedo tensor extracted")
        yield stage.finish("Albedo delighting complete")

        # 6. Synthesis Engine
        stage, event_str = stage_activate(PipelineStage.SYNTHESIS_ENGINE, f"Model: {compiled.target_provider} / {compiled.target_model}")
        yield event_str

        yield stage.processing(f"Generating 2560x1440 2K QHD visual twin via {compiled.target_provider}...")
        # Direct handoff of CompiledPrompt enables systemInstruction / user_prompt separation
        synthesis = synthesize_twin(
            prompt=compiled,
            provider=compiled.target_provider,
            model_name=compiled.target_model,
            screenshot_b64=delighted_b64,
            multi_view_images=request.multi_view_images,
            disable_recaption=request.disable_recaption,
            gemini_api_key=gemini_key,
            world_labs_api_key=world_labs_key
        )
        yield stage.dispatching("Twin artifact received")
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
                delighted_b64=delighted_b64
            )
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
                "splat_url": synthesis.splat_url,
                "collider_mesh_url": synthesis.collider_mesh_url,
                "pano_url": synthesis.pano_url,
                "geojson": scaffold.to_geojson(),
                "latency_ms": round(total_latency_ms, 1),
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