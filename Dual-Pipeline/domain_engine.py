"""
Domain Engine: analyses a captured view through five domain lenses (latent space archaeology)
and writes the time-invariant scene text the renderer works from.
Seasonal phenology is generated per date by generate_phenology.
"""

import os
import re
import json
import base64
import hashlib
import datetime as _dt
from pathlib import Path
import traceback
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

import requests
from fastapi import HTTPException
from google import genai
from google.genai import types

# Domain analysis and the Street View passes. Phenology keeps its own model (PHENOLOGY_MODEL).
DOMAIN_MODEL = "gemini-3.8-flash"


class ViewScope(str, Enum):
    FRUSTUM = "FRUSTUM"        
    OMNI_360 = "OMNI_360"      
    STANDALONE = "STANDALONE"  


@dataclass
class DomainAnalysisResult:
    """Strongly typed output contract for the Domain Engine."""
    address: str
    view_scope: ViewScope
    documentary_prompt: str
    geological_foundation: str
    architectural_analysis: str
    material_and_lithics: str
    botanical_ecology: str
    static_decluttering_summary: str
    raw_response: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Variant layer: seasonal canopy state for ONE date. Empty in pre-split runs,
    # whose seasonal state is woven into botanical_ecology and documentary_prompt instead.
    phenology: str = ""
    # Present surface condition (soiling, cleaning, streaking), kept apart from the fabric.
    # Empty in runs made before the fabric/condition split.
    surface_condition: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================================
# DOMAIN SYSTEM INSTRUCTION (latent space archaeology, five lenses)
# =========================================================================

DOMAIN_SYSTEM_INSTRUCTION = """# DOMAIN ANALYSIS: LATENT SPACE ARCHAEOLOGY FOR A CAPTURED VIEW

## ROLE AND PRINCIPLE
You analyse one real place from a 3D capture and write the scene text an image model renders from. Your purpose is to bypass centroid collapse: the tendency of image models to fall back on the generic, cliche version of a place. You do it by drawing deep, specific knowledge from several domains at once, while keeping every claim about structure tied to what the capture shows.
The governing principle: invent texture, never structure. Knowledge may enrich materials, weathering, chemistry and plant life, because those follow from the place's stone, climate and age. Knowledge may never add architectural features, because those are specific to each building and recall gets them wrong.

## STAGE 1: CENTROID IDENTIFICATION AND REJECTION
Before anything else, name the centroid for this specific place: the generic version an image model would produce if asked for it, in stone colour, ornament, condition, ground surfaces and planting. Everything that follows must resist drifting toward it.

## STAGE 2: DOMAIN LENSES
- GEOLOGY: bedrock, the local building stone and its quarries, mineralogy and cement, mortar chemistry, drainage.
- HISTORICAL AND MATERIAL: how the stone and iron were worked: tooling, dressing, coursing, casting, period fabrication. Not ornament: recalled ornament is unreliable.
- CIVIL ENGINEERING: structural logic and true geometry. Plumb every wall to gravity vertical, planarize facades, sharpen ridges, align window grids. Never read photogrammetry mesh noise as real architecture. Rectification is geometric only: it never cleans, smooths or evens out surface colour or soiling.
- CHEMICAL: how the materials have aged: soot and gypsum crusts, salt efflorescence, iron staining and rust, lime leaching, spalling, and where each concentrates.
- ECOLOGICAL: trees by genus and species, with canopy form, height, trunk and branch structure; and the biology of surfaces: moss, lichen and algae, and where moisture and shelter put them.

## STAGE 3: CROSS-DOMAIN SYNERGY
Find the details that appear only where lenses intersect: how this stone's mineralogy, the local pollution history and the climate together produce the particular soiling, crusting, staining and growth on these surfaces. These intersections are the richest part of the scene and belong in MATERIALS and CONDITION.

## STAGE 4: CONFLICT RESOLUTION
Where lenses disagree, resolve it explicitly. One rule always holds: when recalled knowledge conflicts with the capture, the capture wins. Architectural orders, pilasters, pediments, porticoes, dormers, mansards, balustrades and roof forms enter the documentary prompt only when the capture shows them. In the ARCHITECTURE section, mark any recalled feature the capture does not show as UNVERIFIED.

## FABRIC AND CONDITION
Fabric is what a structure is made of and how it is built. Condition is how its surfaces look today. A 3D capture cannot show condition reliably, so condition is always an estimate here, made from the place's history, stone, climate and age, and confirmed later against street-level photography. Describe it as typical for the place and keep it consistent across a uniform terrace. Never assume a building has been cleaned or restored, and never invent differences between neighbouring buildings. Locate weathering and growth by exposure, never by compass direction: sheltered or exposed faces, drip lines, the undersides of projections, ground contact.

## SCENE RULES
- The frame is given. The capture is the survey. Report only the structures and ground surfaces actually present in it, in proportion to how much of it they occupy. Ground, turf, water and paving that fill the capture deserve the same specificity as buildings. A famous building at this address that is not in the capture is not part of this site.
- Evaluate each structure's era and material independently. Never homogenize the scene into one material; distinguish, for example, historic masonry from modern concrete or glass.
- Trees are time-invariant. Seasonal state is generated separately for each date: never describe leaf presence, leaf colour, flowering, fruiting, leaf fall, bare branches or season in any section.
- Lighting is out of scope. Never describe sky, light, shadows, sun position, weather or time of day: an independent engine manages them.
- Decluttering: no pedestrians, vehicles, bins, temporary signage, scaffolding, hoardings or building wraps. Keep stone kerbs, iron railings, fixed streetlamps and mature trees. Decluttering removes transient objects only; soiling, staining and weathering are permanent.
- Avoid sterile CGI surfaces, sandblasted smoothness and homogenized materials.
- The documentary prompt never uses camera, lens or format language, screen positions, compass directions or street names.
- Style: high-density telegraphic notation, technically precise, no conversational filler.
"""


