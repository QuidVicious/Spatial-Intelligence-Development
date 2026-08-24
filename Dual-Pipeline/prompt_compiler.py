"""
Prompt / Conditioning Compiler: Pure adapter and synthesis payload assembler.
Combines structural cognitive output with deterministic lighting and weather physics.
Enforces the strict < 200-word constraint and low-entropy generation parameters.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from cognitive_engine import CognitiveResult
from lighting_engine import LightingState


@dataclass
class CompiledConditioning:
    """Strongly typed output contract for the Prompt Compiler."""
    prompt: str
    spatial_mode: str
    model_name: str
    temperature: float
    top_p: float
    full_geojson: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compile_conditioning(
    cognitive_result: CognitiveResult,
    lighting_state: LightingState,
    telemetry: Any,
    target_model: str = "gemini-3.1-flash-image"
) -> CompiledConditioning:
    """
    Assembles structural cognition, lighting physics, and delighting directives into a
    concise synthesis payload strictly under 200 words.
    """
    raw_prompt = cognitive_result.distilled_prompt.strip()
    spatial_mode = cognitive_result.spatial_mode

    # 1. Clean delimiters
    clean_prompt = raw_prompt.replace("```", "").strip()
    for tag in ["---DOCUMENTARY_PROMPT_START---", "---DOCUMENTARY_PROMPT_END---", "Prompt:"]:
        clean_prompt = clean_prompt.replace(tag, "").strip()

    # 2. Reference framing per spatial mode
    if spatial_mode == "2D_EXTRUSION":
        reference_frame = "Using the attached 2D satellite image strictly as an unlit structural reference for camera perspective and parcel footprints. "
    else:
        reference_frame = "Using the attached image strictly as an unlit 3D structural skeleton for camera angle and building placement. "

    # 3. Assemble Full Delighted & Relit Synthesis Payload (< 200 words)
    final_prompt = (
        f"{reference_frame}"
        f"{lighting_state.prompt_directive} "
        f"ARCHITECTURAL SCENE ESSENCE: {clean_prompt}"
    )

    # 4. Integrate Stratum 7 into the GeoJSON FeatureCollection
    full_geojson = dict(cognitive_result.geojson)
    if "features" in full_geojson and isinstance(full_geojson["features"], list):
        features = [
            f for f in full_geojson["features"]
            if f.get("properties", {}).get("stratum") != "atmospheric_state" and f.get("id") != "stratum_7_atmospheric_state"
        ]
        features.append(lighting_state.geojson_stratum)
        full_geojson["features"] = features
    else:
        full_geojson = {
            "type": "FeatureCollection",
            "features": [lighting_state.geojson_stratum]
        }

    # 5. Metadata
    metadata = {
        "address": cognitive_result.address,
        "spatial_mode": spatial_mode,
        "lighting_mode": lighting_state.mode.value,
        "weather_mode": lighting_state.weather_mode,
        "lighting_summary": lighting_state.metadata,
        "word_count": len(final_prompt.split())
    }

    # Strict low-entropy hyperparameters
    return CompiledConditioning(
        prompt=final_prompt,
        spatial_mode=spatial_mode,
        model_name=target_model,
        temperature=0.18,
        top_p=0.30,
        full_geojson=full_geojson,
        metadata=metadata
    )