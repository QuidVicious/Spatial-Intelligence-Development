"""
Synthesis Engine: Multi-Provider Generation Hub for 2D Visual Twins and 3D Worlds.
Supports Google Gemini Flash Image Models and World Labs Marble 3D World API.
Enforces standard 2560x1440 2K QHD 16:9 widescreen output via imageConfig.
"""

import os
import time
import base64
from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Union

import requests
from fastapi import HTTPException


class ModelProvider(str, Enum):
    GEMINI = "GEMINI"
    WORLD_LABS = "WORLD_LABS"


@dataclass
class SynthesisResult:
    """Unified output contract for 2D renders and 3D World generation."""
    provider: ModelProvider
    model_name: str
    image_b64: Optional[str] = None          # 2D Image output (Gemini)
    world_id: Optional[str] = None           # World Labs Marble World ID
    world_viewer_url: Optional[str] = None   # Interactive 3D World Web Link
    splat_url: Optional[str] = None          # Gaussian Splat asset (.spz or .ply)
    collider_mesh_url: Optional[str] = None  # Navigable collision mesh (.glb)
    pano_url: Optional[str] = None           # 360-degree panorama asset
    latency_ms: float = 0.0
    raw_response: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _extract_mime_and_data(b64_str: str) -> tuple[str, str]:
    if "," in b64_str and b64_str.startswith("data:"):
        header, raw_data = b64_str.split(",", 1)
        mime_type = header.split(";")[0].replace("data:", "").strip()
        return mime_type, raw_data
    return "image/png", b64_str


def synthesize_gemini_image(
    prompt: str,
    screenshot_b64: Optional[str] = None,
    model_name: str = "gemini-3.1-flash-image",
    temperature: float = 0.0,
    gemini_api_key: Optional[str] = None
) -> SynthesisResult:
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    start_time = time.perf_counter()
    parts: List[Dict[str, Any]] = []

    # 1. Reference Albedo Tensor First
    if screenshot_b64:
        mime_type, raw_b64 = _extract_mime_and_data(screenshot_b64)
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": raw_b64
            }
        })
    
    # 2. Master Prompt Payload
    parts.append({"text": prompt})

    # 3. Payload with 2560x1440 2K QHD Lock
    payload: Dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": temperature,
            "imageConfig": {
                "aspectRatio": "16:9",
                "imageSize": "2K"
            }
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    try:
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=90)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini Synthesis Connection Error: {str(e)}")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Gemini Synthesis Error: {resp.text}")

    resp_json = resp.json()
    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=500, detail=f"Gemini returned no candidates: {resp_json}")

    res_parts = candidates[0].get("content", {}).get("parts", [])
    for part in res_parts:
        data_holder = part.get("inlineData") or part.get("inline_data")
        if data_holder and "data" in data_holder:
            img_data = data_holder["data"]
            mime = data_holder.get("mimeType") or data_holder.get("mime_type", "image/png")
            latency = (time.perf_counter() - start_time) * 1000.0
            return SynthesisResult(
                provider=ModelProvider.GEMINI,
                model_name=model_name,
                image_b64=f"data:{mime};base64,{img_data}",
                latency_ms=latency,
                raw_response=resp_json
            )

    text_feedback = [p.get("text") for p in res_parts if "text" in p]
    raise HTTPException(status_code=500, detail=f"Model returned text without image: {text_feedback}")


