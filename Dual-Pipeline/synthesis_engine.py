"""
Synthesis Engine: Multi-Provider Generation Hub for 2D Visual Twins and 3D Worlds.

Gemini path is unchanged.

World Labs path rewritten against the published Marble OpenAPI schema
(docs.worldlabs.ai/api/reference/worlds/generate). Corrections:

  world_prompt.image            -> world_prompt.image_prompt, and it is an
                                   object with a `source` discriminator, not
                                   a bare string.
  type "panorama"               -> type "image" with is_pano: true
  type "multi_image"            -> type "multi-image" (hyphen)
  world_prompt.multi_view_images-> world_prompt.multi_image_prompt, a list of
                                   {azimuth, content} objects
  polling on `status` string    -> polling on `done` boolean, with `error`
                                   and `response` per the operation schema
"""

import os
import time
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
    image_b64: Optional[str] = None
    world_id: Optional[str] = None
    world_viewer_url: Optional[str] = None
    splat_url: Optional[str] = None
    collider_mesh_url: Optional[str] = None
    pano_url: Optional[str] = None
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


def _media_reference(b64_str: str) -> Dict[str, Any]:
    """Build a DataBase64Reference. Marble wants raw base64, no data: prefix."""
    mime, raw = _extract_mime_and_data(b64_str)
    ext = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}.get(mime, "png")
    return {"source": "data_base64", "data_base64": raw, "extension": ext}


# =========================================================================
# GEMINI  (unchanged)
# =========================================================================

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

    if screenshot_b64:
        mime_type, raw_b64 = _extract_mime_and_data(screenshot_b64)
        parts.append({"inlineData": {"mimeType": mime_type, "data": raw_b64}})

    parts.append({"text": prompt})

    payload: Dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "temperature": temperature,
            "imageConfig": {"aspectRatio": "16:9", "imageSize": "2K"}
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


# =========================================================================
# WORLD LABS MARBLE
# =========================================================================

BASE_URL = "https://api.worldlabs.ai/marble/v1"


def _dig(obj: Any, *keys) -> Optional[Any]:
    """Return the first non-empty value found for any of `keys`, at any depth."""
    if isinstance(obj, dict):
        for k in keys:
            v = obj.get(k)
            if v:
                return v
        for v in obj.values():
            found = _dig(v, *keys)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _dig(item, *keys)
            if found:
                return found
    return None


def build_world_prompt(
    prompt_text: str,
    input_mode: str = "text",
    image_b64: Optional[str] = None,
    multi_view_images: Optional[List[str]] = None,
    multi_view_azimuths: Optional[List[float]] = None,
    disable_recaption: bool = True
) -> Dict[str, Any]:
    """
    Build a world_prompt matching the Marble schema.
      input_mode: "text" | "image" | "pano" | "multi-image"
    """
    mode = (input_mode or "text").lower().replace("_", "-")

    if mode == "image" and image_b64:
        return {
            "type": "image",
            "image_prompt": _media_reference(image_b64),
            "is_pano": False,
            "text_prompt": prompt_text,
            "disable_recaption": disable_recaption
        }

    if mode == "pano" and image_b64:
        return {
            "type": "image",
            "image_prompt": _media_reference(image_b64),
            "is_pano": True,
            "text_prompt": prompt_text,
            "disable_recaption": disable_recaption
        }

    if mode == "multi-image" and multi_view_images:
        items = []
        for i, img in enumerate(multi_view_images[:8]):
            entry: Dict[str, Any] = {"content": _media_reference(img)}
            if multi_view_azimuths and i < len(multi_view_azimuths):
                entry["azimuth"] = multi_view_azimuths[i]
            items.append(entry)
        return {
            "type": "multi-image",
            "multi_image_prompt": items,
            "reconstruct_images": len(items) > 4,
            "text_prompt": prompt_text,
            "disable_recaption": disable_recaption
        }

    return {
        "type": "text",
        "text_prompt": prompt_text,
        "disable_recaption": disable_recaption
    }


