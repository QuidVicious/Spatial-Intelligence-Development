"""
Domain Engine: Standalone Causal Spatial Cognition & Multimodal Archetype Engine.
Executes deep architectural, geological, geographical, and optical reasoning across the 4 Mothers.
Operates independently with or without viewport captures, supporting Frustum, 360° Omni, and Standalone modes.
Features Climate-Adaptive Material Pathology (Location-Agnostic & Time-Grounded).
"""

import os
import re
import json
import base64
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

import requests
from fastapi import HTTPException
from google import genai
from google.genai import types


class ViewScope(str, Enum):
    FRUSTUM = "FRUSTUM"        # Single directional viewport (e.g. Gemini 2D image)
    OMNI_360 = "OMNI_360"      # 360-degree spherical environment (e.g. World Labs Marble)
    STANDALONE = "STANDALONE"  # Pure text/coordinate historical & spatial synthesis


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================================
# THE ALL-SEEING EYE SYSTEM INSTRUCTION (LOCATION-AGNOSTIC COGNITIVE CORE)
# =========================================================================

DOMAIN_SYSTEM_INSTRUCTION = """# [ALL SEEING EYE: ACTIVE COGNITIVE ANCHOR & DOMAIN CORE]

{
  "system_state": "ACTIVE",
  "archetype": [
    "Architect", 
    "Surveyor", 
    "Geologist", 
    "Geographer", 
    "Civil Records Archivist", 
    "Botanist", 
    "Optical Physics Specialist", 
    "Building Conservator", 
    "Medium Format Architectural Photographer"
  ],
  "cognitive_mode": "Location-Agnostic Causal Spatial Analysis & Documentary Synthesis",
  "narrative_style": "6x7 Medium Format documentary-grade, geophysically grounded, structurally precise, sensory-rich, material-authentic",
  "constraints": {
    "suppress": [
      "conversational filler", "AI pleasantries", "generic summaries", 
      "sterile CGI rendering", "smooth sandblasted textures", "material homogenization", 
      "pedestrians", "vehicles", "cars", "traffic", "transient street clutter", "dumpsters", "temporary paper posters",
      "misclassifying foliage as stone", "misinterpreting photogrammetry mesh noise as crumpled architecture"
    ],
    "enforce": [
      "causal synthesis across the 4 Mothers (Geology, Geography, Architecture, Civil Records)",
      "4-dimensional spatial depth and climate-adaptive environmental patina",
      "strict visual geometry adherence and planar vertical load-bearing lines",
      "per-structure material discrimination and indigenous lithics",
      "organic leafy foliage disambiguation",
      "static civil fabric decluttering",
      "6x7 medium format optical clarity (Mamiya 7, 45mm lens, ultra-fine grain film)"
    ]
  }
}

## THE DIRECTIVES:

1. **The Transparent Eyeball**: Relinquish conversational ego. You are a passive, highly sensitive lens—a silent eyeball through which the physical and historical reality of the world converges across space and time into a documentary representation.

2. **The 4 Mothers Causal Domain Stack**:
   - **Mother 1: GEOLOGY (Subterranean Foundation & Indigenous Lithics):**
     Identify bedrock lithology, stratigraphy, local quarry masonry materials (e.g. regional sandstones, oolitic limestones, volcanic basalts, clay brick bonds), mortar chemistry, and subterranean drainage dynamics.
   - **Mother 2: GEOGRAPHY (Environmental Weathering & Climate-Adaptive Pathology):**
     * NEVER render architecture as freshly constructed, pristine CGI, or sandblasted.
     * Causally deduce authentic environmental weathering from the location's specific micro-climate, regional environment, and the structure's chronological age:
       * *Humid / Subtropical / Coastal (e.g., Florida, Caribbean, Gulf Coast):* Dark biological algae/mildew striations (Gloeocapsa magma), salt-aerosol efflorescence, UV paint chalking, moisture oxidation, and humidity patina.
       * *Historic / Post-Industrial Temperate (e.g., UK, Central Europe, Rust Belt):* Gypsum crusting, historic carbon deposition in sheltered reveals/cornices, rainwater wash patterns, and softened ashlar joint lines.
       * *Arid / Desert (e.g., American Southwest, Middle East, Mediterranean):* Intense solar UV bleaching, windborne silicate grit micro-abrasion, fine dust accumulation in horizontal recesses, and thermal hairline expansion fissures.
       * *Cold / Freeze-Thaw (e.g., Nordic, Canadian, Alpine):* Frost spalling, mortar expansion fractures, moisture leaching along lower plinths, and natural unpainted timber graying.
   - **Mother 3: ARCHITECTURE (Physical Planar Rectification & Anti-Warp Protocol):**
     * Photogrammetry 3D meshes frequently distort glass, balconies, and reflective facades into melted polygon noise. **NEVER** interpret melted polygon noise as deconstructivist architecture.
     * Plumb all vertical walls to true gravity vertical. Planarize wobbly wall surfaces, sharpen roof ridges, rectify fenestration, and ensure all balcony slabs, canopies, and floor plates are laser-straight horizontal planes.
     * Differentiate every structure in view independently—never blanket-apply a single material across all buildings.
   - **Mother 4: CIVIL RECORDS (Provenance, Massing & Height Truth):**
     Ground building heights, exact storey counts, and structural typology in verified civil records and historical construction eras. Primary residential/commercial structures must never be collapsed into low ground decals; enforce true habitable heights (≥6.5m–8.0m floor-to-ridge floors).

3. **Landscape Ecology & Foliage Disambiguation**:
   Photogrammetry meshes render urban trees as crumpled geometric blocks. **NEVER** describe foliage as stone or masonry. Explicitly render all trees as mature organic vegetation with distinct botanical species (e.g. London plane trees, live oaks, palmettos, sycamores), leafy canopies, and natural branching.

4. **Static Civil Fabric Decluttering (MANDATORY)**:
   Render the scene as a pure static architectural documentary photograph.
   - **Strip All Transient Noise:** ZERO pedestrians, ZERO motor vehicles (parked or moving), ZERO dumpsters, and ZERO temporary construction clutter.
   - **Preserve Permanent Infrastructure:** Retain stone curbs, iron railings, fixed streetlamps, engraved signage, and mature street trees.

5. **Optical & Documentary Lens**:
   Ground the visual description as captured on a 6x7 medium format camera (Mamiya 7 rangefinder, 45mm wide-angle lens, ISO 100 fine-grain film, f/8 aperture for deep corner-to-corner sharpness).
"""


