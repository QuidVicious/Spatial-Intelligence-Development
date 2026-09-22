"""
System Prompt Engine: conditioning compiler with per-target renderers.

Two renderers, one per output target:

  GEMINI      screen-space 2D image. Photographic language, frame-relative
              lighting, and the rectification contract all belong here.
              UNCHANGED from the previous version.

  WORLD_LABS  volumetric world. No camera, no lens, no aspect ratio, no
              left/right screen references. Marble builds a space, not a
              photograph, so frame-relative instructions are meaningless
              to it and photographic vocabulary is actively misleading.

Domain output is scrubbed of photographic register before it reaches the
Marble renderer, because domain_engine's system instruction still carries
a photographer archetype (removed 2026-09-04) and older archives contain
camera-format phrases; the scrub below is kept as a safety net.
"""

import re
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


# =========================================================================
# GEMINI RENDERER  (unchanged)
# =========================================================================

def _build_task_header(eco_clause: str) -> str:
    """Builds the primary imperative reconstruction contract."""
    eco_clause = eco_clause.strip() or "Enforce true seasonal canopy state matching the target date."

    return (
        "[TASK: ARCHITECTURAL RELIGHTING & STATIC RECONSTRUCTION]\n"
        "Transform the reference photogrammetry plate into a razor-sharp, photorealistic architectural image.\n"
        "Keep the reference plate's exact composition: every edge, horizon line, and object position stays where it is.\n\n"
        "MANDATORY TRANSFORMATION RULES:\n"
        "1. PLANAR RECTIFICATION & GEOMETRY LOCK: Treat the reference image as an immutable spatial coordinate frame. Eliminate all 3D mesh polygon wobble, melted facades, and distorted rooflines. Plumb all vertical walls to true gravity vertical. Render the specific materials, coursing, window types, and roof forms named in the SCENE section below with sharp, correct detail.\n"
        "2. STATIC DECLUTTERING (MANDATORY): COMPLETELY ERASE all transient vehicles, parked cars, delivery vans, pedestrians, and temporary street clutter from the seed image. Repaint the ground plane with the authentic surfacing, kerbs, and pavement named in the SCENE section below.\n"
        "3. BOTANICAL PHENOLOGY & CANOPY INTEGRITY: Overwrite all raw 3D mesh blob foliage with authentic seasonal canopy structures matching the target date. Zero green summer foliage during dormant/autumn/winter periods:\n"
        f"   {eco_clause}\n"
        "4. OPTICAL DEPTH: Sharp focus across the entire frame, near to far. No blur, no depth-of-field falloff, no vignetting."
    )


def _render_gemini(domain_result: Any, lighting_state: Any, budget: int = 3200) -> Dict[str, Any]:
    """
    Budgeted assembly. The task header and the lighting block are fixed and
    reserved first; the remainder is shared between the botanical clause and
    the documentary prompt. Longer prompts appear to pull the model away from
    editing the seed and toward generating a fresh image, so total length is a
    tuning parameter rather than a safety limit.
    """
    doc_prompt = (getattr(domain_result, "documentary_prompt", "") or "").strip()
    if not doc_prompt:
        doc_prompt = "Documentary-grade architectural survey with authentic regional lithics, intact fenestration grids, and planar vertical rectification."
    botanical_text = (getattr(domain_result, "botanical_ecology", "") or "").strip()
    light_directive = (getattr(lighting_state, "prompt_directive", "Clear sky daylight with natural directional illumination.") or "").strip()

    lighting_block = f"[SOLAR & ATMOSPHERIC LIGHTING OVERRIDE]\n{light_directive}"
    skeleton = len(_build_task_header("")) + len(lighting_block) + len("[SCENE GEOMETRY & AUTHENTIC LITHICS]\n") + 6

    remaining = max(0, budget - skeleton)
    # documentary prompt carries the site, botany is supporting: 3 to 1
    eco_alloc = int(remaining * 0.25)
    doc_alloc = remaining - eco_alloc
    if len(botanical_text) < eco_alloc:
        doc_alloc += eco_alloc - len(botanical_text)
        eco_alloc = len(botanical_text)
    if len(doc_prompt) < doc_alloc:
        eco_alloc += doc_alloc - len(doc_prompt)
        doc_alloc = len(doc_prompt)

    eco_used = _trim_to(botanical_text, eco_alloc) if eco_alloc >= 40 else ""
    doc_used = _trim_to(doc_prompt, doc_alloc) if doc_alloc >= 60 else doc_prompt[:200]

    full_prompt = (
        f"{_build_task_header(eco_used)}\n\n"
        f"{lighting_block}\n\n"
        f"[SCENE GEOMETRY & AUTHENTIC LITHICS]\n{doc_used}"
    ).strip()

    return {
        "prompt": full_prompt,
        "metadata": {
            "renderer": "GEMINI",
            "final_char_count": len(full_prompt),
            "budget": budget,
            "over_budget": len(full_prompt) > budget,
            "skeleton_chars": skeleton,
            "doc_chars": len(doc_used),
            "doc_trimmed": len(doc_used) < len(doc_prompt),
            "eco_chars": len(eco_used),
            "eco_trimmed": len(eco_used) < len(botanical_text),
            "has_botanical_phenology": bool(eco_used)
        }
    }


