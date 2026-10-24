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
# STRUCTURE CHECK (2026-10-18): which structural features a pass took out of the scene text.
# Both passes (finishing pass, weft pass) are told to keep structure; on 2026-10-16/17 both dropped it anyway
# (the lamp, arches, dormers, storey counts, granite kerbs). Additions are listed by the model; removals are
# checked here, by comparing the texts, so they never depend on the model owning up.
# =========================================================================

_STRUCTURE_TERMS = [
    # counts and massing
    # 60 (2026-10-22): each count is a synonym group, so "four-storey" reworded as "four floors of windows" is not a loss.
    *[rf"{n}-storey|{n} storeys?|{n} floors?" for n in ("one", "two", "three", "four", "five", "six")],
    r"one-bay", r"two-bay", r"three-bay", r"four-bay", r"five-bay", r"six-bay", r"seven-bay",
    r"attic", r"dormers?", r"mansards?", r"basements?", r"lightwells?", r"areas? railings?",
    # openings
    r"arch(?:ed|es)?", r"fanlights?", r"transoms?", r"blind (?:windows?|panels?)", r"sash(?:es)?", r"doors?", r"door case",
    r"squared|square-headed|flat-(?:headed|lintelled|topped)|rectangular", r"bays?",
    # elements
    r"steps?", r"lamps?", r"globe", r"railings?", r"spearheads?", r"balconettes?", r"cornices?",
    r"blocking course", r"band courses?", r"string courses?", r"rustication|rusticated", r"plinths?",
    r"chimneys?(?: stacks?)?", r"(?:terracotta )?pots", r"hoods?", r"aprons?", r"pilasters?", r"pediments?",
    r"porticos?|porticoes", r"balustrades?", r"quoins?", r"parapets?", r"gates?", r"porch(?:es)?", r"portals?",
    r"verandas?|verandahs?", r"balcon(?:y|ies)", r"columns?", r"lintels?", r"shutters?", r"canales", r"vigas?",
    r"towers?", r"domes?", r"gables?", r"eaves", r"awnings?", r"fences?", r"walls?",
    # materials named as fact
    r"granite", r"slate", r"brick", r"adobe", r"stucco", r"render(?:ed)?", r"timber", r"limestone", r"sandstone",
    r"marble", r"concrete", r"tiles?", r"thatch",
    # render directives
    r"geometric accuracy", r"plumb gravity verticals", r"roof ridgelines",
]
_STRUCTURE_RE = [(t, re.compile(rf"\b(?:{t})\b", re.IGNORECASE)) for t in _STRUCTURE_TERMS]


_NEGATED = re.compile(r"\b(?:without|no|never|none)\s+(?:\w+\s+){0,2}$", re.IGNORECASE)


def _affirmed(rx, text: str) -> bool:
    """True if the term appears at least once NOT negated ("without dormers" does not count as dormers)."""
    for m in rx.finditer(text or ""):
        if not _NEGATED.search(text[max(0, m.start() - 40):m.start()]):
            return True
    return False


def structure_removed(before: str, after: str) -> List[str]:
    """Structural terms affirmed in `before` and missing (or only negated) in `after`, in the words `before` used."""
    # Each entry is a synonym group ("squared" and "flat-headed rectangular" count as the same feature), so a pass
    # that rewords a feature is not reported as removing it.
    gone = []
    for _t, rx in _STRUCTURE_RE:
        b = rx.search(before or "")
        if b and _affirmed(rx, before) and not _affirmed(rx, after):
            gone.append(b.group(0).lower())
    return sorted(set(gone))


# =========================================================================
# STREET VIEW FINISHING PASS (revised 2026-10-18 with the weft rules)
# The pano is evidence for SURFACES. The scene text's structure is confirmed (Don's own edits, his layout, the
# capture) and stays. On 2026-10-17 the old pass deleted the lamp and the arches, turned the target building round
# and removed the dormers, because the pano could not see them. Now it may only set surfaces, colours of painted
# features and opening shapes; anything the pano seems to contradict is REPORTED, never applied.
# =========================================================================