def reverse_geocode(lat: float, lon: float, google_maps_api_key: Optional[str] = None) -> str:
    """Converts GPS coordinates into a verified postal address or locality."""
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

    # Fallback to BigDataCloud client API
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
    lighting_description: Optional[str] = None,
    temporal_epoch: Optional[str] = None,
    gemini_api_key: Optional[str] = None
) -> DomainAnalysisResult:
    """
    Executes pure causal spatial domain reasoning across the 4 Mothers.
    Can run standalone (text/GPS only) or multimodally with a viewport capture.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    client = genai.Client(api_key=api_key)

    # 1. Build Location & Telemetry Context
    lat_str = f"{coordinates[0]:.6f}" if coordinates else (f"{getattr(telemetry, 'latitude', 0.0):.6f}" if telemetry else "Unknown")
    lon_str = f"{coordinates[1]:.6f}" if coordinates else (f"{getattr(telemetry, 'longitude', 0.0):.6f}" if telemetry else "Unknown")
    altitude_agl = getattr(telemetry, "altitude_agl", 0.0) if telemetry else 0.0
    heading = getattr(telemetry, "heading", 0.0) if telemetry else 0.0
    pitch = getattr(telemetry, "pitch", -45.0) if telemetry else -45.0
    fov = getattr(telemetry, "fov", 45.0) if telemetry else 45.0
    tile_mode = getattr(telemetry, "tile_mode", "3D_TILES") if telemetry else "STANDALONE"

    context_block = f"""TARGET LOCATION & SPATIAL CONTEXT:
- Resolved Address: {address}
- GPS Coordinates: ({lat_str}, {lon_str})
- Temporal Epoch: {temporal_epoch or 'Present Day'}
- View Scope Mode: {view_scope.value}
- Camera Telemetry: Altitude {altitude_agl:.1f}m AGL, Heading {heading:.1f}°, Pitch {pitch:.1f}°, FOV {fov:.1f}°
- Tile Mode: {tile_mode}
"""
    if lighting_description:
        context_block += f"- Atmospheric & Solar Context: {lighting_description}\n"

    # 2. Configure View Scope Directives
    if view_scope == ViewScope.OMNI_360:
        scope_directive = (
            "SCOPE DIRECTIVE (360° OMNIDIRECTIONAL WORLD RECONSTRUCTION):\n"
            "Analyze and describe the entire 360-degree spatial environment enclosing the observer. "
            "Detail the Northern, Southern, Eastern, and Western perimeter structures, overhead canopy, and ground terrain. "
            "This description will be consumed by a 3D World Generation Model (World Labs Marble)."
        )
    elif view_scope == ViewScope.STANDALONE:
        scope_directive = (
            "SCOPE DIRECTIVE (STANDALONE CAUSAL ANALYSIS):\n"
            "No visual capture provided. Reconstruct the spatial reality from first principles using your deep knowledge "
            "of local geology, historical civil records, architectural vernacular, and landscape ecology."
        )
    else:  # FRUSTUM
        scope_directive = (
            "SCOPE DIRECTIVE (DIRECTIONAL FRUSTUM RECTIFICATION):\n"
            "Using the viewport capture as the absolute coordinate reference, break down the scene spatially across the frame: "
            "(A) Foreground/street level; (B) Center structures; (C) Left and right flanking structures. "
            "Plumb all verticals, rectify planar facades, and disambiguate organic foliage from masonry."
        )

    user_prompt = f"""{context_block}

{scope_directive}

SEARCH & GROUNDING DIRECTIVE:
Use Google Search grounding to verify local geology (indigenous bedrock, local quarries), municipal civil records, architectural styles, climate-specific weathering patterns, and native flora.

OUTPUT REQUIREMENTS:
Provide your output structured into the following labeled sections:

---GEOLOGY---
[Subterranean bedrock, local stone/masonry lithics, mortar chemistry, and local groundwater/drainage]

---ARCHITECTURE---
[Architectural typologies, verified storey counts, roof geometry, window fenestration, planar rectification, and anti-warp corrections]

---MATERIALS---
[Per-structure facade materials, brick bonds, renders, and climate-adaptive weathering/patina derived from the site's micro-climate and historical age]

---ECOLOGY---
[Identified native/urban tree and plant species, mature leafy canopies, and botanical characteristics]

---STATIC_DECLUTTERING---
[Confirmation of complete removal of all transient vehicles, pedestrians, dumpsters, and clutter while retaining permanent civil infrastructure]

---DOCUMENTARY_PROMPT---
[The complete, sensory-rich, highly descriptive documentary synthesis prompt for the generative image/world engine. Explicitly detail authentic climate-adaptive environmental weathering, realistic material age, differentiated facade lithics, mature leafy trees, and a completely static decluttered civil environment under calibrated optical clarity.]
"""

    contents: List[Any] = [user_prompt]

    # Attach viewport capture if present
    if screenshot_b64 and view_scope != ViewScope.STANDALONE:
        raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
        image_bytes = base64.b64decode(raw_b64)
        contents.insert(0, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

    # Execute Gemini inference with search grounding
    config = types.GenerateContentConfig(
        system_instruction=DOMAIN_SYSTEM_INSTRUCTION,
        temperature=0.35,
        top_p=0.85,
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
        tools=[{"google_search": {}}]
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=contents,
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Domain Engine Error: {str(e)}")

    response_text = response.text or ""

    # Parse Sections Cleanly
    def _extract_section(tag: str, text: str) -> str:
        pattern = rf"---{tag}---\s*(.*?)(?=---[A-Z_]+---|$)"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    geology = _extract_section("GEOLOGY", response_text)
    architecture = _extract_section("ARCHITECTURE", response_text)
    materials = _extract_section("MATERIALS", response_text)
    ecology = _extract_section("ECOLOGY", response_text)
    decluttering = _extract_section("STATIC_DECLUTTERING", response_text)
    doc_prompt = _extract_section("DOCUMENTARY_PROMPT", response_text)

    # Fallback if section delimiters were missed
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
        metadata={
            "address": address,
            "coordinates": (lat_str, lon_str),
            "tile_mode": tile_mode,
            "view_scope": view_scope.value
        }
    )