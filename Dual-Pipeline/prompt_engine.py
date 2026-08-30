"""
System Prompt Engine: Deterministic conditioning compiler and budget manager.
Merges the 4 Mothers causal domain prompt with NOAA lighting overrides,
injects the strict Structural Decoupling, Geometry Rectification, Botanical Phenology,
and Static Decluttering Contracts into a single monolithic imperative payload.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class CompiledPrompt:
    """Strongly typed output contract for the final synthesized prompt."""
    prompt: str
    target_provider: str
    target_model: str
    system_instruction: str = ""
    user_prompt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


def _build_task_header(botanical_ecology: str) -> str:
    """Builds the primary imperative reconstruction contract."""
    eco_clause = botanical_ecology.strip() if botanical_ecology else "Enforce true seasonal canopy state matching the target date."
    
    return (
        "[TASK: 2560x1440 2K QHD 16:9 ARCHITECTURAL RELIGHTING & STATIC RECONSTRUCTION]\n"
        "Transform the reference photogrammetry plate into a razor-sharp, photorealistic 6x7 medium-format architectural survey photograph.\n\n"
        "MANDATORY TRANSFORMATION RULES:\n"
        "1. PLANAR RECTIFICATION & GEOMETRY LOCK: Treat the reference image as an immutable spatial coordinate frame. Eliminate all 3D mesh polygon wobble, melted facades, and distorted rooflines. Plumb all vertical walls to true gravity vertical. Render razor-sharp ashlar courses, straight timber sash mullions, and crisp slate roofs.\n"
        "2. STATIC DECLUTTERING (MANDATORY): COMPLETELY ERASE all transient vehicles, parked cars, delivery vans, pedestrians, and temporary street clutter from the seed image. Repaint the carriageway with authentic road surfacing, stone setts, whinstone kerbs, and clean flagstone pavements.\n"
        "3. BOTANICAL PHENOLOGY & CANOPY INTEGRITY: Overwrite all raw 3D mesh blob foliage with authentic seasonal canopy structures matching the target date. Zero green summer foliage during dormant/autumn/winter periods:\n"
        f"   {eco_clause}\n"
        "4. OPTICAL DEPTH: Pin-sharp infinite depth of field (f/11). Zero lens blur, tilt-shift, or depth-of-field falloff across foreground and background."
    )


def compile_conditioning(
    domain_result: Any, 
    lighting_state: Any, 
    target_provider: str = "GEMINI", 
    target_model: Optional[str] = None
) -> CompiledPrompt:
    
    doc_prompt = getattr(domain_result, "documentary_prompt", "").strip()
    if not doc_prompt:
        doc_prompt = "Documentary-grade architectural survey with authentic regional lithics, intact fenestration grids, and planar vertical rectification."

    botanical_text = getattr(domain_result, "botanical_ecology", "").strip()
    light_directive = getattr(lighting_state, "prompt_directive", "Clear sky daylight with natural directional illumination.").strip()
    
    task_header = _build_task_header(botanical_text)
    lighting_block = f"[SOLAR & ATMOSPHERIC LIGHTING OVERRIDE]\n{light_directive}"
    
    max_doc_len = 2500
    if len(doc_prompt) > max_doc_len:
        sliced_doc = doc_prompt[:max_doc_len]
        last_period = max(sliced_doc.rfind(". "), sliced_doc.rfind(".\n"), sliced_doc.rfind("."))
        if last_period > 200:
            doc_prompt = sliced_doc[:last_period + 1]
        else:
            doc_prompt = sliced_doc.rstrip() + "..."
            
    scene_block = f"[SCENE GEOMETRY & AUTHENTIC LITHICS]\n{doc_prompt}"

    full_prompt = (
        f"{task_header}\n\n"
        f"{lighting_block}\n\n"
        f"{scene_block}"
    ).strip()

    provider = target_provider.upper()
    if not target_model:
        model = "marble-1.1-plus" if provider == "WORLD_LABS" else "gemini-3.1-flash-image"
    else:
        model = target_model

    return CompiledPrompt(
        prompt=full_prompt,
        system_instruction="",
        user_prompt=full_prompt,
        target_provider=provider,
        target_model=model,
        metadata={
            "final_char_count": len(full_prompt),
            "doc_length": len(doc_prompt),
            "has_botanical_phenology": bool(botanical_text)
        }
    )