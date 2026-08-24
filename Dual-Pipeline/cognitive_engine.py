"""
Cognitive Engine: Dispatches telemetry and viewport imagery to Gemini 3.7 Flash.
Pure structural cognition: extracts geometry, indigenous lithics, and decluttered scene essence.
Completely decoupled from lighting and weather physics.
"""

import os
import re
import json
import base64
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

import requests
from fastapi import HTTPException
from google import genai
from google.genai import types

from prompt_engine import SYSTEM_INSTRUCTION


@dataclass
class CognitiveResult:
    """Strongly typed output contract for pure spatial cognition."""
    address: str
    spatial_mode: str
    geojson: Dict[str, Any]
    distilled_prompt: str
    raw_response: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def reverse_geocode(lat: float, lon: float, google_maps_api_key: Optional[str] = None) -> str:
    """Converts GPS coordinates into a verified postal address or locality."""
    key = (
        google_maps_api_key
        or os.getenv("GOOGLE_MAPS_API_KEY")
        or os.getenv("GOOGLE_MAPS_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or os.getenv("MAPS_API_KEY")
    )

    # 1. Try Google Maps Geocoding API
    if key:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={key}"
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", [])
                if results:
                    addr = results[0].get("formatted_address")
                    print(f"[Geocode Success (Google)]: {addr}")
                    return addr
                elif "error_message" in data:
                    print(f"[Google Geocode Info]: {data.get('status')} - {data.get('error_message')}")
        except Exception as e:
            print(f"[Google Geocode Warning]: {e}")

    # 2. Try BigDataCloud Free Client Geocoding (Fast, global, free)
    try:
        bdc_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={lat}&longitude={lon}&localityLanguage=en"
        resp = requests.get(bdc_url, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            locality = data.get("locality") or data.get("city")
            admin_area = data.get("principalSubdivision") # State/Province (e.g. New Mexico)
            country = data.get("countryName") # Country (e.g. United States)
            
            parts = [p for p in [locality, admin_area, country] if p]
            if parts:
                addr = ", ".join(parts)
                print(f"[Geocode Success (BigDataCloud)]: {addr}")
                return addr
    except Exception as e:
        print(f"[BigDataCloud Warning]: {e}")

    # 3. Try OpenStreetMap Nominatim
    try:
        osm_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat:.5f}&lon={lon:.5f}&zoom=12&addressdetails=1"
        headers = {"User-Agent": "SpatialIntelligencePipeline/1.0 (dev@local.internal)"}
        resp = requests.get(osm_url, headers=headers, timeout=3)
        if resp.status_code == 200:
            res_json = resp.json()
            addr_data = res_json.get("address", {})
            loc = (
                addr_data.get("city")
                or addr_data.get("town")
                or addr_data.get("county")
                or addr_data.get("natural")
            )
            state = addr_data.get("state")
            country = addr_data.get("country")
            parts = [p for p in [loc, state, country] if p]
            if parts:
                addr = ", ".join(parts)
                print(f"[Geocode Success (OSM)]: {addr}")
                return addr
    except Exception as e:
        print(f"[OSM Warning]: {e}")

    # 4. Ultimate fallback
    return f"{lat:.4f}°, {lon:.4f}°"


def query_the_eye(
    address: str,
    telemetry: Any,
    screenshot_b64: str,
    gemini_api_key: Optional[str] = None
) -> CognitiveResult:
    """
    Sends viewport capture and telemetry to Gemini 3.7 Flash for pure structural rectification
    and lithic material analysis.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    # 1. Clean Base64 image
    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    image_bytes = base64.b64decode(raw_b64)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    # 2. Extract Telemetry Parameters
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
- Resolved Address: {address}
- GPS Coordinates: {lat:.6f}, {lon:.6f}
- Altitude (AGL): {altitude_agl:.1f} meters
- Camera Orientation: Heading {heading:.1f}°, Pitch {pitch:.1f}°, FOV {fov:.1f}°
- Tile Mode: {tile_mode}
"""

    user_instruction = (
        "Execute causal spatial cognition across the 4 Mothers (Geology, Geography, Architecture, Civil Records). "
        "Deliberate on the physical site reality, resolve all architectural geometry into plumb planar verticality, "
        "and output:\n"
        "1. The RFC 7946 GeoJSON FeatureCollection (Strata 1-6) in a ```json codeblock.\n"
        "2. The 2-Sentence Distilled Architectural Essence Prompt delimited between "
        "'---DOCUMENTARY_PROMPT_START---' and '---DOCUMENTARY_PROMPT_END---'."
    )

    if is_2d_satellite:
        user_instruction += (
            f"\n\nSEARCH DIRECTIVE (2D Extrusion Grounding):\n"
            f"Search civil and architectural records for property/structures at ({lat:.6f}, {lon:.6f}) near '{address}' "
            f"to establish documented storey counts, roof geometry, and facade materials."
        )

    client = genai.Client(api_key=api_key)
    tools = [{"google_search": {}}] if is_2d_satellite else None

    # Low-entropy inference constraints
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.15,
        top_p=0.25,
        thinking_config=types.ThinkingConfig(thinking_budget=1024),
        tools=tools
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=[telemetry_summary, image_part, user_instruction],
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cognitive Engine Error: {str(e)}")

    candidate_text = response.text or ""

    # Parse GeoJSON cleanly
    geojson_data = {}
    geojson_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate_text, re.DOTALL)
    if geojson_match:
        try:
            geojson_data = json.loads(geojson_match.group(1))
        except Exception as err:
            print(f"[GeoJSON Parse Warning]: {err}")

    # Extract 2-Sentence Essence Prompt
    if "---DOCUMENTARY_PROMPT_START---" in candidate_text:
        distilled_prompt = candidate_text.split("---DOCUMENTARY_PROMPT_START---")[-1]
        distilled_prompt = distilled_prompt.split("---DOCUMENTARY_PROMPT_END---")[0].strip()
    else:
        distilled_prompt = re.sub(r"```(?:json)?.*?```", "", candidate_text, flags=re.DOTALL).strip()

    # Determine Spatial Mode
    top_props = geojson_data.get("properties", {}) if isinstance(geojson_data.get("properties"), dict) else {}
    spatial_mode = top_props.get("spatial_mode")
    if not spatial_mode:
        for feat in geojson_data.get("features", []):
            if isinstance(feat, dict) and "spatial_mode" in feat.get("properties", {}):
                spatial_mode = feat["properties"]["spatial_mode"]
                break

    if spatial_mode not in ["3D_RECTIFICATION", "2D_EXTRUSION"]:
        spatial_mode = "3D_RECTIFICATION" if tile_mode == "3D_TILES" else "2D_EXTRUSION"

    return CognitiveResult(
        address=address,
        spatial_mode=spatial_mode,
        geojson=geojson_data,
        distilled_prompt=distilled_prompt,
        raw_response=candidate_text
    )