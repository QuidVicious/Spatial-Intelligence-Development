"""
Archiver Module: Persists all spatial twin pipeline run artifacts.
Writes timestamped folders with viewport captures, synthesized twins, GeoJSON scaffolds, and run metadata.
"""

import os
import re
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from cognitive_engine import CognitiveResult
from prompt_compiler import CompiledConditioning
from synthesis_engine import SynthesisResult

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = BASE_DIR / "spatial_twin_runs"


def slugify_address(address: str, max_len: int = 35) -> str:
    """Creates a clean, filesystem-safe folder name from an address."""
    clean = re.sub(r"[^\w\s-]", "", address).strip()
    clean = re.sub(r"[\s-]+", "_", clean)
    return clean[:max_len].strip("_") or "spatial_twin"


def archive_run(
    telemetry: Any,
    cognitive_result: CognitiveResult,
    conditioning: CompiledConditioning,
    synthesis_result: SynthesisResult,
    screenshot_b64: str,
    runs_dir: Optional[Path] = None
) -> str:
    """
    Saves the 4 core artifacts:
    1. viewport_capture.jpg
    2. spatial_twin.png
    3. spatial_twin_scaffold.geojson
    4. run_metadata.json
    """
    target_dir = runs_dir or DEFAULT_RUNS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    addr_slug = slugify_address(cognitive_result.address)
    run_folder = target_dir / f"{addr_slug}_{timestamp}"
    run_folder.mkdir(parents=True, exist_ok=True)

    # 1. Save Raw Viewport Capture (JPG)
    raw_viewport_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    viewport_path = run_folder / "viewport_capture.jpg"
    with open(viewport_path, "wb") as f:
        f.write(base64.b64decode(raw_viewport_b64))

    # 2. Save Synthesized Spatial Twin (PNG)
    raw_synth_b64 = synthesis_result.image_b64.split(",")[-1] if "," in synthesis_result.image_b64 else synthesis_result.image_b64
    twin_path = run_folder / "spatial_twin.png"
    with open(twin_path, "wb") as f:
        f.write(base64.b64decode(raw_synth_b64))

    # 3. Save RFC 7946 GeoJSON Database (including Stratum 7)
    geojson_path = run_folder / "spatial_twin_scaffold.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(conditioning.full_geojson, f, indent=2)

    # 4. Save Run Metadata (JSON)
    metadata = {
        "timestamp": timestamp,
        "address": cognitive_result.address,
        "spatial_mode": cognitive_result.spatial_mode,
        "telemetry": {
            "latitude": getattr(telemetry, "latitude", 0.0),
            "longitude": getattr(telemetry, "longitude", 0.0),
            "altitude_agl": getattr(telemetry, "altitude_agl", 0.0),
            "heading": getattr(telemetry, "heading", 0.0),
            "pitch": getattr(telemetry, "pitch", 0.0),
            "fov": getattr(telemetry, "fov", 0.0),
            "tile_mode": getattr(telemetry, "tile_mode", "3D_TILES"),
            "date": getattr(telemetry, "date", None),
            "time_of_day": getattr(telemetry, "time_of_day", None),
            "lighting_mode": getattr(telemetry, "lighting_mode", "SOLAR"),
            "weather_mode": getattr(telemetry, "weather_mode", "AUTO")
        },
        "lighting_and_weather_summary": conditioning.metadata.get("lighting_summary"),
        "distilled_structural_prompt": cognitive_result.distilled_prompt,
        "compiled_prompt": conditioning.prompt,
        "word_count": conditioning.metadata.get("word_count", 0),
        "synthesis": {
            "model_name": synthesis_result.model_name,
            "latency_ms": round(synthesis_result.latency_ms, 2)
        }
    }

    meta_path = run_folder / "run_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[Archiver] Run persisted to: {run_folder.resolve()}")
    return str(run_folder.resolve())


# Backward-compatibility alias
persist_run = archive_run