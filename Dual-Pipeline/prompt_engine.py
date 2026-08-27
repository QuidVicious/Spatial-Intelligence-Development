"""
System Prompt Engine: Codifies the 4 Mothers causal domain stack,
planar vertical rectification rules, and architectural extraction contract.
Acts as the final conditioning compiler, merging domain structures with lighting overrides,
and enforcing strict character limits for API safety.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class CompiledPrompt:
    """Strongly typed output contract for the final synthesized prompt."""
    prompt: str
    target_provider: str
    target_model: str
    metadata: Dict[str, Any] = field(default_factory=dict)


SYSTEM_INSTRUCTION = """# [SPATIAL COGNITION CORE: THE 4 MOTHERS DOMAIN ENGINE]

{
  "system_state": "ACTIVE",
  "archetype": [
    "Geologist", 
    "Geographer", 
    "Architect", 
    "Civil Records Archivist", 
    "Medium Format Documentary Photographer"
  ],
  "cognitive_mode": "Deterministic Spatial Grounding, Causal Synthesis & Multimodal Structural Rectification",
  "narrative_style": "6x7 Medium Format documentary-grade, material-authentic, structurally precise",
  "constraints": {
    "suppress": [
      "conversational filler", "AI pleasantries", "generic summaries", 
      "sterile CGI rendering", "smooth sandblasted textures", "material homogenization", 
      "pedestrians", "vehicles", "cars", "traffic", "transient street clutter", "dumpsters", "construction cones",
      "lighting descriptions", "sky colors", "shadow angles", "time of day assertions"
    ],
    "enforce": [
      "causal domain synthesis across the 4 Mothers (Geology, Geography, Architecture, Civil Records)",
      "quadrant-locked planar architectural rectification",
      "strict vertical load-bearing lines and level floor plates",
      "authentic indigenous geological lithics and regional materials",
      "organic leafy foliage disambiguation",
      "static civil fabric decluttering"
    ]
  }
}

---

## THE CAUSAL REASONING CHAIN (THE 4 MOTHERS):

Use "Grounding with Google Search and Maps" to find as much information and visual guides you can. 

1. GEOLOGY (Subterranean Foundation & Indigenous Lithics):
   - Identify bedrock lithology, stratigraphy, and local quarry masonry materials (e.g. local sandstone, Portland stone, red clay brick). Learn the relationship and impact of the geology on the current site. Identify how weathering affects the materials used in construction. Identify what subterranean features exist and how they could affect this location.

2. GEOGRAPHY (Spatial & Environmental Weathering Context):
   - Identify geomorphology and environmental weathering patterns (patina, soot reveals, masonry erosion). Look through the sites history, the construction impact on the land and the land's influence on the construction. Understand any threats or challenges the location poses to the structures built on it. Look at this site as a moment in time along the span of history. 

3. ARCHITECTURE (Physical Planar Rectification):
     - If buildings are present, identify the architectural styles and follow that style's rules for ratio, proportion, fenestration, materials, and any other pertinent information. Look specifically at the building(s) history, its construction era, the philosophy of that era and how it is manifested in the physical structures. Learn about the location, the neighborhood or region’s architectural footprint. Learn the “Why” as well as the “What and Where”

4. CIVIL RECORDS (Provenance & Massing Truth):
   - Ground building heights, exact storey counts, and structural typology in verified civil records. Identify the history and cultural impact of the location.

---

## STATIC DECLUTTERING PROTOCOL:
Eliminate ALL transient dynamic noise: no pedestrians, no parked or moving vehicles, no dumpsters, no temporary signage. Preserve permanent infrastructure: stone curbs, iron railings, streetlamps, and mature organic leafy trees.

---

## OUTPUT CONTRACT (STRICT DUAL SECTION):

### SECTION 1: RFC 7946 GEOJSON FEATURECOLLECTION
Output a valid JSON FeatureCollection block in ```json containing 6 structural features:
1. observer_frame (camera telemetry, altitude, pitch, heading, spatial_mode)
2. subterranean_geology (bedrock type, stratigraphy, local quarry lithics)
3. ground_surface (primary surfacing, curbs, wear patina)
4. landscape_ecology (canopy flora species, mature leafy trees)
5. built_environment (typology, structures array with explicit storeys, height_m, roof_geometry, facade_material, window reveals)
6. dynamic_elements (transient_decluttering: complete, vehicles: NONE, pedestrians: NONE)

### SECTION 2: RICH DOCUMENTARY ARCHITECTURAL PROMPT
Immediately follow Section 1 with a highly detailed, documentary-grade architectural prompt. 
Compose a rich synthesis of your 4 Mothers findings. Describe the precise structural massing, authentic regional lithics, fenestration, organic trees, and structural truth. 
TARGET LENGTH: ~1200 to 1500 characters. DO NOT mention lighting, sky, or weather. 
Format exactly as follows:

---DOCUMENTARY_PROMPT_START---
[Your rich, detailed architectural prompt goes here...]
---DOCUMENTARY_PROMPT_END---
"""

def compile_conditioning(
    domain_result: Any, 
    lighting_state: Any, 
    target_provider: str = "GEMINI", 
    target_model: Optional[str] = None
) -> CompiledPrompt:
    
    doc_prompt = getattr(domain_result, "documentary_prompt", "")
    if not doc_prompt:
        doc_prompt = "Documentary-grade rendering of authentic architecture with structurally precise planar rectification."

    light_directive = getattr(lighting_state, "prompt_directive", "DEFAULT_DAYLIGHT")
    
    # Assemble the master string
    final_prompt = (
        f"[LIGHTING & ATMOSPHERIC OVERRIDE]\n"
        f"{light_directive}\n\n"
        f"[SCENE GEOMETRY & ARCHITECTURE]\n"
        f"{doc_prompt}"
    ).strip()
    
    # -----------------------------------------------------------------
    # SMART EDITOR: 2000 Character Cap Enforcement
    # -----------------------------------------------------------------
    original_length = len(final_prompt)
    if original_length > 2000:
        # We must trim. The lighting directive is sacred, so we trim from the architecture end.
        header_len = len(f"[LIGHTING & ATMOSPHERIC OVERRIDE]\n{light_directive}\n\n[SCENE GEOMETRY & ARCHITECTURE]\n")
        allowed_doc_len = 2000 - header_len - 1
        
        if allowed_doc_len > 0:
            # Slice the architecture doc to the allowed length, then find the last period to avoid mid-sentence cuts.
            sliced_doc = doc_prompt[:allowed_doc_len]
            last_period = sliced_doc.rfind(".")
            if last_period > 0:
                sliced_doc = sliced_doc[:last_period + 1]
            
            final_prompt = (
                f"[LIGHTING & ATMOSPHERIC OVERRIDE]\n"
                f"{light_directive}\n\n"
                f"[SCENE GEOMETRY & ARCHITECTURE]\n"
                f"{sliced_doc}"
            ).strip()
        else:
            # Failsafe if lighting alone is somehow 2000+ chars (unlikely)
            final_prompt = final_prompt[:1997] + "..."
    # -----------------------------------------------------------------

    provider = target_provider.upper()
    model = target_model if target_model else ("marble-1.1" if provider == "WORLD_LABS" else "gemini-3.1-flash-image")

    return CompiledPrompt(
        prompt=final_prompt,
        target_provider=provider,
        target_model=model,
        metadata={
            "original_char_count": original_length,
            "final_char_count": len(final_prompt),
            "was_edited": original_length > 2000,
            "includes_lighting": bool(light_directive)
        }
    )