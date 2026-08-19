"""
Archiver Module: Handles the isolated recording and persistence of all 6 spatial twin artifacts.
"""
import os
import re
import json
import base64
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
RUNS_DIR = BASE_DIR / "spatial_twin_runs"
RUNS_DIR.mkdir(parents=True, exist_ok=True)


def archive_run(
    address: str,
    telemetry: Any,
    spatial_mode: str,
    temporal_anchor: str,
    screenshot_b64: str,
    synthesized_b64: str,
    geojson_data: Dict[str, Any],
    prompt: str,
    depth_image: Optional[Union[Image.Image, str]] = None,
) -> str:
    """Saves all 6 pipeline artifacts into an isolated timestamped folder."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_addr = re.sub(r'[^a-zA-Z0-9_-]', '_', address)[:35].strip('_')
    folder_name = f"{clean_addr}_{timestamp}"
    run_path = RUNS_DIR / folder_name
    run_path.mkdir(parents=True, exist_ok=True)

    # 1. Viewport Capture JPG
    raw_viewport = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    (run_path / "viewport_capture.jpg").write_bytes(base64.b64decode(raw_viewport))

    # 2. Depth Map PNG (Artifact #6)
    if depth_image is not None:
        if isinstance(depth_image, Image.Image):
            depth_image.save(run_path / "depth_map.png")
        elif isinstance(depth_image, str):
            raw_depth = depth_image.split(",")[-1] if "," in depth_image else depth_image
            (run_path / "depth_map.png").write_bytes(base64.b64decode(raw_depth))

    # 3. Synthesized Twin Image PNG
    raw_synth = synthesized_b64.split(",")[-1] if "," in synthesized_b64 else synthesized_b64
    (run_path / "synthesized_twin.png").write_bytes(base64.b64decode(raw_synth))

    # 4. GeoJSON Spatial Scaffold
    (run_path / "spatial_scaffold.json").write_text(json.dumps(geojson_data, indent=2), encoding="utf-8")

    # 5. Documentary Synthesis Prompt
    (run_path / "prompt.txt").write_text(prompt, encoding="utf-8")

    # 6. Telemetry & Run Metadata
    telemetry_dict = telemetry.dict() if hasattr(telemetry, "dict") else telemetry
    meta = {
        "timestamp": timestamp,
        "resolved_address": address,
        "spatial_mode": spatial_mode,
        "temporal_anchor": temporal_anchor,
        "telemetry": telemetry_dict
    }
    (run_path / "telemetry_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"[Archiver] Successfully saved 6 artifacts to: {run_path}")
    return folder_name