def reverse_geocode(lat: float, lon: float, google_maps_api_key: Optional[str] = None) -> str:
    key = (
        google_maps_api_key
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or os.getenv("GOOGLE_MAPS_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )

    if key:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={key}"
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    return results[0].get("formatted_address")
        except Exception:
            pass

    try:
        bdc_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
        resp = requests.get(bdc_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            locality = data.get("locality") or data.get("city")
            admin_area = data.get("principalSubdivision")
            country = data.get("countryName")
            parts = [p for p in [locality, admin_area, country] if p]
            if parts:
                return ", ".join(parts)
    except Exception:
        pass

    return f"{lat:.4f}°, {lon:.4f}°"


def analyze_spatial_domain(
    address: str,
    coordinates: Optional[tuple[float, float]] = None,
    view_scope: ViewScope = ViewScope.FRUSTUM,
    telemetry: Optional[Any] = None,
    screenshot_b64: Optional[str] = None,
    temporal_epoch: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    use_search_grounding: bool = False
) -> DomainAnalysisResult:
    
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    lat_str = f"{coordinates[0]:.6f}" if coordinates else (f"{getattr(telemetry, 'latitude', 0.0):.6f}" if telemetry else "Unknown")
    lon_str = f"{coordinates[1]:.6f}" if coordinates else (f"{getattr(telemetry, 'longitude', 0.0):.6f}" if telemetry else "Unknown")
    altitude_agl = getattr(telemetry, "altitude_agl", 0.0) if telemetry else 0.0
    heading = getattr(telemetry, "heading", 0.0) if telemetry else 0.0
    pitch = getattr(telemetry, "pitch", -45.0) if telemetry else -45.0
    fov = getattr(telemetry, "fov", 45.0) if telemetry else 45.0
    tile_mode = getattr(telemetry, "tile_mode", "3D_TILES") if telemetry else "STANDALONE"

    cam_lat = getattr(telemetry, "latitude", None) if telemetry else None
    cam_lon = getattr(telemetry, "longitude", None) if telemetry else None
    tgt_lat = getattr(telemetry, "target_latitude", None) if telemetry else None
    tgt_lon = getattr(telemetry, "target_longitude", None) if telemetry else None
    tgt_dist = getattr(telemetry, "target_distance_m", None) if telemetry else None
    has_target = tgt_lat is not None and tgt_lon is not None

    if has_target:
        subject_lines = (
            f"- Resolved Address (of the framed subject): {address}\n"
            f"- Subject Coordinates (surface point at frame center): ({lat_str}, {lon_str})"
            + (f", {tgt_dist:.0f} m from camera" if tgt_dist is not None else "") + "\n"
            "- Note: the address and subject coordinates identify what the capture is aimed at, "
            "not where the camera stands. Neighbouring addresses may also be in frame."
        )
    else:
        subject_lines = (
            f"- Resolved Address (camera ground position; no subject point resolved): {address}\n"
            f"- Coordinates: ({lat_str}, {lon_str})\n"
            "- Note: this address is where the camera stands and may not describe the framed subject."
        )

    camera_pos = (
        f"({cam_lat:.6f}, {cam_lon:.6f}), " if (has_target and cam_lat is not None and cam_lon is not None) else ""
    )

    context_block = f"""TARGET LOCATION & SPATIAL CONTEXT:
{subject_lines}
- Temporal Epoch / Date: {temporal_epoch or 'Present Day'}
- View Scope Mode: {view_scope.value}
- Camera Telemetry: {camera_pos}Altitude {altitude_agl:.1f}m AGL, Heading {heading:.1f}°, Pitch {pitch:.1f}°, FOV {fov:.1f}°
- Tile Mode: {tile_mode}
"""

    if view_scope == ViewScope.OMNI_360:
        scope_directive = (
            "SCOPE DIRECTIVE (360° OMNIDIRECTIONAL WORLD RECONSTRUCTION):\n"
            "Analyze and describe the entire 360-degree spatial environment enclosing the observer. "
            "Detail the Northern, Southern, Eastern, and Western perimeter structures, overhead canopy, and ground terrain."
        )
    elif view_scope == ViewScope.STANDALONE:
        scope_directive = (
            "SCOPE DIRECTIVE (STANDALONE CAUSAL ANALYSIS):\n"
            "No visual capture provided. Reconstruct the spatial reality from first principles using your deep knowledge."
        )
    else:  
        scope_directive = (
            "SCOPE DIRECTIVE (DIRECTIONAL FRUSTUM RECTIFICATION):\n"
            "Using the viewport capture as the absolute coordinate reference, break down the scene spatially across the frame. "
            "Plumb all verticals, rectify planar facades, and disambiguate organic foliage from masonry."
        )

    user_prompt = f"""{context_block}

{scope_directive}

OUTPUT REQUIREMENTS:
Provide your output structured into the following labeled sections:

---CENTROID---
[Stage 1: the generic version of this specific place an image model would produce, in stone colour, ornament, condition, ground surfaces and planting. Everything below resists it]

---GEOLOGY---
[Subterranean bedrock, local stone/masonry lithics, mortar chemistry, and local groundwater/drainage]

---ARCHITECTURE---
[Architectural typologies, storey counts, bay rhythm, roof geometry, window fenestration, planar rectification. Mark every recalled feature the capture does not show as UNVERIFIED]

---MATERIALS---
[Per-structure fabric: facade materials, quarry stone, dressing, brick bonds, renders. Fabric only: surface condition goes in CONDITION]

---CONDITION---
[Per-structure estimated present surface condition from the chemical and ecological lenses, for buildings, paving, kerbs, walls and ironwork: overall colour as it looks today, soiling and crusts, staining, efflorescence, moss, lichen and algae, and where each concentrates by exposure. Always an estimate: a 3D capture cannot show it. No differences between neighbouring buildings unless the capture plainly shows them]

---ECOLOGY---
[Identified native/urban tree genus and species, canopy volume, height, trunk and branch structure. Time-invariant only: no leaf state, colour, or season]

---STATIC_DECLUTTERING---
[Confirmation of complete removal of all transient vehicles, pedestrians, dumpsters, and clutter]

---DOCUMENTARY_PROMPT---
[High-density, telegraphic documentary prompt covering only what is visible in the reference capture. Include specific quarry lithics, masonry dressing, fenestration grids, distinct modern vs historic materials, ground surfacing, and botanical tree species with canopy form. Name only features the capture shows: massing, storey count, bay rhythm, window grid, materials, and the ground surface as far as it is legible. Never include UNVERIFIED features or ornament the capture does not show, such as orders, pilasters, pediments, dormers, mansards or balustrades. Describe each structure surface first: open with how its stone looks today (its colour as seen, its soiling and where that concentrates), then the material and dressing beneath. Never open with the clean quarry colour, and give tone as an actual colour, not an intensity word such as light or moderate. Surface condition is part of the time-invariant scene. Never drift toward the centroid named in CENTROID. TARGET LENGTH: 1200 to 1600 characters. Time-invariant material and fabric only: no lighting, sky, shadows, weather, or time of day; no leaf state, foliage colour, or season; no camera, lens, or format; no frame or compass placement.]
"""

    contents: List[Any] = [user_prompt]

    if screenshot_b64 and view_scope != ViewScope.STANDALONE:
        if "," in screenshot_b64 and screenshot_b64.startswith("data:"):
            header, raw_b64 = screenshot_b64.split(",", 1)
            mime_type = header.split(";")[0].replace("data:", "").strip()
        else:
            mime_type = "image/png"
            raw_b64 = screenshot_b64
        
        image_bytes = base64.b64decode(raw_b64)
        contents.insert(0, types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    # Configured with expanded 4096 thinking budget and Search Grounding
    config_kwargs = dict(
        system_instruction=DOMAIN_SYSTEM_INSTRUCTION,
        temperature=0.0,
        top_p=0.85,
        thinking_config=types.ThinkingConfig(thinking_budget=4096),
    )
    if use_search_grounding:
        config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    print(f"[Domain] search grounding: {'ON' if use_search_grounding else 'OFF'}")
    config = types.GenerateContentConfig(**config_kwargs)

    try:
        response = client.models.generate_content(
            model=DOMAIN_MODEL,
            contents=contents,
            config=config
        )
    except Exception as e:
        print("\n[ERROR] Domain Engine generate_content failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Domain Engine Error: {str(e)}")

    response_text = response.text or ""

    def _extract_section(tag: str, text: str) -> str:
        # Handles markdown headings or raw tags
        pattern = rf"(?:###\s*)?---{tag}---\s*(.*?)(?=(?:###\s*)?---[A-Z_]+---|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    geology = _extract_section("GEOLOGY", response_text)
    architecture = _extract_section("ARCHITECTURE", response_text)
    materials = _extract_section("MATERIALS", response_text)
    condition = _extract_section("CONDITION", response_text)
    centroid = _extract_section("CENTROID", response_text)
    ecology = _extract_section("ECOLOGY", response_text)
    decluttering = _extract_section("STATIC_DECLUTTERING", response_text)
    doc_prompt = _extract_section("DOCUMENTARY_PROMPT", response_text)

    if not doc_prompt:
        doc_prompt = response_text.strip()

    return DomainAnalysisResult(
        address=address,
        view_scope=view_scope,
        documentary_prompt=doc_prompt,
        geological_foundation=geology,
        architectural_analysis=architecture,
        material_and_lithics=materials,
        botanical_ecology=ecology,
        static_decluttering_summary=decluttering,
        raw_response=response_text,
        surface_condition=condition,
        metadata={
            "address": address,
            "invariant_split": True,
            "split_version": 1,
            "coordinates": (lat_str, lon_str),
            "address_source": "TARGET" if has_target else "CAMERA",
            "tile_mode": tile_mode,
            "view_scope": view_scope.value,
            "search_grounding": use_search_grounding,
            "condition_split": True,
            "visible_only": True,
            "domain_instruction": "lsa-merge-1",
            "centroid": centroid,
            "domain_model": DOMAIN_MODEL
        }
    )


# =========================================================================
# PHENOLOGY: the variant layer, generated per date and cached
# =========================================================================

PHENOLOGY_MODEL = "gemini-3.7-flash"
PHENOLOGY_CACHE_PATH = Path(__file__).resolve().parent / "phenology_cache.json"

PHENOLOGY_SYSTEM_INSTRUCTION = """You are an urban arboriculturist and phenologist.
You receive the tree species present at a real site, its location, and one calendar date.
Describe, for each listed species only, its canopy state on that date in that local climate:
leaf presence and density, leaf colour, leaf fall, bare branch structure, and any flowering or fruiting visible from street level.
Account for regional climate and typical seasonal timing at that latitude.
Rules: telegraphic notation, one clause per species, 350 characters maximum in total.
Never add species that are not listed. Never describe weather, sky, light, shadows, time of day, or buildings.
Output only the description, no preamble."""


def _load_phenology_cache() -> Dict[str, Any]:
    try:
        return json.loads(PHENOLOGY_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_phenology_cache(cache: Dict[str, Any]) -> None:
    try:
        tmp = PHENOLOGY_CACHE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PHENOLOGY_CACHE_PATH)
    except Exception as e:
        print(f"[Phenology] cache not written: {e}")


def _generate_phenology_per_date(
    ecology_text: str,
    address: str,
    lat: float,
    lon: float,
    date_str: str,
    gemini_api_key: Optional[str] = None,
) -> tuple:
    """
    Returns (phenology_text, source) where source is "cache", "generated", or "failed".
    The same species list, place, and date always return the same text, so a series
    frame can be re-rendered without its foliage changing.
    """
    ecology_text = (ecology_text or "").strip()
    if not ecology_text or not date_str:
        return "", "failed"

    key_src = f"{PHENOLOGY_MODEL}|{ecology_text}|{round(lat, 3)}|{round(lon, 3)}|{date_str}"
    key = hashlib.sha1(key_src.encode("utf-8")).hexdigest()
    cache = _load_phenology_cache()
    if key in cache:
        return cache[key]["text"], "cache"

    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "", "failed"

    prompt = (
        f"SITE: {address} ({lat:.4f}, {lon:.4f})\n"
        f"DATE: {date_str}\n"
        f"TREES PRESENT (time-invariant description):\n{ecology_text}\n\n"
        "Describe each listed species' canopy state on this date."
    )
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=PHENOLOGY_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=PHENOLOGY_SYSTEM_INSTRUCTION,
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_budget=1024),
                **({"automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True)}
                   if hasattr(types, "AutomaticFunctionCallingConfig") else {}),
            ),
        )
        text = (response.text or "").strip()
    except Exception as e:
        print(f"[Phenology] generation failed: {e}")
        return "", "failed"

    if not text:
        return "", "failed"
    cache[key] = {"date": date_str, "address": address, "text": text}
    _save_phenology_cache(cache)
    return text, "generated"


# =========================================================================
# PHENOLOGY CALENDAR: one model call per site returns each species' key dates
# and a short look for each stage. Every frame's text is then derived from
# where its date falls, so the seasons can only move forward.
# =========================================================================

CALENDAR_VERSION = 2
STAGE_ORDER = ["budburst", "full_leaf", "colour_onset", "peak_colour", "half_fall", "bare"]
STAGE_FOR_INTERVAL = {        # interval starting at each milestone -> the stage it opens
    "budburst": ("budburst", "bud break"),
    "full_leaf": ("full_leaf", "full leaf"),
    "colour_onset": ("colouring", "colouring"),
    "peak_colour": ("peak", "peak colour"),
    "half_fall": ("falling", "leaf fall"),
    "bare": ("dormant", "dormant"),
}

CALENDAR_SYSTEM_INSTRUCTION = """You are an urban arboriculturist and phenologist.
You receive the plants listed at a real site and its location. Return the TYPICAL annual phenology
for each listed plant at that location in its local climate (climate normals, not one particular year).
Return JSON only, no prose, in exactly this shape:
{
  "climate_note": "one sentence on how this climate shifts seasonal timing",
  "species": [
    {
      "name": "Latin name exactly as listed",
      "habit": "deciduous" or "evergreen",
      "milestones": {"budburst": "MM-DD", "full_leaf": "MM-DD", "colour_onset": "MM-DD",
                     "peak_colour": "MM-DD", "half_fall": "MM-DD", "bare": "MM-DD"},
      "stages": {"budburst": "...", "full_leaf": "...", "colouring": "...",
                 "peak": "...", "falling": "...", "dormant": "..."},
      "evergreen_look": "..."
    }
  ]
}
Rules: include every listed plant and never add one. Deciduous plants need all six milestones, in
seasonal order, and all six stages. Evergreen plants (including lawn grasses) need only evergreen_look.
Each stage and evergreen_look is at most 90 characters of telegraphic visual description as seen from
street level: leaf colour and form, flowers or fruit, bark or branch character.
Each stage description must be true for the WHOLE stage: never name a month, and never include an event
that lasts only part of the stage (for example, flowering that ends partway through summer).
Do not state how dense or sparse the canopy is; leaf cover is supplied separately as a number.
Never describe weather, sky, light, shadows, time of day, or buildings."""


def _doy(month_day: str) -> int:
    """Day of year in a fixed non-leap reference year; Feb 29 counts as Feb 28."""
    m, d = (int(x) for x in month_day.split("-"))
    if m == 2 and d == 29:
        d = 28
    return (_dt.date(2025, m, d) - _dt.date(2025, 1, 1)).days


def _valid_species(sp: Dict[str, Any]) -> bool:
    if sp.get("habit") == "evergreen":
        return bool(sp.get("evergreen_look"))
    ms, st = sp.get("milestones") or {}, sp.get("stages") or {}
    try:
        days = [_doy(ms[k]) for k in STAGE_ORDER]
    except Exception:
        return False
    offsets = [(d - days[0]) % 365 for d in days]
    increasing = all(offsets[i] < offsets[i + 1] for i in range(len(offsets) - 1))
    return increasing and all(st.get(v[0]) for v in STAGE_FOR_INTERVAL.values())


def _parse_calendar(text: str, ecology_text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        cal = json.loads(raw)
    except Exception:
        return None
    eco_lower = ecology_text.lower()
    kept, dropped = [], []
    for sp in cal.get("species") or []:
        genus = (sp.get("name") or "").split()[0].strip("*").lower() if sp.get("name") else ""
        if not genus or genus not in eco_lower:
            dropped.append(sp.get("name"))           # a plant the art bible never listed
        elif _valid_species(sp):
            kept.append(sp)
        else:
            dropped.append(f"{sp.get('name')} (invalid dates)")
    if dropped:
        print(f"[Phenology] calendar dropped: {dropped}")
    if not kept:
        return None
    cal["species"] = kept
    cal["dropped"] = dropped
    cal["version"] = CALENDAR_VERSION
    return cal


# Leaf cover (percent of a full canopy) across each stage, as (start, end), interpolated by
# how far into the stage the date falls. Words like "dense" or "thinning" leave the renderer room
# to choose; a number derived from the date gives every frame the same target.
LEAF_COVER = {
    "budburst": (5, 90),
    "full_leaf": (100, 100),
    "colouring": (100, 95),
    "peak": (95, 50),      # peak colour runs up to "half fallen"
    "falling": (50, 0),
    "dormant": (0, 0),
}


def _leaf_cover(stage_key: str, frac: float) -> int:
    a, b = LEAF_COVER[stage_key]
    return int(round((a + (b - a) * max(0.0, min(1.0, frac))) / 5.0) * 5)


def _branch_note(cover: int) -> str:
    if cover >= 90:
        return "inner branches hidden"
    if cover >= 50:
        return "main limbs partly visible through the leaves"
    if cover >= 10:
        return "branch framework clearly visible"
    return "bare branches"


def phenology_from_calendar(cal: Dict[str, Any], date_str: str) -> str:
    """Deterministic: the same calendar and date always give the same text, and later dates never look earlier."""
    target = _doy(date_str[5:10])
    parts = []
    for sp in cal["species"]:
        name = sp["name"].strip("*")
        if sp.get("habit") == "evergreen":
            parts.append(f"*{name}*: {sp['evergreen_look'].rstrip('.')}.")
            continue
        days = [_doy(sp["milestones"][k]) for k in STAGE_ORDER]
        offsets = [(d - days[0]) % 365 for d in days] + [365]
        pos = (target - days[0]) % 365
        for i, key in enumerate(STAGE_ORDER):
            if offsets[i] <= pos < offsets[i + 1]:
                stage_key, label = STAGE_FOR_INTERVAL[key]
                frac = (pos - offsets[i]) / max(1, offsets[i + 1] - offsets[i])
                when = "early" if frac < 1 / 3 else ("mid" if frac < 2 / 3 else "late")
                cover = _leaf_cover(stage_key, frac)
                parts.append(f"*{name}* ({when} {label}; leaf cover about {cover}%, {_branch_note(cover)}): "
                             f"{sp['stages'][stage_key].rstrip('.')}.")
                break
    return " ".join(parts)


def get_phenology_calendar(
    ecology_text: str,
    address: str,
    lat: float,
    lon: float,
    gemini_api_key: Optional[str] = None,
) -> tuple:
    """Returns (calendar or None, source) where source is "cache", "generated", or "failed"."""
    ecology_text = (ecology_text or "").strip()
    if not ecology_text:
        return None, "failed"
    key_src = f"cal{CALENDAR_VERSION}|{PHENOLOGY_MODEL}|{ecology_text}|{round(lat, 3)}|{round(lon, 3)}"
    key = "cal:" + hashlib.sha1(key_src.encode("utf-8")).hexdigest()
    cache = _load_phenology_cache()
    if key in cache:
        return cache[key]["calendar"], "cache"
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "failed"
    prompt = (
        f"SITE: {address} ({lat:.4f}, {lon:.4f})\n"
        f"PLANTS LISTED (time-invariant description):\n{ecology_text}\n\n"
        "Return the typical annual phenology calendar for every listed plant at this site."
    )
    cfg = dict(
        system_instruction=CALENDAR_SYSTEM_INSTRUCTION,
        temperature=0.0,
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=2048),
    )
    if hasattr(types, "AutomaticFunctionCallingConfig"):
        cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=PHENOLOGY_MODEL, contents=[prompt], config=types.GenerateContentConfig(**cfg),
        )
        cal = _parse_calendar(response.text or "", ecology_text)
    except Exception as e:
        print(f"[Phenology] calendar generation failed: {e}")
        return None, "failed"
    if not cal:
        print("[Phenology] calendar unusable; falling back to per-date generation")
        return None, "failed"
    cache[key] = {"address": address, "calendar": cal}
    _save_phenology_cache(cache)
    return cal, "generated"


def generate_phenology(
    ecology_text: str,
    address: str,
    lat: float,
    lon: float,
    date_str: str,
    gemini_api_key: Optional[str] = None,
) -> tuple:
    """
    Returns (phenology_text, source). Uses the site's phenology calendar, so frames
    progress monotonically; falls back to one model call per date only if no calendar
    can be made. Sources: calendar-cache, calendar-generated, cache, generated, failed.
    """
    if not date_str:
        return "", "failed"
    cal, src = get_phenology_calendar(ecology_text, address, lat, lon, gemini_api_key)
    if cal:
        return phenology_from_calendar(cal, date_str), f"calendar-{src}"
    return _generate_phenology_per_date(ecology_text, address, lat, lon, date_str, gemini_api_key)


# =========================================================================
# STREET VIEW READ: reference notes for the keystone's art bible
# =========================================================================

STREETVIEW_READ_INSTRUCTION = """You are an architectural surveyor and building conservator.
You receive two images of the same real place and the current scene description.
IMAGE 1 is the composition being rendered, from a 3D capture. It defines what is in frame and where.
IMAGE 2 is a recent street-level reference photograph of the subject, taken from a different position.
Write reference notes for elements that appear in BOTH images, covering only what Image 2 shows and the capture cannot:
- construction detail: doors and fanlights, window types, blind or painted windows, railings, cornices, string courses, rustication, roof features
- surface condition per facade: stone colour, soot or grime blackening versus cleaned stone, how uneven it is, where it is heaviest (which storeys, under cornices, around windows), streaking, patch repairs
Locate every facade by its position in IMAGE 1 (for example "left foreground facade", "centre corner block", "far terrace beyond"). Never use street names or compass directions: the renderer cannot map them.
Ignore everything temporary or seasonal in Image 2: vehicles, people, signs, scaffolding, bins, foliage, weather, wet surfaces, sky, light and shadows.
Never describe anything that is not visible in Image 1. Where Image 2 clearly contradicts the scene description, say so in one clause.
Telegraphic notation, at most 700 characters. Output only the notes."""


def read_streetview(
    capture_b64: str,
    pano_jpeg: bytes,
    scene_text: str,
    pano_date: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
) -> str:
    """Construction and weathering notes from a Street View pano, located by position in the capture."""
    return _streetview_call(STREETVIEW_READ_INSTRUCTION, capture_b64, pano_jpeg, scene_text, pano_date,
                            "Write the reference notes.", 2048, gemini_api_key)


def _streetview_call(instruction: str, capture_b64: str, pano_jpeg: bytes, scene_text: str,
                     pano_date: Optional[str], ask: str, thinking_budget: int,
                     gemini_api_key: Optional[str]) -> str:
    """One call with the capture (IMAGE 1), the pano (IMAGE 2) and the current scene text."""
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    raw = capture_b64.split(",", 1)[1] if capture_b64.startswith("data:") else capture_b64
    mime = capture_b64.split(";")[0].replace("data:", "") if capture_b64.startswith("data:") else "image/jpeg"
    contents = [
        "IMAGE 1 (the composition being rendered):",
        types.Part.from_bytes(data=base64.b64decode(raw), mime_type=mime),
        f"IMAGE 2 (Street View reference, {pano_date or 'date unknown'}):",
        types.Part.from_bytes(data=pano_jpeg, mime_type="image/jpeg"),
        f"CURRENT SCENE DESCRIPTION:\n{scene_text}\n\n{ask}",
    ]
    cfg = dict(
        system_instruction=instruction,
        temperature=0.0,
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
    )
    if hasattr(types, "AutomaticFunctionCallingConfig"):
        cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=DOMAIN_MODEL, contents=contents, config=types.GenerateContentConfig(**cfg),
    )
    return (response.text or "").strip()