# =========================================================================
# MARBLE RENDERER
# =========================================================================

# Photographic / frame-relative register that must not reach a world model.
_PHOTO_PATTERNS = [
    r"\b\d+\s*[xX×]\s*\d+\s*(?:medium[- ]format|format)?\b",      # 6x7, 4x5
    r"\bmedium[- ]format\b",
    r"\blarge[- ]format\b",
    r"\b35\s*mm\b",
    r"\bf/\d+(?:\.\d+)?\b",                                        # f/11
    r"\bdepth[- ]of[- ]field\b",
    r"\btilt[- ]shift\b",
    r"\blens\b",
    r"\bbokeh\b",
    r"\bshutter\b",
    r"\bISO\s*\d+\b",
    r"\bfilm grain\b",
    r"\bKodachrome\b",
    r"\bphotograph(?:y|ic|ed)?\b",
    r"\bphoto\b",
    r"\bcamera[- ]left\b",
    r"\bcamera[- ]right\b",
    r"\bleft (?:edge|side) of the frame\b",
    r"\bright (?:edge|side) of the frame\b",
    r"\bin[- ]frame\b",
    r"\bforeground\b",
    r"\bbackground\b",
    r"\bmidground\b",
    r"\baspect ratio\b",
    r"\b\d{3,4}\s*[xX×]\s*\d{3,4}\b",                              # 2560x1440
    r"\b(?:2K|4K|QHD|UHD)\b",
    r"\b16:9\b|\b9:16\b|\b4:3\b|\b3:2\b",
    r"\bedge[- ]to[- ]edge\b",
    r"\bpin[- ]sharp\b",
    r"\brazor[- ]sharp\b",
    r"\bdocumentary[- ]grade\b",
    r"\bsurvey photograph\b",
    r"\bultra[- ]fine grain\b",
    r"\bfilm clarity\b",
    r"\boptical resolution\b",
    r"\bfine grain\b",
    # pipeline-internal language: meaningless to a world model
    r"\bphotogrammetr(?:y|ic)\b",
    r"\b3D[- ]scan(?:ning)? distortions?\b",
    r"\bmesh (?:noise|wobble|distortion)\b",
    r"\bpolygon (?:wobble|artifacts?)\b",
    r"\bplanar rectification\b",
    r"\brectif(?:y|ied|ication)\b",
    r"\bdecluttering\b",
    r"\bseed image\b",
    r"\breference (?:image|plate)\b",
]
_PHOTO_RE = re.compile("|".join(_PHOTO_PATTERNS), re.IGNORECASE)


