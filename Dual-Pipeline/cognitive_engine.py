"""
Cognitive Engine: Dispatches telemetry, solar/floodlight physics, and viewport imagery
to Gemini 3.7 Flash with High Reasoning.
Executes causal analysis across the 4 Mothers (Geology, Geography, Architecture, Civil Records),
produces the RFC 7946 GeoJSON spatial database, and extracts the distilled 3-sentence visual essence prompt.
"""

import os
import re
import sys
import glob
import json
import base64
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

import requests
from PIL import Image
from fastapi import HTTPException
from google import genai
from google.genai import types

# Import domain instructions & lighting rig
from prompt_engine import SYSTEM_INSTRUCTION
from lighting_engine import resolve_lighting_state, LightingState, LightingMode


@dataclass
class CognitiveResult:
    """Strongly typed output contract for the Cognitive Engine."""
    address: str
    spatial_mode: str
    geojson: Dict[str, Any]
    distilled_prompt: str
    raw_response: str
    lighting_state: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def reverse_geocode(lat: float, lon: float, google_maps_api_key: Optional[str]) -> str:
    """Converts GPS coordinates into a verified postal address or locality."""
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
        print(f"[Reverse Geocode Warning]: {e}")

    return f"{lat:.5f}, {lon:.5f}"


def query_the_eye(
    address: str,
    telemetry: Any,
    screenshot_b64: str,
    temporal_anchor: str = "Present Day",
    gemini_api_key: Optional[str] = None
) -> CognitiveResult:
    """
    Sends viewport capture, telemetry, and deterministic lighting physics to Gemini 3.7 Flash.
    Synthesizes the 4 Mothers causal domain stack into GeoJSON and a distilled visual essence prompt.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    # 1. Clean Base64 image
    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    image_bytes = base64.b64decode(raw_b64)
    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

    # 2. Extract Telemetry & Lighting Parameters
    tile_mode = getattr(telemetry, "tile_mode", "3D_TILES")
    is_2d_satellite = (tile_mode == "2D_SATELLITE")
    lat = getattr(telemetry, "latitude", 0.0)
    lon = getattr(telemetry, "longitude", 0.0)
    altitude_agl = getattr(telemetry, "altitude_agl", 0.0)
    heading = getattr(telemetry, "heading", 0.0)
    pitch = getattr(telemetry, "pitch", -45.0)
    fov = getattr(telemetry, "fov", 45.0)
    timestamp_utc = getattr(telemetry, "timestamp_utc", None)
    lighting_mode = getattr(telemetry, "lighting_mode", "SOLAR")

    # 3. Deterministic Lighting Engine Resolution
    lighting_state = resolve_lighting_state(
        lat=lat,
        lon=lon,
        camera_heading=heading,
        camera_pitch=pitch,
        timestamp_utc=timestamp_utc,
        mode=lighting_mode
    )

    telemetry_summary = f"""