def synthesize_worldlabs_marble(
    prompt: str,
    input_mode: str = "text",
    image_b64: Optional[str] = None,
    multi_view_images: Optional[List[str]] = None,
    multi_view_azimuths: Optional[List[float]] = None,
    display_name: str = "Spatial Twin",
    model_name: str = "marble-1.1",
    disable_recaption: bool = True,
    seed: Optional[int] = None,
    poll_interval: float = 5.0,
    max_wait_sec: float = 600.0,
    world_labs_api_key: Optional[str] = None
) -> SynthesisResult:
    api_key = world_labs_api_key or os.getenv("WORLD_LABS_API_KEY") or os.getenv("WLT_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="WORLD_LABS_API_KEY / WLT_API_KEY is not configured.")

    start_time = time.perf_counter()
    headers = {"WLT-Api-Key": api_key, "Content-Type": "application/json"}

    world_prompt = build_world_prompt(
        prompt_text=prompt,
        input_mode=input_mode,
        image_b64=image_b64,
        multi_view_images=multi_view_images,
        multi_view_azimuths=multi_view_azimuths,
        disable_recaption=disable_recaption
    )

    payload: Dict[str, Any] = {
        "display_name": display_name[:64],
        "model": model_name,
        "world_prompt": world_prompt
    }
    if seed is not None:
        payload["seed"] = seed

    try:
        resp = requests.post(f"{BASE_URL}/worlds:generate", json=payload, headers=headers, timeout=60)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"World Labs Connection Error: {str(e)}")

    if resp.status_code == 402:
        raise HTTPException(status_code=402, detail="World Labs: insufficient API credits.")
    if resp.status_code not in (200, 201, 202):
        raise HTTPException(status_code=resp.status_code, detail=f"World Labs API Error: {resp.text}")

    init_json = resp.json()
    operation_id = init_json.get("operation_id")
    if not operation_id:
        raise HTTPException(status_code=500, detail=f"World Labs returned no operation_id: {init_json}")

    poll_url = f"{BASE_URL}/operations/{operation_id}"
    print(f"[Marble] operation {operation_id} started, mode={world_prompt['type']}, model={model_name}")

    while (time.perf_counter() - start_time) < max_wait_sec:
        time.sleep(poll_interval)
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=30)
        except Exception as e:
            print(f"[Marble] poll network warning: {e}")
            continue

        if poll_resp.status_code != 200:
            print(f"[Marble] poll returned {poll_resp.status_code}: {poll_resp.text[:200]}")
            continue

        op = poll_resp.json()

        if not op.get("done"):
            meta = op.get("metadata") or {}
            if meta:
                print(f"[Marble] working... {meta}")
            continue

        err = op.get("error")
        if err:
            raise HTTPException(status_code=500, detail=f"World Labs generation failed: {err}")

        result = op.get("response") or {}
        pano_url_fallback = _dig(result.get("assets", {}) if isinstance(result, dict) else {}, "pano_url")
        latency = (time.perf_counter() - start_time) * 1000.0
        print(f"[Marble] done in {latency/1000:.1f}s. Response keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

        return SynthesisResult(
            provider=ModelProvider.WORLD_LABS,
            model_name=model_name,
            world_id=_dig(result, "world_id", "id") or operation_id,
            world_viewer_url=_dig(result, "world_marble_url", "viewer_url", "world_url", "share_url", "url"),
            splat_url=_dig(result, "spz_urls", "splat_url", "spz_url", "ply_url", "gaussian_url"),
            collider_mesh_url=_dig(result, "collider_mesh_url", "mesh_url", "glb_url", "collision_mesh_url"),
            image_b64=_dig(result, "thumbnail_b64"),
            pano_url=_dig(result, "pano_url", "panorama_url", "equirect_url") or pano_url_fallback,
            latency_ms=latency,
            raw_response=op
        )

    raise HTTPException(status_code=504, detail=f"World Labs generation timed out after {max_wait_sec}s (operation {operation_id}).")


# =========================================================================
# DISPATCH
# =========================================================================

def synthesize_twin(
    prompt: Any,
    provider: Union[ModelProvider, str] = ModelProvider.GEMINI,
    model_name: Optional[str] = None,
    screenshot_b64: Optional[str] = None,
    multi_view_images: Optional[List[str]] = None,
    disable_recaption: bool = True,
    gemini_api_key: Optional[str] = None,
    world_labs_api_key: Optional[str] = None,
    marble_input_mode: str = "text",
    display_name: str = "Spatial Twin",
    **kwargs
) -> SynthesisResult:
    prov = ModelProvider(provider) if isinstance(provider, str) else provider
    prompt_text = prompt.prompt if hasattr(prompt, "prompt") else str(prompt)

    if prov == ModelProvider.WORLD_LABS:
        # marble_input_mode defaults to "text" deliberately: the photogrammetry
        # plate is not a trustworthy seed for a world model. Set "image",
        # "pano", or "multi-image" once a clean seed exists.
        mode = marble_input_mode
        if mode == "multi-image" and not multi_view_images:
            mode = "text"
        if mode in ("image", "pano") and not screenshot_b64:
            mode = "text"

        return synthesize_worldlabs_marble(
            prompt=prompt_text,
            input_mode=mode,
            image_b64=screenshot_b64,
            multi_view_images=multi_view_images,
            model_name=model_name or "marble-1.1",
            disable_recaption=disable_recaption,
            display_name=display_name,
            world_labs_api_key=world_labs_api_key
        )

    return synthesize_gemini_image(
        prompt=prompt_text,
        screenshot_b64=screenshot_b64,
        model_name=model_name or "gemini-3.1-flash-image",
        gemini_api_key=gemini_api_key
    )