def scrub_photographic(text: str) -> str:
    """Strip camera, lens, and frame-relative language from domain prose."""
    if not text:
        return ""
    out = _PHOTO_RE.sub("", text)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"([,.;:])\1+", r"\1", out)
    out = re.sub(r"^[\s,.;:]+", "", out)

    # Drop sentences left as stubs by the substitutions above.
    kept = []
    for sent in re.split(r"(?<=[.!?])\s+", out):
        if len(sent.split()) >= 4:
            kept.append(sent.strip())
    return " ".join(kept).strip()


def _world_atmosphere(lighting_state: Any) -> str:
    """
    World-level illumination. Solar azimuth is a TRUE compass bearing and is
    therefore valid in a world; the screen-space directive (left walls lit,
    shadows to the RIGHT) is not, and is deliberately not used here.

    Direct sun and diffuse conditions are mutually exclusive: under overcast,
    fog, or rain there is no directional sun sentence at all.
    """
    meta = getattr(lighting_state, "metadata", {}) or {}
    az = meta.get("solar_azimuth")
    el = meta.get("solar_elevation")
    cct = meta.get("color_temperature_k")
    weather = str(meta.get("weather") or getattr(lighting_state, "weather_mode", "")).upper()

    diffuse = weather in ("OVERCAST", "FOG", "RAIN", "SNOW")
    bits = []

    if el is not None and el <= -6:
        bits.append("Night. No direct sunlight; ambient sky illumination only.")
    elif el is not None and el <= 0:
        bits.append("Civil twilight. No direct sun; diffuse ambient skylight and soft contact shadows.")
    elif diffuse:
        bits.append(
            "No direct sunlight and no hard cast shadows. Even, omnidirectional skylight from an "
            "overcast sky, with soft ambient occlusion under cornices, sills, and ledges."
        )
    elif el is not None and az is not None:
        bits.append(
            f"Direct sunlight from a true compass bearing of {az:.0f} degrees at {el:.1f} degrees "
            f"elevation above the horizon, casting hard shadows away from that bearing at a length "
            f"consistent with that sun elevation."
        )

    if cct:
        bits.append(f"Light colour temperature approximately {cct}K.")

    wx = {
        "SUNNY": "Clear sky.",
        "OVERCAST": "Fully overcast sky.",
        "RAIN": "Rain falling; wet reflective paving and darkened stone.",
        "FOG": "Ground mist and haze softening distant contrast.",
        "SNOW": "Snow lying on roofs, ledges, and pavement edges."
    }.get(weather)
    if wx:
        bits.append(wx)

    return " ".join(bits) if bits else "Overcast daylight."