def synthesize_worldlabs_marble(
    prompt: str,
    visual_input: Optional[Union[str, List[str]]] = None,
    input_type: str = "text",
    display_name: str = "Spatial Twin World (2560x1440 16:9)",
    model_name: str = "marble-1.1-plus",
    disable_recaption: bool = True,
    poll_interval: float = 4.0,
    max_wait_sec: float = 300.0,
    world_labs_api_key: Optional[str] = None
) -> SynthesisResult:
    api_key = (
        world_labs_api_key
        or os.getenv("WORLD_LABS_API_KEY")
        or os.getenv("WLT_API_KEY")
    )
    if not api_key:
        raise HTTPException(status_code=500, detail="WORLD_LABS_API_KEY is not configured.")

    start_time = time.perf_counter()
    headers = {
        "WLT-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    world_prompt: Dict[str, Any] = {
        "disable_recaption": disable_recaption
    }

    if input_type == "text" or not visual_input:
        world_prompt["type"] = "text"
        world_prompt["text_prompt"] = prompt
    elif input_type == "image" and isinstance(visual_input, str):
        world_prompt["type"] = "image"
        world_prompt["text_prompt"] = prompt
        world_prompt["image"] = visual_input
    elif input_type == "pano" and isinstance(visual_input, str):
        world_prompt["type"] = "panorama"
        world_prompt["text_prompt"] = prompt
        world_prompt["panorama"] = visual_input
    elif input_type == "multi_image" and isinstance(visual_input, list):
        world_prompt["type"] = "multi_image"
        world_prompt["text_prompt"] = prompt
        world_prompt["multi_view_images"] = visual_input

    payload: Dict[str, Any] = {
        "display_name": display_name[:64],
        "model": model_name,
        "world_prompt": world_prompt
    }

    base_url = "https://api.worldlabs.ai/marble/v1"
    create_url = f"{base_url}/worlds:generate"

    try:
        resp = requests.post(create_url, json=payload, headers=headers, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"World Labs Connection Error: {str(e)}")

    if resp.status_code not in [200, 201, 202]:
        raise HTTPException(status_code=resp.status_code, detail=f"World Labs API Error: {resp.text}")

    init_json = resp.json()
    operation_id = init_json.get("operation_id") or init_json.get("id")
    poll_url = init_json.get("operation_url") or f"{base_url}/operations/{operation_id}"

    elapsed = 0.0
    while elapsed < max_wait_sec:
        time.sleep(poll_interval)
        elapsed = time.perf_counter() - start_time

        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=20)
            if poll_resp.status_code == 200:
                status_data = poll_resp.json()
                state = status_data.get("status", "").upper()

                if state in ["COMPLETED", "SUCCEEDED", "READY"]:
                    world_data = status_data.get("world", status_data.get("result", {}))
                    latency = (time.perf_counter() - start_time) * 1000.0

                    return SynthesisResult(
                        provider=ModelProvider.WORLD_LABS,
                        model_name=model_name,
                        world_id=world_data.get("id", operation_id),
                        world_viewer_url=world_data.get("viewer_url") or world_data.get("url"),
                        splat_url=world_data.get("splat_url") or world_data.get("spz_url"),
                        collider_mesh_url=world_data.get("collider_mesh_url") or world_data.get("mesh_url"),
                        pano_url=world_data.get("pano_url") or world_data.get("imagery", {}).get("pano_url"),
                        image_b64=world_data.get("thumbnail_b64"),
                        latency_ms=latency,
                        raw_response=status_data
                    )
                elif state in ["FAILED", "ERROR"]:
                    raise HTTPException(status_code=500, detail=f"World Labs generation failed: {status_data}")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            print(f"[World Labs Poll Warning]: {e}")

    raise HTTPException(status_code=504, detail="World Labs Marble generation timed out.")


def synthesize_twin(
    prompt: Any,
    provider: Union[ModelProvider, str] = ModelProvider.GEMINI,
    model_name: Optional[str] = None,
    screenshot_b64: Optional[str] = None,
    multi_view_images: Optional[List[str]] = None,
    disable_recaption: bool = True,
    gemini_api_key: Optional[str] = None,
    world_labs_api_key: Optional[str] = None,
    **kwargs
) -> SynthesisResult:
    prov = ModelProvider(provider) if isinstance(provider, str) else provider
    prompt_text = prompt.prompt if hasattr(prompt, "prompt") else str(prompt)

    if prov == ModelProvider.WORLD_LABS:
        target_model = model_name or "marble-1.1-plus"
        input_type = "multi_image" if multi_view_images else ("image" if screenshot_b64 else "text")
        visual_data = multi_view_images if multi_view_images else screenshot_b64

        return synthesize_worldlabs_marble(
            prompt=prompt_text,
            visual_input=visual_data,
            input_type=input_type,
            model_name=target_model,
            disable_recaption=disable_recaption,
            world_labs_api_key=world_labs_api_key
        )
    else:  # GEMINI
        target_model = model_name or "gemini-3.1-flash-image"
        return synthesize_gemini_image(
            prompt=prompt_text,
            screenshot_b64=screenshot_b64,
            model_name=target_model,
            gemini_api_key=gemini_api_key
        )