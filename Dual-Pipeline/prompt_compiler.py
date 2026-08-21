"""
Prompt / Conditioning Compiler: Deterministic adapter and delighting barrier.
Combines structured cognitive output with deterministic lighting physics (Solar or Floodlight),
enforces baked shadow cancellation, and packages generation hyperparameters for image synthesis.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from cognitive_engine import CognitiveResult
from lighting_engine import LightingState, LightingMode, resolve_lighting_state


@dataclass
class CompiledConditioning:
    """Strongly typed output contract for the Prompt Compiler."""
    prompt: str
    spatial_mode: str
    model_name: str
    temperature: float
    top_p: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compile_conditioning(
    cognitive_result: CognitiveResult,
    telemetry: Any,
    lighting_state: Optional[LightingState] = None,
    target_model: str = "gemini-3.1-flash-image"
) -> CompiledConditioning:
    """
    Compiles cognitive output and lighting physics into a clean synthesis payload.
    Enforces structural delighting (stripping baked sunlight/shadows) and dynamic relighting.
    """
    raw_prompt = cognitive_result.distilled_prompt.strip()
    spatial_mode = cognitive_result.spatial_mode

    # 1. Clean markdown or legacy delimiter leaks
    clean_prompt = raw_prompt.replace("```", "").strip()
    for tag in ["---DOCUMENTARY_PROMPT_START---", "---DOCUMENTARY_PROMPT_END---", "Prompt:"]:
        clean_prompt = clean_prompt.replace(tag, "").strip()

    # 2. Resolve Lighting State if not explicitly passed
    if lighting_state is None:
        lat = getattr(telemetry, "latitude", 0.0)
        lon = getattr(telemetry, "longitude", 0.0)
        heading = getattr(telemetry, "heading", 0.0)
        pitch = getattr(telemetry, "pitch", -45.0)
        ts_utc = getattr(telemetry, "timestamp_utc", None)
        mode = getattr(telemetry, "lighting_mode", "SOLAR")
        lighting_state = resolve_lighting_state(
            lat=lat,
            lon=lon,
            camera_heading=heading,
            camera_pitch=pitch,
            timestamp_utc=ts_utc,
            mode=mode
        )

    # 3. Dynamic Reference Framing & Delighting Barrier per spatial mode
    if spatial_mode == "2D_EXTRUSION":
        temperature = 0.20
        top_p = 0.70
        reference_frame = (
            "Using the attached 2D satellite footprint image strictly as an unlit structural reference "
            "for camera perspective and parcel massing placement. "
        )
    else:
        # 3D_RECTIFICATION
        temperature = 0.25
        top_p = 0.60
        reference_frame = (
            "Using the attached image strictly as an unlit 3D structural skeleton for camera angle, perspective, "
            "horizon line, and building placement. "
        )

    # 4. Assemble Full Delighted & Relit Synthesis Payload
    # [Structural Reference] + [Delighting & Relighting Directive] + [Architectural & Material Essence]
    final_prompt = (
        f"{reference_frame}"
        f"{lighting_state.prompt_directive} "
        f"ARCHITECTURAL SCENE ESSENCE: {clean_prompt}"
    )

    # 5. Metadata for audit trail & telemetry persistence
    metadata = {
        "address": cognitive_result.address,
        "spatial_mode": spatial_mode,
        "lighting_mode": lighting_state.mode.value,
        "lighting_summary": lighting_state.metadata,
        "pitch": getattr(telemetry, "pitch", -45.0),
        "heading": getattr(telemetry, "heading", 0.0),
        "fov": getattr(telemetry, "fov", 75.0),
        "word_count": len(final_prompt.split())
    }

    return CompiledConditioning(
        prompt=final_prompt,
        spatial_mode=spatial_mode,
        model_name=target_model,
        temperature=temperature,
        top_p=top_p,
        metadata=metadata
    )


# --- Standalone CLI Runner for Testing ---
if __name__ == "__main__":
    print("=" * 70)
    print("=== Prompt Compiler (Delighting & Relighting) Diagnostic ===")
    print("=" * 70)

    class MockTelemetry:
        latitude = 55.953492
        longitude = -3.211036
        altitude_agl = 4.5
        heading = 315.0
        pitch = -12.0
        fov = 75.0
        tile_mode = "3D_TILES"
        timestamp_utc = "2026-08-20T17:30:00Z"
        lighting_mode = "SOLAR"

    mock_cog_result = CognitiveResult(
        address="Ainslie Place, Edinburgh, Scotland",
        spatial_mode="3D_RECTIFICATION",
        geojson={"type": "FeatureCollection", "features": []},
        distilled_prompt=(
            "A 3-storey Craigleith sandstone Georgian crescent with plumb vertical facades, crisp sash windows, "
            "and level slate rooflines. Authentic honey ashlar masonry with subtle soot patina in reveals. "
            "Clean, static street completely free of pedestrians and vehicles."
        ),
        raw_response=""
    )

    # Test 1: Solar Relighting Payload
    compiled_solar = compile_conditioning(mock_cog_result, MockTelemetry())
    print("\n--- [TEST 1: COMPILED SOLAR SYNTHESIS PAYLOAD] ---")
    print(f"Word Count: {compiled_solar.metadata['word_count']}")
    print(f"Compiled Prompt:\n{compiled_solar.prompt}\n")

    # Test 2: Camera Night Floodlight Payload
    class MockFloodlightTelemetry(MockTelemetry):
        lighting_mode = "FLOODLIGHT"

    compiled_flood = compile_conditioning(mock_cog_result, MockFloodlightTelemetry())
    print("--- [TEST 2: COMPILED CAMERA FLOODLIGHT PAYLOAD] ---")
    print(f"Word Count: {compiled_flood.metadata['word_count']}")
    print(f"Compiled Prompt:\n{compiled_flood.prompt}\n")
    print("=" * 70)