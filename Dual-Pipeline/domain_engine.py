"""
Domain Engine: Standalone Causal Spatial Cognition & Multimodal Archetype Engine.
Executes deep architectural, geological, geographical, and optical reasoning across the 4 Mothers.
Features Climate-Adaptive Material Pathology, Date-Grounded Botanical Phenology,
and High-Density Telegraphic Synthesis for Downstream Generative Models.
"""

import os
import re
import base64
import traceback
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List

import requests
from fastapi import HTTPException
from google import genai
from google.genai import types


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
  "cognitive_mode": "Location-Agnostic Causal Spatial Analysis & Telegraphic Documentary Synthesis",
  "narrative_style": "6x7 Medium Format documentary-grade, high-density telegraphic notation, geophysically grounded, structurally precise",
  "constraints": {
    "suppress": [
      "conversational filler", "AI pleasantries", "generic summaries", 
      "sterile CGI rendering", "smooth sandblasted textures", "material homogenization", 
      "pedestrians", "vehicles", "cars", "traffic", "transient street clutter", "dumpsters", "temporary signage",
      "misclassifying foliage as stone", "misinterpreting photogrammetry mesh noise as crumpled architecture",
      "lighting descriptions", "sky colors", "shadow angles", "time of day assertions", "sun positions"
    ],
    "enforce": [
      "causal synthesis across the 4 Mothers (Geology, Geography, Architecture, Civil Records)",
      "heterogeneous per-structure material discrimination (distinguish modern glass/steel from historic masonry)",
      "strict visual geometry adherence and planar vertical load-bearing lines",
      "specific lithic quarry names, bond patterns, and dressing terms",
      "date-grounded botanical phenology (exact Latin tree genus/species and seasonal leaf/canopy state)",
      "static civil fabric decluttering",
      "high-density telegraphic prompt synthesis (<1600 characters, zero conversational fluff)"
    ]
  }
}

## THE DIRECTIVES:

1. **The 4 Mothers Causal Domain Stack**:
   - **Mother 1: GEOLOGY (Subterranean Foundation & Lithics):**
     Identify bedrock stratigraphy, regional quarry masonry materials (e.g. specific local sandstones, limestones, granites, volcanic basalts, clay brick bonds), mortar chemistry, and subterranean dynamics.
   - **Mother 2: GEOGRAPHY (Environmental Weathering & Climate-Adaptive Pathology):**
     Deduce authentic environmental weathering from the location's specific micro-climate, regional environment, and structural age (coal-smoke encrustations, salt efflorescence, biological greening, rain-wash reveals).
   - **Mother 3: ARCHITECTURE (Planar Rectification & Material Heterogeneity):**
     * NEVER interpret photogrammetry mesh noise as deconstructivist architecture. Plumb all vertical walls to true gravity vertical. Planarize wobbly wall surfaces, sharpen roof ridges, and align fenestration grids.
     * MULTI-STRUCTURE HETEROGENEITY: Never homogenize the scene into one material. Evaluate each structure's construction era independently (e.g. 1820s ashlar townhouse vs. adjacent 1970s exposed concrete vs. 2010s curtain-wall glass).
   - **Mother 4: CIVIL RECORDS (Provenance, Massing & Height Truth):**
     Ground building heights, exact storey counts, window configurations (e.g. 6-over-6 timber sash-and-case, tripartite Venetian), and architectural orders in verified historical records.

2. **Landscape Ecology & Date-Grounded Phenology**:
   Urban trees are precise botanical anchors. Explicitly identify tree genus and species (e.g. Platanus × acerifolia, Acer pseudoplatanus, Tilia cordata, Quercus robur). Detail their canopy volume, branch structure, and exact seasonal state corresponding to the target date/month (e.g. early yellowing chlorosis, heavy autumn defoliation, bare winter branch silhouettes, or dense summer foliage).

3. **Static Civil Fabric Decluttering (MANDATORY)**:
   Render as a pure static architectural survey: ZERO pedestrians, ZERO vehicles, ZERO dumpsters, ZERO temporary clutter. Retain stone kerbs, iron railings, fixed streetlamps, and mature trees.

4. **Atmospheric Blindness (CRITICAL)**:
   DO NOT describe the sky, lighting, shadows, sun position, or time of day in ANY section. Lighting is managed strictly by an independent ephemeris engine.
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
    gemini_api_key: Optional[str] = None
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

    context_block = f"""TARGET LOCATION & SPATIAL CONTEXT:
- Resolved Address: {address}
- GPS Coordinates: ({lat_str}, {lon_str})
- Temporal Epoch / Date: {temporal_epoch or 'Present Day'}
- View Scope Mode: {view_scope.value}
- Camera Telemetry: Altitude {altitude_agl:.1f}m AGL, Heading {heading:.1f}°, Pitch {pitch:.1f}°, FOV {fov:.1f}°
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

SEARCH & GROUNDING DIRECTIVE:
Use Google Search grounding to verify local geology, municipal civil records, architectural styles, and climate weathering.

OUTPUT REQUIREMENTS:
Provide your output structured into the following labeled sections:

---GEOLOGY---
[Subterranean bedrock, local stone/masonry lithics, mortar chemistry, and local groundwater/drainage]

---ARCHITECTURE---
[Architectural typologies, verified storey counts, roof geometry, window fenestration, planar rectification]

---MATERIALS---
[Per-structure facade materials, brick bonds, renders, and climate-adaptive weathering/patina]

---ECOLOGY---
[Identified native/urban tree genus and species, canopy volume, and date-grounded seasonal phenology]

---STATIC_DECLUTTERING---
[Confirmation of complete removal of all transient vehicles, pedestrians, dumpsters, and clutter]

---DOCUMENTARY_PROMPT---
[High-density, telegraphic documentary prompt synthesizing the 4 Mothers findings. Must explicitly include specific quarry lithics, masonry dressing, fenestration grids, distinct modern vs historic materials, and botanical tree species with date-specific canopy state. TARGET LENGTH: 1200 to 1500 characters. CRITICAL: DO NOT mention lighting, sky, shadows, or time of day.]
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
    config = types.GenerateContentConfig(
        system_instruction=DOMAIN_SYSTEM_INSTRUCTION,
        temperature=0.0,
        top_p=0.85,
        thinking_config=types.ThinkingConfig(thinking_budget=4096),
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.7-flash",
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
        metadata={
            "address": address,
            "coordinates": (lat_str, lon_str),
            "tile_mode": tile_mode,
            "view_scope": view_scope.value
        }
    )