# =========================================================================
# STREET VIEW FINISHING PASS: rewrite the scene text's surface condition
# =========================================================================

STREETVIEW_REWRITE_INSTRUCTION = """You are an architectural surveyor and building conservator doing the finishing pass on a scene description.
You receive two images of the same real place and the current scene description.
IMAGE 1 is the composition being rendered, from a 3D capture. It fixes what is in frame, where it is, and the massing. Its surface detail is unreliable.
IMAGE 2 is a street-level reference photograph of the subject, taken from a different position. It is the evidence for visible detail and for how the surfaces look today.
Return the complete scene description, revised so that:
- Surface condition matches IMAGE 2 and comes first. Open each structure's description with how its stone looks today (its colour as seen, its soiling, how even or uneven it really is, where darkening concentrates), then name the material and dressing beneath it. Never open with the clean quarry colour, and remove clean quarry-colour words such as blonde, pale buff or honey for stone that IMAGE 2 shows soiled. Give tone as an actual colour, not an intensity word such as light or moderate. Describe differences between buildings only where IMAGE 2 shows them.
- Visible detail matches IMAGE 2 for structures that appear in both images: doors and fanlights, window types, pilasters and their order and how many bays they span, string courses, cornices, the roofline including dormers or their absence, railings, and the ground surface. Add detail IMAGE 2 shows; correct detail it contradicts.
- Every architectural feature that appears in neither image is deleted, for example pediments, pilaster orders, dormers or mansard roofs that neither image shows.
- Everything else, including tree species, stays word for word.
Ignore everything temporary or seasonal in IMAGE 2: vehicles, people, signs, scaffolding, bins, foliage, weather, wet surfaces, sky, light and shadows. Bright sun or deep shade in IMAGE 2 is light, not surface colour.
Never add lighting, weather, season, camera, screen-position or compass language, and never use street names. Name structures by their architectural features. Keep the telegraphic style and keep the length within about 25% of the original.
Output only the revised scene description."""


def rewrite_condition_from_streetview(
    capture_b64: str,
    pano_jpeg: bytes,
    scene_text: str,
    pano_date: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
) -> str:
    """Finishing pass: the full scene text back, with condition and visible detail set from the pano
    and features shown in neither image removed."""
    out = _streetview_call(STREETVIEW_REWRITE_INSTRUCTION, capture_b64, pano_jpeg, scene_text, pano_date,
                           "Return the revised scene description.", 4096, gemini_api_key)
    out = re.sub(r"^```[a-z]*\s*|\s*```$", "", out).strip()
    if not out:
        raise HTTPException(status_code=502, detail="The rewrite came back empty; the scene text is unchanged.")
    ratio = len(out) / max(len(scene_text), 1)
    if not 0.6 <= ratio <= 1.6:
        raise HTTPException(status_code=502, detail=(
            f"The rewrite changed the length too much ({ratio:.0%} of the original); the scene text is unchanged."))
    return out