TARGET LOCATION TELEMETRY & DETERMINISTIC PHYSICAL STATE:
- Resolved Address / Postal Sector: {address}
- GPS Coordinates: {lat:.6f}, {lon:.6f}
- Altitude (AGL): {altitude_agl:.1f} meters
- Camera Orientation: Heading {heading:.1f}°, Pitch {pitch:.1f}°, FOV {fov:.1f}°
- Tile Rendering Mode: {tile_mode}
- Temporal Anchor: {temporal_anchor}
- Illumination Mode: {lighting_state.mode.value}
- Atmospheric & Lighting Physics: {lighting_state.prompt_directive}
"""

    user_instruction = (
        "Execute causal spatial cognition across the 4 Mothers (Geology, Geography, Architecture, Civil Records). "
        "Deliberate on the physical site reality, resolve all architectural geometry into plumb planar verticality, "
        "and output:\n"
        "1. The RFC 7946 GeoJSON FeatureCollection in a ```json codeblock (incorporating Stratum 7 atmospheric state).\n"
        "2. The 3-Sentence Distilled Essence Prompt delimited between '---DOCUMENTARY_PROMPT_START---' and '---DOCUMENTARY_PROMPT_END---'.\n"
        f"CRITICAL: Align the lighting and atmospheric description in Sentence 3 strictly with the calculated physics: {lighting_state.prompt_directive}"
    )

    if is_2d_satellite:
        user_instruction += (
            f"\n\nSEARCH DIRECTIVE (2D Extrusion Grounding):\n"
            f"Search civil and architectural records for property/structures at ({lat:.6f}, {lon:.6f}) near '{address}' "
            f"to establish documented storey counts, roof geometry, and facade materials."
        )

    # 4. Configure Gemini 3.7 Flash Call
    client = genai.Client(api_key=api_key)
    tools = [{"google_search": {}}] if is_2d_satellite else None

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2,
        top_p=0.3,
        thinking_config=types.ThinkingConfig(thinking_budget=2048),
        tools=tools
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents=[telemetry_summary, image_part, user_instruction],
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cognitive Engine (Gemini 3.7 Flash) Error: {str(e)}")

    candidate_text = response.text or ""

    # 5. Parse GeoJSON cleanly & Ensure Stratum 7 is Deterministic
    geojson_data = {}
    geojson_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate_text, re.DOTALL)
    if geojson_match:
        try:
            geojson_data = json.loads(geojson_match.group(1))
        except Exception as err:
            print(f"[GeoJSON Parse Warning]: {err}")

    # Inject/Enforce Deterministic Stratum 7 in GeoJSON
    if isinstance(geojson_data, dict) and "features" in geojson_data:
        features = geojson_data["features"]
        # Replace or append Stratum 7
        features = [f for f in features if f.get("properties", {}).get("stratum") != "atmospheric_state" and f.get("id") != "stratum_7_atmospheric_state"]
        features.append(lighting_state.geojson_stratum)
        geojson_data["features"] = features

    # 6. Extract Distilled 3-Sentence Essence Prompt
    if "---DOCUMENTARY_PROMPT_START---" in candidate_text:
        distilled_prompt = candidate_text.split("---DOCUMENTARY_PROMPT_START---")[-1]
        distilled_prompt = distilled_prompt.split("---DOCUMENTARY_PROMPT_END---")[0].strip()
    else:
        distilled_prompt = re.sub(r"```(?:json)?.*?```", "", candidate_text, flags=re.DOTALL).strip()

    # 7. Determine Spatial Mode
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
        raw_response=candidate_text,
        lighting_state=lighting_state.to_dict()
    )


# --- Standalone CLI Runner for Testing ---
if __name__ == "__main__":
    from dotenv import load_dotenv

    env_path = Path(r"C:\DEV\Squid\SquidBlack\.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    print("=" * 70)
    print("=== Cognitive Engine (The 4 Mothers + Lighting Rig) Standalone Diagnostic ===")
    print("=" * 70)

    # Locate test image
    test_img = Path("viewport_capture.jpg")
    if not test_img.exists():
        run_captures = glob.glob("spatial_twin_runs/**/viewport_capture.jpg", recursive=True)
        archive_captures = glob.glob("archive/**/*.jpg", recursive=True)
        all_candidates = run_captures + archive_captures
        
        if all_candidates:
            test_img = Path(sorted(all_candidates, key=os.path.getmtime)[-1])
            print(f"[CLI] Using discovered capture: {test_img}")
        else:
            test_img = Path("test_synthetic_view.jpg")
            dummy = Image.new("RGB", (800, 600), color=(100, 130, 160))
            dummy.save(test_img)
            print(f"[CLI] Created temporary synthetic test image: {test_img}")

    with open(test_img, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    class MockTelemetry:
        latitude = 55.953492
        longitude = -3.211036
        altitude_agl = 4.5
        heading = 315.0
        pitch = -12.0
        fov = 75.0
        tile_mode = "3D_TILES"
        timestamp_utc = "2026-08-20T17:30:00Z"
        lighting_mode = "SOLAR"

    print("[CLI] Dispatching viewport capture + Solar Ephemeris to Gemini 3.7 Flash...")
    result = query_the_eye(
        address="",
        telemetry=MockTelemetry(),
        screenshot_b64=img_b64,
        temporal_anchor="Present Day"
    )

    print("\n--- [1. RESOLVED SPATIAL MODE & LIGHTING] ---")
    print(f"Spatial Mode  : {result.spatial_mode}")
    print(f"Lighting Rig  : {result.lighting_state.get('mode') if result.lighting_state else 'N/A'}")

    print("\n--- [2. DISTILLED 3-SENTENCE ESSENCE PROMPT] ---")
    print(result.distilled_prompt)

    print("\n--- [3. RFC 7946 GEOJSON DATABASE (Features with Stratum 7)] ---")
    features = result.geojson.get("features", [])
    print(f"Features parsed: {len(features)}")
    for i, feat in enumerate(features, 1):
        props = feat.get("properties", {}) if isinstance(feat, dict) else {}
        stratum_name = props.get("stratum") or feat.get("id") or f"Stratum #{i}"
        print(f"  [{i}/{len(features)}] Stratum: {stratum_name}")

    print("=" * 70)
    print("[CLI] Step 3 Diagnostic Complete. Ready for Step 4 (Server & Viewfinder).")
    print("=" * 70)