def _trim_to(text: str, limit: int) -> str:
    """Trim at a sentence boundary, never mid-word."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "; ", ", "):
        i = cut.rfind(sep)
        if i > limit * 0.5:
            return cut[:i + 1].strip()
    i = cut.rfind(" ")
    return (cut[:i] if i > 0 else cut).strip()


def _flatten(text: str) -> str:
    """Markdown bullets and bold markers to plain prose."""
    if not text:
        return ""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    t = re.sub(r"(?m)^\s*[-*\u2022]\s*", "", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def _render_marble(domain_result: Any, lighting_state: Any, telemetry: Any = None,
                   budget: int = 2000) -> Dict[str, Any]:
    """
    Budgeted assembly. Fixed framing, illumination, and occupancy are reserved
    FIRST and can never be trimmed away; the remaining budget is shared among
    the domain sections by weight. Sections get shorter, they do not disappear.
    """
    address = getattr(domain_result, "address", "") or ""

    # ---- fixed sections: reserved before anything else ----
    framing = (
        "An outdoor world at street level in a real place"
        + (f": {address}." if address else ".")
        + " Open sky overhead. This is a continuous exterior environment that "
        "continues in every direction, not an enclosed courtyard and not a picture."
    )
    observer = ""
    if telemetry is not None:
        agl = getattr(telemetry, "altitude_agl", None)
        method = getattr(telemetry, "altitude_method", None)
        if isinstance(agl, (int, float)) and method == "TILESET_SAMPLE":
            if agl <= 2.5:
                observer = "The viewpoint stands on the ground at street level."
            elif agl <= 12:
                observer = f"The viewpoint is about {agl:.0f} metres up, at upper-storey height."
            else:
                observer = f"The viewpoint is about {agl:.0f} metres above the ground."

    illumination = "ILLUMINATION\n" + _world_atmosphere(lighting_state)
    occupancy = ("OCCUPANCY\nNo people and no vehicles anywhere. Retain permanent civil "
                 "fabric: kerbs, railings, street lamps, steps, gates, and mature trees.")

    fixed = [framing, observer, illumination, occupancy]
    fixed_cost = sum(len(f) for f in fixed if f) + 2 * len([f for f in fixed if f])

    # ---- variable sections, in priority order with weights ----
    variable = [
        ("THE PLACE", scrub_photographic(_flatten(getattr(domain_result, "documentary_prompt", "") or "")), 3),
        ("STRUCTURE AND MASSING", scrub_photographic(_flatten(getattr(domain_result, "architectural_analysis", "") or "")), 3),
        ("SURFACES AND MATERIALS", scrub_photographic(_flatten(getattr(domain_result, "material_and_lithics", "") or "")), 3),
        ("VEGETATION", scrub_photographic(_flatten(getattr(domain_result, "botanical_ecology", "") or "")), 1),
    ]
    variable = [(h, b, w) for h, b, w in variable if b]

    remaining = max(0, budget - fixed_cost - sum(len(h) + 3 for h, _, _ in variable))

    # proportional allocation, with surplus from short sections redistributed
    alloc: Dict[str, int] = {}
    pending = list(variable)
    pool = remaining
    while pending:
        total_w = sum(w for _, _, w in pending)
        if total_w == 0 or pool <= 0:
            for h, _, _ in pending:
                alloc[h] = 0
            break
        under = [(h, b, w) for h, b, w in pending if len(b) <= pool * w / total_w]
        if not under:
            for h, b, w in pending:
                alloc[h] = int(pool * w / total_w)
            break
        for h, b, w in under:
            alloc[h] = len(b)
            pool -= len(b)
        pending = [(h, b, w) for h, b, w in pending if h not in alloc]

    body = []
    trimmed_sections = []
    for h, b, _ in variable:
        limit = alloc.get(h, 0)
        if limit < 60:
            trimmed_sections.append(h)
            continue
        piece = _trim_to(b, limit)
        if len(piece) < len(b):
            trimmed_sections.append(h)
        body.append(f"{h}\n{piece}")

    sections = [framing]
    if observer:
        sections.append(observer)
    sections.extend(body)
    sections.append(illumination)
    sections.append(occupancy)

    full = "\n\n".join(s.strip() for s in sections if s and s.strip())

    return {
        "prompt": full,
        "metadata": {
            "renderer": "WORLD_LABS",
            "final_char_count": len(full),
            "budget": budget,
            "over_budget": len(full) > budget,
            "fixed_cost": fixed_cost,
            "sections_included": len(sections),
            "sections_trimmed": trimmed_sections,
            "scrubbed_photographic": True,
            "screen_space_lighting_used": False
        }
    }


# =========================================================================
# ENTRY POINT
# =========================================================================

def compile_conditioning(
    domain_result: Any,
    lighting_state: Any,
    target_provider: str = "GEMINI",
    target_model: Optional[str] = None,
    telemetry: Any = None,
    marble_budget: int = 2000,
    gemini_budget: int = 3200
) -> CompiledPrompt:

    provider = target_provider.upper()

    if provider == "WORLD_LABS":
        rendered = _render_marble(domain_result, lighting_state, telemetry, budget=marble_budget)
        default_model = "marble-1.1-plus"
    else:
        rendered = _render_gemini(domain_result, lighting_state, budget=gemini_budget)
        default_model = "gemini-3.1-flash-image"

    model = target_model or default_model
    full_prompt = rendered["prompt"]

    return CompiledPrompt(
        prompt=full_prompt,
        system_instruction="",
        user_prompt=full_prompt,
        target_provider=provider,
        target_model=model,
        metadata=rendered["metadata"]
    )
