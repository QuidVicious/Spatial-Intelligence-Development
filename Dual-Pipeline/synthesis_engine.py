"""
Synthesis Engine: Handles generative twin synthesis, compound structure massing extraction,
and dynamic mode parameter switching with Gemini 3.1 Flash Image.
"""
import os
from typing import Dict, Any
import requests
from fastapi import HTTPException


def extract_compound_massing(geojson_data: Dict[str, Any]) -> Dict[str, Any]:
    """Scans all features and nested structure arrays to extract massing metrics."""
    massing_info = {
        "primary_storeys": None,
        "primary_height_m": None,
        "has_compound_structures": False,
        "structures_summary": []
    }

    features = geojson_data.get("features", [])
    for feat in features:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties", {})
        
        # Check if this feature has a 'structures' array (compound site / farmstead)
        structures = props.get("structures", [])
        if isinstance(structures, list) and len(structures) > 0:
            massing_info["has_compound_structures"] = True
            for struct in structures:
                if isinstance(struct, dict):
                    name = struct.get("name") or struct.get("type", "Structure")
                    s_storeys = struct.get("storeys")
                    s_height = struct.get("height_m")
                    
                    if s_storeys or s_height:
                        massing_info["structures_summary"].append(
                            f"{name} ({s_storeys or 2} storeys, {s_height or 7.0}m elevation)"
                        )
                    
                    # Lock primary residence if detected
                    if massing_info["primary_storeys"] is None and s_storeys:
                        try:
                            massing_info["primary_storeys"] = int(s_storeys)
                        except (ValueError, TypeError):
                            pass
                    if massing_info["primary_height_m"] is None and s_height:
                        try:
                            massing_info["primary_height_m"] = float(s_height)
                        except (ValueError, TypeError):
                            pass

        # Also check direct feature properties
        if massing_info["primary_storeys"] is None and "storeys" in props:
            try:
                massing_info["primary_storeys"] = int(props["storeys"])
            except (ValueError, TypeError):
                pass
        if massing_info["primary_height_m"] is None and "height_m" in props:
            try:
                massing_info["primary_height_m"] = float(props["height_m"])
            except (ValueError, TypeError):
                pass

    # Top-level properties fallback
    top_props = geojson_data.get("properties", {}) if isinstance(geojson_data.get("properties"), dict) else {}
    if massing_info["primary_storeys"] is None and "storeys" in top_props:
        try:
            massing_info["primary_storeys"] = int(top_props["storeys"])
        except (ValueError, TypeError):
            pass
    if massing_info["primary_height_m"] is None and "height_m" in top_props:
        try:
            massing_info["primary_height_m"] = float(top_props["height_m"])
        except (ValueError, TypeError):
            pass

    # Enforce authoritative safety floors (prevent 1.5-storey prior collapse)
    massing_info["primary_storeys"] = massing_info["primary_storeys"] if massing_info["primary_storeys"] is not None else 2
    massing_info["primary_height_m"] = massing_info["primary_height_m"] if massing_info["primary_height_m"] is not None else 7.5

    return massing_info


def synthesize_twin_image(
    prompt: str,
    screenshot_b64: str,
    spatial_mode: str,
    telemetry: Any,
    geojson_data: Dict[str, Any],
    gemini_api_key: str
) -> str:
    """Dispatches prompt and viewport image to gemini-3.1-flash-image with massing constraints."""
    if not gemini_api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64
    massing = extract_compound_massing(geojson_data)
    
    pitch = getattr(telemetry, "pitch", -45.0)
    heading = getattr(telemetry, "heading", 0.0)

    # Build the massing constraint text
    if massing["structures_summary"]:
        compound_details = " Distinct compound heights: " + ", ".join(massing["structures_summary"]) + "."
    else:
        compound_details = ""

    if spatial_mode == "2D_EXTRUSION":
        temp = 0.25
        top_p = 0.75
        wrapper = (
            f"DIRECTIVE: VOLUMETRIC EXTRUSION FROM 2D SATELLITE FOOTPRINT.\n"
            f"MANDATORY MASSING: Erect primary structure to exactly {massing['primary_storeys']} full storeys "
            f"({massing['primary_height_m']}m vertical ridge elevation).{compound_details} "
            f"Do not render as a low flat 1-storey building. Eaves and roof ridges must rise distinctly above terrain. "
            f"Render elevated roof pitches and pronounced physical cast shadows on the ground plane, strictly matching camera pitch ({pitch:.1f}°) and heading ({heading:.1f}°). "
            f"Apply authentic surface materials across vertical facades. DO NOT paint textures flat on ground. Plumb all vertical walls perpendicular to terrain.\n\n"
            f"SCENE DESCRIPTION:\n{prompt}"
        )
    else:
        # Mode A: 3D Rectification with Hybrid Massing Safeguard
        temp = 0.2
        top_p = 0.35
        wrapper = (
            f"DIRECTIVE: UNIVERSAL GEOMETRIC RECTIFICATION & FACADE MASSING.\n"
            f"Treat the attached image as a true 3D geometric wireframe. Plumb all vertical walls to gravity vertical, "
            f"establish continuous planar surfaces, sharpen corner intersections, and rectify photogrammetry noise. "
            f"Preserve distinct vertical facade elevation ({massing['primary_storeys']} storeys / {massing['primary_height_m']}m ridge height for primary structures). "
            f"Do not allow building roofs to flatten into the terrain plane.\n\n"
            f"SCENE DESCRIPTION:\n{prompt}"
        )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": wrapper},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": raw_b64
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": temp,
            "topP": top_p
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent?key={gemini_api_key}"
    resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Image Synthesis Error: {resp.text}")

    resp_json = resp.json()
    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=500, detail=f"Synthesis model returned no candidates: {resp_json}")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if "inlineData" in part:
            return f"data:image/png;base64,{part['inlineData']['data']}"
        elif "inline_data" in part:
            return f"data:image/png;base64,{part['inline_data']['data']}"
    
    text_responses = [p.get("text") for p in parts if "text" in p]
    raise HTTPException(status_code=500, detail=f"Synthesis model did not return image data: {text_responses}")