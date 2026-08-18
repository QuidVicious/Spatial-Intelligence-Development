"""
Cognitive Engine: Dispatches telemetry and viewport imagery to Gemini 3.7 Flash with High Reasoning,
handles conditional Search Grounding, parses RFC 7946 GeoJSON spatial scaffolds, and extracts documentary prompts.
"""
import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

import requests
from fastapi import HTTPException

BASE_DIR = Path(__file__).resolve().parent
PROMPT_TEMPLATE_PATH = BASE_DIR / "eye_prompt.md"


def reverse_geocode(lat: float, lon: float, google_maps_api_key: Optional[str]) -> str:
    """Converts GPS coordinates into a precise street address or locality."""
    if not google_maps_api_key:
        return f"{lat:.5f}, {lon:.5f}"
    
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={google_maps_api_key}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0].get("formatted_address", f"{lat:.5f}, {lon:.5f}")
    except Exception as e:
        print(f"[Reverse Geocode Error]: {e}")
    
    return f"{lat:.5f}, {lon:.5f}"


def query_the_eye(
    address: str,
    telemetry: Any,
    screenshot_b64: str,
    temporal_anchor: str,
    gemini_api_key: str
) -> Tuple[Dict[str, Any], str, str]:
    """Sends telemetry, image, and system instructions to Gemini 3.7 Flash."""
    if not gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    system_instruction = ""
    if PROMPT_TEMPLATE_PATH.exists():
        system_instruction = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    
    tile_mode = getattr(telemetry, "tile_mode", "3D_TILES")
    is_2d_satellite = (tile_mode == "2D_SATELLITE")
    
    lat = getattr(telemetry, "latitude", 0.0)
    lon = getattr(telemetry, "longitude", 0.0)
    altitude_agl = getattr(telemetry, "altitude_agl", 0.0)
    heading = getattr(telemetry, "heading", 0.0)
    pitch = getattr(telemetry, "pitch", -45.0)
    fov = getattr(telemetry, "fov", 45.0)

    telemetry_summary = f"""
TARGET LOCATION TELEMETRY:
- Resolved Address / Postal Sector: {address}
- GPS Coordinates: {lat:.6f}, {lon:.6f}
- Altitude (AGL): {altitude_agl:.1f} meters
- Camera Heading: {heading:.1f}°
- Camera Pitch: {pitch:.1f}°
- Camera Field of View (FOV): {fov:.1f}°
- Tile Rendering Mode: {tile_mode}
- Temporal Anchor: {temporal_anchor}
"""

    user_instruction = (
        "Execute 4D Spatial Cognition across all 5 strata. "
        "Output the RFC 7946 GeoJSON FeatureCollection in a ```json codeblock, followed immediately by "
        "'--- DOCUMENTARY PROMPT ---' and the 35mm documentary prompt.\n\n"
        "MANDATORY MASSING & HEIGHT SPECIFICATIONS:\n"
        "1. In the GeoJSON 'built_environment' feature, populate the 'structures' array with explicit 'storeys' (integer) "
        "and 'height_m' (float) for EVERY building (e.g. primary residence vs. agricultural barns/outbuildings).\n"
        "2. In the 35mm documentary prompt, SENTENCE 1 MUST explicitly declare the physical storey count and vertical height "
        "of the primary structure (e.g., 'A prominent 2-storey [materials] residence rising to [X]m elevation...'). "
        "Differentiate main structures from adjacent lower/higher outbuildings."
    )

    if is_2d_satellite:
        user_instruction += (
            f"\n\nSEARCH DIRECTIVE (Cascading Fallback Protocol):\n"
            f"1. Search specifically for any named property, farmstead, lodge, ranch, estate, or historic building located at coordinates "
            f"({lat:.6f}, {lon:.6f}) near '{address}'.\n"
            f"2. If a specific named property/building is identified, extract its documented storeys, roof type, masonry/finishes, fenestration, and landscaping records.\n"
            f"3. If no specific entity exists, fall back to the regional agricultural/vernacular typology and construction materials typical of this county/region.\n"
            f"4. Apply the 'Skeleton vs. Skin' rule: Use search findings for material textures and fenestration skin, but strictly respect the viewport footprint and camera perspective."
        )

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": telemetry_summary},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": raw_b64
                        }
                    },
                    {"text": user_instruction}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.25,
            "topP": 0.2,
            "thinkingConfig": {
                "thinkingBudget": 2048
            }
        }
    }

    if is_2d_satellite:
        print("[The Eye] Mode is 2D_SATELLITE -> Google Search Grounding active.")
        payload["tools"] = [{"googleSearch": {}}]
    else:
        print("[The Eye] Mode is 3D_TILES -> Latent spatial domain reasoning (Search disabled).")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key={gemini_api_key}"
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"The Eye (Gemini 3.7 Flash) Error: {resp.text}")

    resp_json = resp.json()
    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=500, detail=f"The Eye returned no candidates: {resp_json}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [p.get("text", "") for p in parts if "text" in p]
    candidate_text = "\n".join(text_parts)

    # 1. Parse GeoJSON cleanly
    geojson_data = {}
    geojson_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate_text, re.DOTALL)
    if geojson_match:
        try:
            geojson_data = json.loads(geojson_match.group(1))
        except Exception as err:
            print(f"[GeoJSON Parse Warning]: {err}")

    # 2. Extract clean prompt (strip out raw JSON blocks so image generator is never corrupted)
    if "--- DOCUMENTARY PROMPT ---" in candidate_text:
        doc_prompt = candidate_text.split("--- DOCUMENTARY PROMPT ---")[-1].strip()
    elif "Prompt:" in candidate_text:
        doc_prompt = candidate_text.split("Prompt:")[-1].strip()
    else:
        doc_prompt = re.sub(r"```(?:json)?.*?```", "", candidate_text, flags=re.DOTALL).strip()

    # 3. Resolve spatial mode
    top_props = geojson_data.get("properties", {}) if isinstance(geojson_data.get("properties"), dict) else {}
    spatial_mode = top_props.get("spatial_mode")
    if not spatial_mode:
        for feat in geojson_data.get("features", []):
            if isinstance(feat, dict) and "spatial_mode" in feat.get("properties", {}):
                spatial_mode = feat["properties"]["spatial_mode"]
                break

    if spatial_mode not in ["3D_RECTIFICATION", "2D_EXTRUSION"]:
        spatial_mode = "3D_RECTIFICATION" if tile_mode == "3D_TILES" else "2D_EXTRUSION"

    return geojson_data, doc_prompt, spatial_mode