STREETVIEW_REWRITE_INSTRUCTION = """You are an architectural surveyor and building conservator doing the finishing pass on a scene description.
You receive two images of the same real place and the current scene description.
IMAGE 1 is the composition being rendered, from a 3D capture. It fixes what is in frame, where it is, and the massing. Its surface detail is unreliable.
IMAGE 2 is a street-level reference photograph of the subject, taken from a different position. It is the evidence for how the surfaces look today.
SCENE TEXT is the current description. Its structure is CONFIRMED by the director: every building, storey count, bay count, opening shape, roof form, step, railing, fixture, ground material and every other structural feature it names stays, word for word where possible, even where IMAGE 2 does not show it (IMAGE 2 is taken from elsewhere and sees less).

Return the scene description revised so that:
- Surface condition matches IMAGE 2 and comes first. Open each structure's description with how its walls look today (their colour, soiling, staining, fading or patching, how even or uneven it is, where it concentrates), then the material and finish beneath. Never open with the material's clean, new colour; give tone as an actual colour.
- COLOUR: name every colour as it would look under flat, even overcast daylight. Warmth from sunlight in IMAGE 2 is light, not the material's colour: a sunlit wall that looks golden or honey is named by its own colour (for example buff-grey, grey-tan, pale grey).
- WEATHERING: describe it by the mark it leaves (pale, cleaner, darker, streaked, crusted, stained, bleached, chalky, flaking), never by the weather that made it: no rain, rain-washed, wet, damp, sun-bleached, frost or snow in the scene text.
- Colours of painted or finished features that IMAGE 2 shows are named: doors, window frames, shutters, railings, ironwork, trim.
- Opening shapes that IMAGE 2 shows clearly on a facade the scene text describes are stated in positive words (for example flat-headed rectangular, round-arched, segmental, pointed), facade by facade.
- COUNT before you compare: for each facade that both IMAGE 2 and the scene text describe, count its bays (vertical rows of openings) and its storeys in IMAGE 2 (storeys are floors of windows above the ground the viewer stands on; floors below street level are not storeys), and compare with the scene text's numbers. Any difference goes in "conflicts" with both numbers ("IMAGE 2 shows five bays on the side-street return; the scene text says four"). Also report an opening shape, roof form or feature that IMAGE 2 clearly shows differently.
- Detail IMAGE 2 shows and the scene text lacks may be ADDED, attached to the element it belongs to: for example a balcony, a porch, a cornice or parapet, a door surround, a transom light. List every structural addition in "added".
- NOTHING the scene text names is deleted, merged, recounted or moved to another facade. Where IMAGE 2 seems to CONTRADICT the scene text's structure (a different bay count, a different opening shape, a feature that seems absent), leave the scene text as it is and report it in "conflicts", in one short sentence each, saying what IMAGE 2 shows.
- Every rendering directive (for example "High geometric accuracy: ...") stays word for word, in its place.
Ignore everything temporary or seasonal in IMAGE 2: vehicles, people, signs, scaffolding, bins, foliage, weather, wet surfaces, sky, light and shadows. Bright sun or deep shade in IMAGE 2 is light, not surface colour.
Never add lighting, weather, season, camera, screen-position or compass language, and never use street names. Keep the telegraphic style; the revised text may be at most 15% longer than the original (put colour and condition in few words; do not repeat a description for every building), never shorter than 90% of it.

Return JSON only, in exactly this shape:
{"scene_text": "the revised scene description",
 "added": [{"phrase": "the exact words as they appear in scene_text", "note": "a few words: what IMAGE 2 shows"}],
 "conflicts": ["one sentence per place IMAGE 2 seems to contradict the scene text's structure"]}"""


