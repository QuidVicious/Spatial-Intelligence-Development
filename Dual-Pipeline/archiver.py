"""
Archiver Module: Persists all spatial twin pipeline run artifacts.
Writes timestamped folders with viewport captures, synthesized twins (2D PNG or 3D World Manifest),
GeoJSON scaffolds (Strata 1-7), domain analysis, and run metadata.
"""

import os
import re
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from domain_engine import DomainAnalysisResult
from spatial_scaffold_engine import SpatialScaffold
from prompt_engine import CompiledPrompt
from synthesis_engine import SynthesisResult, ModelProvider

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = BASE_DIR / "spatial_twin_runs"


def slugify_address(address: str, max_len: int = 35) -> str:
    """Creates a clean, filesystem-safe folder name from an address."""
    clean = re.sub(r"[^\w\s-]", "", address).strip()
    clean = re.sub(r"[\s-]+", "_", clean)
    return clean[:max_len].strip("_") or "spatial_twin"


def archive_run(
    telemetry: Any,
    domain_result: DomainAnalysisResult,
    scaffold: SpatialScaffold,
    conditioning: CompiledPrompt,
    synthesis_result: SynthesisResult,
    screenshot_b64: Optional[str] = None,
    runs_dir: Optional[Path] = None
) -> str:
    """
    Saves the core pipeline artifacts:
    1. viewport_capture.jpg (if present)
    2. spatial_twin.png (or 3D World manifest / thumbnail)
    3. spatial_twin_scaffold.geojson (RFC 7946 Strata 1-7)
    4. domain_analysis.md (full causal analysis)
    5. run_metadata.json
    """
    target_dir = runs_dir or DEFAULT_RUNS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    addr_slug = slugify_address(domain_result.address)
    run_folder = target_dir / f"{addr_slug}_{timestamp}"
    run_folder.mkdir(parents=True, exist_ok=True)

    # 1. Save Raw Viewport Capture (if available)
    if screenshot_b64:
        raw_viewport_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
        viewport_path = run_folder / "viewport_capture.jpg"
        with open(viewport_path, "wb") as f:
            f.write(base64.b64decode(raw_viewport_b64))

    # 2. Save Synthesized Visual Twin Artifact
    if synthesis_result.image_b64:
        raw_synth_b64 = synthesis_result.image_b64.split(",")[-1] if "," in synthesis_result.image_b64 else synthesis_result.image_b64
        twin_path = run_folder / "spatial_twin.png"
        with open(twin_path, "wb") as f:
            f.write(base64.b64decode(raw_synth_b64))

    # If 3D World (World Labs Marble), save world manifest
    if synthesis_result.provider == ModelProvider.WORLD_LABS:
        world_manifest = {
            "world_id": synthesis_result.world_id,
            "viewer_url": synthesis_result.world_viewer_url,
            "splat_url": synthesis_result.splat_url,
            "collider_mesh_url": synthesis_result.collider_mesh_url,
            "pano_url": synthesis_result.pano_url,
            "raw_response": synthesis_result.raw_response
        }
        manifest_path = run_folder / "world_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(world_manifest, f, indent=2)

    # 3. Save RFC 7946 7-Strata GeoJSON Database
    geojson_path = run_folder / "spatial_twin_scaffold.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(scaffold.to_geojson(), f, indent=2)

    # 4. Save Full Domain Analysis Markdown
    domain_md_path = run_folder / "domain_analysis.md"
    with open(domain_md_path, "w", encoding="utf-8") as f:
        f.write(f"# Spatial Domain Analysis: {domain_result.address}\n\n")
        f.write(f"**View Scope:** {domain_result.view_scope.value}\n\n")
        f.write(f"## 1. Geology & Indigenous Lithics\n{domain_result.geological_foundation}\n\n")
        f.write(f"## 2. Architecture & Planar Rectification\n{domain_result.architectural_analysis}\n\n")
        f.write(f"## 3. Materials & Environmental Patina\n{domain_result.material_and_lithics}\n\n")
        f.write(f"## 4. Landscape Ecology & Botanical Canopy\n{domain_result.botanical_ecology}\n\n")
        f.write(f"## 5. Static Civil Fabric Decluttering\n{domain_result.static_decluttering_summary}\n\n")
        f.write(f"## 6. Synthesized Documentary Prompt\n```text\n{domain_result.documentary_prompt}\n```\n")

    # 5. Save Run Metadata (JSON)
    metadata = {
        "timestamp": timestamp,
        "address": domain_result.address,
        "view_scope": domain_result.view_scope.value,
        "provider": synthesis_result.provider.value,
        "model_name": synthesis_result.model_name,
        "latency_ms": round(synthesis_result.latency_ms, 2),
        "telemetry": {
            "latitude": getattr(telemetry, "latitude", 0.0),
            "longitude": getattr(telemetry, "longitude", 0.0),
            "altitude_agl": getattr(telemetry, "altitude_agl", 0.0),
            "heading": getattr(telemetry, "heading", 0.0),
            "pitch": getattr(telemetry, "pitch", 0.0),
            "fov": getattr(telemetry, "fov", 0.0),
            "tile_mode": getattr(telemetry, "tile_mode", "3D_TILES")
        },
        "compiled_prompt": conditioning.prompt,
        "word_count": conditioning.metadata.get("word_count", 0),
        "includes_lighting": conditioning.metadata.get("includes_lighting", False)
    }

    meta_path = run_folder / "run_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[Archiver] Run persisted to: {run_folder.resolve()}")
    return str(run_folder.resolve())