def rewrite_condition_from_streetview(
    capture_b64: str,
    pano_jpeg: bytes,
    scene_text: str,
    pano_date: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Finishing pass. Returns {scene_text, added, conflicts, removed}: the scene text with surfaces set from the pano,
    structural additions listed, contradictions reported (never applied), and any structural term the pass dropped
    (found by comparing the texts). Raises HTTPException(502) and changes nothing on an empty, unparseable or
    badly sized result."""
    out = _streetview_call(STREETVIEW_REWRITE_INSTRUCTION, capture_b64, pano_jpeg, scene_text, pano_date,
                           "Return the JSON.", 4096, gemini_api_key)
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out).strip()
    try:
        data = json.loads(out)
    except Exception:
        raise HTTPException(status_code=502, detail="The finishing pass did not return valid JSON; the scene text is unchanged.")
    text = str((data or {}).get("scene_text") or "").strip() if isinstance(data, dict) else ""
    if not text:
        raise HTTPException(status_code=502, detail="The finishing pass came back empty; the scene text is unchanged.")
    ratio = len(text) / max(len(scene_text), 1)
    if not 0.8 <= ratio <= 1.4:
        raise HTTPException(status_code=502, detail=(
            f"The finishing pass changed the length too much ({len(scene_text)} to {len(text)} characters); the scene text is unchanged."))
    added = []
    for it in data.get("added") or []:
        if isinstance(it, dict) and str(it.get("phrase") or "").strip():
            p = str(it["phrase"]).strip()
            added.append({"phrase": p, "note": str(it.get("note") or "").strip(), "found": p in text})
    conflicts = [str(c).strip() for c in (data.get("conflicts") or []) if str(c).strip()]
    warnings = sorted({m.group(0).lower() for m in _WEAVE_WARN_RE.finditer(text)}
                      | {m.group(0) for m in _WEAVE_STREET_RE.finditer(text)})
    return {"scene_text": text, "added": added, "conflicts": conflicts, "removed": structure_removed(scene_text, text),
            "warnings": warnings}


# =========================================================================
# WEFT PASS (2026-10-15, revised 2026-10-16; named the weft pass 2026-10-17): throw an LSA Studio run's weft
# (surfaces, condition, biology, species) through the scene text's warp (structure). Formerly "the weave"; the
# code keeps its old identifiers (weave_lsa_into_scene, /api/lsa/weave).
# The bag and the placement (DECISIONS.md, 2026-10-16): LSA Studio decides what the scene contains;
# the pipeline decides form and position. Names go in (the director's layout and the analysis may use
# street and place names); position words come out (the scene text the image model reads never does).
# Every structural item the pass adds is listed with a status for Don to keep or remove:
#   confirmed = in the director's layout, the scene text or plainly in the capture
#   proposed  = recalled by the LSA analysis only
# Light, weather, season and time are excluded and set aside for the render stage.
# =========================================================================

LSA_WEAVE_INSTRUCTION = """You are an architectural conservator and urban ecologist merging descriptions of one real place for an image model.
You receive:
IMAGE 1: a 3D capture of the view being rendered. It fixes what is in frame, where each element sits, and how far it is from the camera. Its surface detail is unreliable.
SCENE TEXT: the current scene description. The director has reviewed and edited it. It is the base text you revise.
DIRECTOR'S LAYOUT: the director's own description of this view, checked on site and in street-level photography. It may use street names, house numbers and storey counts. Everything structural in it is CONFIRMED.
LSA ANALYSIS: a deep domain analysis of the same place by another model. It is the authority on what the scene contains: materials, how they were made and worked, condition, chemistry, biology and species. Structure it recalls that the director's layout, the scene text and IMAGE 1 do not show is PROPOSED, not confirmed.
ECOLOGY RECORD: the current time-invariant description of the trees and plants, used later to age them through the seasons.

Return the scene text with the analysis's knowledge woven in and the director's layout applied.

THE LAYOUT OUTRANKS THE SCENE TEXT: where the DIRECTOR'S LAYOUT is more specific than the SCENE TEXT about the same element (which windows are blind or glazed on which floor and bay, which openings are arched or flat-headed, how many bays), rewrite the scene text's wording for that element to match the layout, keep it attached to that element, and list it in added_structure as confirmed from the layout.

KEEP FROM THE SCENE TEXT:
- Every structure and ground surface it names, in the same order, with its massing, storeys, bays, windows, doors, roof forms and openings.
- Its surface-first style: each structure opens with how its walls look today, then the material beneath.
- Its specific wording and qualifiers ("dashed" lane markings, "like the basements", a stated comparison or count): replace a word only with something more specific, never with something more general.
- Every rendering directive, word for word and in its place: any sentence about geometric accuracy, plumb verticals, planar facades, sharp ridgelines, or how to render rather than what is there.

STRUCTURE, IN THREE STATUSES:
- CONFIRMED: storeys, bays, roof forms, dormers, attics, openings, arches, blind windows, railings and other structure named in the DIRECTOR'S LAYOUT or the SCENE TEXT, or plainly shown in IMAGE 1. Add confirmed structure the scene text lacks, for structures visible in IMAGE 1, attached to the structure it belongs to.
- PROPOSED: structure only the LSA ANALYSIS names (for example a paving type, a cornice or parapet type, finials, a roof form, a feature on a facade the director did not mention). Add it where it belongs, as a separate short clause so it can be removed cleanly.
- Never add structure that contradicts the DIRECTOR'S LAYOUT or IMAGE 1; list it in not_added.
List EVERY structural feature that is in your scene text but was not in the original SCENE TEXT in added_structure, with its status. Surface condition, materials and biology are not structure and are not listed.

PERMANENT FIXTURES: street lamps and lamp posts, railings, bollards, post boxes, fixed benches, signposts and nameplates (described, never their text) are fixed to the ground or to a building and stay all year. They are not clutter. Keep every fixture the SCENE TEXT names. A fixture the DIRECTOR'S LAYOUT names or IMAGE 1 plainly shows is CONFIRMED; one only the analysis names is PROPOSED, added only where IMAGE 1 has room for it. Each added fixture is listed in added_structure. Describe each by form, material and finish, with detail by distance as for every other element. Transient things (bins, cones, temporary signs, vehicles, people) stay out.

STOREYS: count floors of windows above the ground the viewer stands on. A top floor whose windows sit in the wall face is a floor and is counted, whatever it is called; say what is above it (a cornice, a parapet, and whether the roof shows behind it). Only windows set in a roof slope (dormers) belong to the roof. Say which buildings each roof form belongs to; never give one roof sentence for every building. Name the roof form as the layout or IMAGE 1 gives it. Floors below street level are not counted; name them separately. Example of the form: "three floors of windows with a fourth floor set into the roof, one floor below street level".

NAMES IN, POSITIONS OUT: the DIRECTOR'S LAYOUT and the analysis may locate things by street names and house numbers. Translate each into words that point at IMAGE 1: which facade, which side, near or far, the long front, the short return, the corner building, the row beyond. Keep the fact exactly (which openings have which shape; which buildings have which roof form). The scene text you return never contains street names, house numbers or place names.

ADD FROM THE ANALYSIS, only for structures and surfaces visible in IMAGE 1:
- material type and source, how it was worked or finished (tooling, dressing, coursing, plaster, render, paint), mortar or binder
- condition: soiling, crusts, fading, staining, runoff channels, cracking, erosion, efflorescence, spalling, repairs and patching, corrosion and paint wear, and where each concentrates
- biology on surfaces: lichen, moss and algae, by species where the analysis names them, and where moisture and shelter put them
- ground materials: paving, kerbs, edging, unpaved ground
Name colours as they would look under flat, even overcast daylight, never warmed by sunlight. Attach each addition to the element it describes, in the same sentence or the one after it. Never place an addition between an element and the thing fixed to it (never between a wall and the railing on top of it).

DETAIL BY DISTANCE: judge each element's distance from IMAGE 1. Near elements get the full detail. Mid-distance elements get colour, staining and where soiling gathers. Far elements get overall tone in a few words.

NEVER ADD:
- Light, sun, cast shadows, sky, weather, wetness, dampness or time of day, including weathering described by its cause ("rain-washed", "sun-bleached", "damp-stained"): describe the mark instead (pale, cleaner, darker, streaked, crusted, stained, bleached). Exposure terms are allowed: sheltered, exposed, shaded by mature trees, under projections, drip lines.
- Season: leaf state or colour, fallen leaves, flowering, fruiting, fungal leaf spots.
- Compass directions or aspects ("north-facing"): turn them into exposure terms.
- Street names, house numbers, place names, dates, numeric rendering parameters, or camera and lens language.

SPECIES: trees keep the scene text's species, unless the analysis or the director's layout names a more specific or different species for the same trees; then use that name in both the scene text and the ecology record, and list it in species_to_verify. Never add trees IMAGE 1 does not show. The ecology record names exactly the species the scene text names, and stays time-invariant: form, height, trunk, bark and branch structure.

STYLE AND LENGTH: the scene text's telegraphic notation. The message gives the target length in characters: return a scene_text inside that range, and never over 3000 characters. Rewriting the whole text more compactly is not shortening to fit: keep every sentence about structure as it is. If you must shorten to fit, shorten surface description (condition, biology, tooling) of far elements first; never drop structure, and never cut the subject's details.

Return JSON only, in exactly this shape:
{"scene_text": "the revised scene text",
 "ecology": "the revised ecology record",
 "added_structure": [{"phrase": "the exact words as they appear in your scene_text", "status": "confirmed" or "proposed", "source": "layout", "analysis" or "capture", "note": "a few words: what it is and why"}],
 "species_to_verify": ["Latin name", "..."],
 "set_aside": "one short paragraph: the light, weather, season and time details in the analysis that were left out",
 "not_added": "one short paragraph: structural claims not added because they contradict the director's layout or IMAGE 1, or are not visible in it"}"""

# Words that should not survive the weave; their presence is reported, not fatal.
_WEAVE_WARN_RE = re.compile(
    r"\b(?:north|south|east|west)(?:ern|erly|-facing|\s+facing)?\b|\b(?:sun|sunlight|sunlit|shadows?|golden|"
    r"autumn|autumnal|spring|summer|winter|october|november|yellowing|fallen leaves|wet|rain|damp|frost|frosty|snow|glistening|puddles?|sky|"
    r"degrees?|mm lens|lens)\b", re.IGNORECASE)
# Street-like names (case-sensitive): "Nelson St", "Abercromby Place", "Queen Street".
_WEAVE_STREET_RE = re.compile(
    r"\b[A-Z][a-z]+\s+(?:Place|Pl|Street|St|Row|Crescent|Square|Terrace|Lane|Road|Rd|Avenue|Ave|Circus|Gardens?|Boulevard|Blvd|Drive|Dr|Way|Court|Ct|Trail|Highway|Hwy)\b\.?"
    r"|\b(?:Calle|Camino|Paseo|Avenida|Plaza|Rue|Via|Viale|Strasse|Straße)\s+(?:(?:de|del|la|los|las|du|des)\s+)*[A-Z][a-z]+")


def _clean_added(raw: Any, scene: str) -> List[Dict[str, Any]]:
    """The added-structure list, tidied: each item has phrase, status, source, note and whether
    the phrase was found word for word in the returned scene text (so the page can remove it)."""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for it in raw:
        if not isinstance(it, dict):
            continue
        phrase = str(it.get("phrase") or "").strip()
        if not phrase:
            continue
        status = str(it.get("status") or "").strip().lower()
        out.append({
            "phrase": phrase,
            "status": status if status in ("confirmed", "proposed") else "proposed",
            "source": str(it.get("source") or "").strip().lower() or "analysis",
            "note": str(it.get("note") or "").strip(),
            "found": phrase in scene,
        })
    return out


WEAVE_CAP = 3000   # the LSA pass's ceiling on scene text length (Don, 2026-10-24; was 2900)


def weave_lsa_into_scene(
    capture_b64: str,
    scene_text: str,
    ecology_text: str,
    analysis: str,
    gemini_api_key: Optional[str] = None,
    director_layout: Optional[str] = None,
) -> Dict[str, Any]:
    """The LSA pass. Returns scene_text, ecology, added_structure, species_to_verify, set_aside, not_added
    and warnings. Raises HTTPException(502) and changes nothing if the result is empty, unparseable or the wrong length."""
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")
    raw = capture_b64.split(",", 1)[1] if capture_b64.startswith("data:") else capture_b64
    mime = capture_b64.split(";")[0].replace("data:", "") if capture_b64.startswith("data:") else "image/jpeg"
    contents = [
        "IMAGE 1 (the composition being rendered):",
        types.Part.from_bytes(data=base64.b64decode(raw), mime_type=mime),
        f"SCENE TEXT:\n{scene_text}",
        f"DIRECTOR'S LAYOUT:\n{(director_layout or '').strip() or '(none given)'}",
        f"ECOLOGY RECORD:\n{ecology_text or '(none)'}",
        f"LSA ANALYSIS:\n{analysis}",
        "Return the JSON.",
    ]
    cfg = dict(
        system_instruction=LSA_WEAVE_INSTRUCTION,
        temperature=0.0,
        response_mime_type="application/json",
        thinking_config=types.ThinkingConfig(thinking_budget=4096),
    )
    if hasattr(types, "AutomaticFunctionCallingConfig"):
        cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
    # 2026-10-24 (Don): the cap is 3000 characters (was 2900), and the model is told the target range in numbers.
    # The temperature is 0, so pressing ADD again repeats the same miss: on a length miss the pass retries once by
    # itself, telling the model how far out it was. The floor stays at 80 per cent: a bigger cut drops structure.
    n = len(scene_text)
    hi = min(WEAVE_CAP, max(int(n * 1.7), n))
    lo = min(int(n * 0.9), hi - 150)
    contents.insert(-1, f"LENGTH: the SCENE TEXT above is {n} characters. Return a scene_text between {lo} and {hi} characters "
                        f"(never over {WEAVE_CAP}). Keep every structural sentence; add the analysis's surfaces to the elements they describe.")
    client = genai.Client(api_key=api_key)

    def _attempt(extra: Optional[str]):
        call = list(contents)
        if extra:
            call.insert(-1, extra)
        try:
            response = client.models.generate_content(
                model=DOMAIN_MODEL, contents=call, config=types.GenerateContentConfig(**cfg),
            )
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=502, detail=f"The LSA pass call failed: {e}")
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (response.text or "").strip())
        try:
            data = json.loads(text)
        except Exception:
            raise HTTPException(status_code=502, detail="The LSA pass did not return valid JSON; the scene text is unchanged.")
        if not isinstance(data, dict):
            raise HTTPException(status_code=502, detail="The LSA pass returned the wrong shape; the scene text is unchanged.")
        out = str(data.get("scene_text") or "").strip()
        if not out:
            raise HTTPException(status_code=502, detail="The LSA pass came back empty; the scene text is unchanged.")
        return data, out

    def _length_ok(out: str) -> bool:
        ratio = len(out) / max(n, 1)
        return 0.8 <= ratio <= 2.0 and len(out) <= WEAVE_CAP

    data, out = _attempt(None)
    if not _length_ok(out):
        first = len(out)
        print(f"[LSA pass] length miss: {n} to {first} characters (target {lo} to {hi}); retrying once")
        data, out = _attempt(
            f"YOUR LAST ANSWER was {first} characters, outside the range. Return it again between {lo} and {hi} characters. "
            + ("Too short: put back the structure and detail you cut; only far surfaces may be brief." if first < lo
               else "Too long: shorten surface description of far elements first; never structure or the subject."))
        if not _length_ok(out):
            raise HTTPException(status_code=502, detail=(
                f"The LSA pass changed the length too much twice ({n} to {first}, then {len(out)} characters; "
                f"the target was {lo} to {hi}); the scene text is unchanged."))
    species = data.get("species_to_verify") or []
    species = [str(s).strip() for s in species if str(s).strip()] if isinstance(species, list) else []
    warnings = sorted({m.group(0).lower() for m in _WEAVE_WARN_RE.finditer(out)}
                      | {m.group(0) for m in _WEAVE_STREET_RE.finditer(out)})
    return {
        "scene_text": out,
        "ecology": str(data.get("ecology") or "").strip(),
        "added_structure": _clean_added(data.get("added_structure"), out),
        "species_to_verify": species,
        "set_aside": str(data.get("set_aside") or "").strip(),
        "not_added": str(data.get("not_added") or "").strip(),
        "warnings": warnings,
        "removed": structure_removed(scene_text, out),
    }
