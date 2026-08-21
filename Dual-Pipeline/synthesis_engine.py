"""
Synthesis Engine: Pure execution client for multimodal visual twin synthesis.
Dispatches the compiled conditioning prompt and viewport capture to Gemini Image Generation.
"""

import os
import sys
import time
import glob
import base64
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

import requests
from fastapi import HTTPException
from PIL import Image

from prompt_compiler import CompiledConditioning


@dataclass
class SynthesisResult:
    """Strongly typed output contract for the Synthesis Engine."""
    image_b64: str
    model_name: str
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def synthesize_twin_image(
    conditioning: CompiledConditioning,
    screenshot_b64: str,
    gemini_api_key: Optional[str] = None
) -> SynthesisResult:
    """
    Dispatches compiled prompt and viewport image directly to gemini-3.1-flash-image.
    Returns the synthesized image as a standard base64 data URI.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured.")

    start_time = time.perf_counter()

    # Clean Base64 image payload
    raw_b64 = screenshot_b64.split(",")[-1] if "," in screenshot_b64 else screenshot_b64

    # Build REST payload for Gemini 3.1 Flash Image
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": conditioning.prompt},
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
            "temperature": conditioning.temperature,
            "topP": conditioning.top_p
        }
    }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{conditioning.model_name}:generateContent?key={api_key}"
    
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=90
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image Synthesis Connection Error: {str(e)}")

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Image Synthesis API Error ({resp.status_code}): {resp.text}"
        )

    resp_json = resp.json()
    candidates = resp_json.get("candidates", [])
    if not candidates:
        raise HTTPException(status_code=500, detail=f"Synthesis model returned no candidates: {resp_json}")

    parts = candidates[0].get("content", {}).get("parts", [])
    
    # Extract base64 image data
    for part in parts:
        if "inlineData" in part and "data" in part["inlineData"]:
            img_data = part["inlineData"]["data"]
            mime = part["inlineData"].get("mimeType", "image/png")
            latency = (time.perf_counter() - start_time) * 1000.0
            return SynthesisResult(
                image_b64=f"data:{mime};base64,{img_data}",
                model_name=conditioning.model_name,
                latency_ms=latency
            )
        elif "inline_data" in part and "data" in part["inline_data"]:
            img_data = part["inline_data"]["data"]
            mime = part["inline_data"].get("mime_type", "image/png")
            latency = (time.perf_counter() - start_time) * 1000.0
            return SynthesisResult(
                image_b64=f"data:{mime};base64,{img_data}",
                model_name=conditioning.model_name,
                latency_ms=latency
            )

    text_feedback = [p.get("text") for p in parts if "text" in p]
    raise HTTPException(
        status_code=500,
        detail=f"Synthesis model returned text without image payload: {text_feedback}"
    )


# --- Standalone CLI Runner for Testing ---
if __name__ == "__main__":
    from dotenv import load_dotenv

    env_path = Path(r"C:\DEV\Squid\SquidBlack\.env")
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    print("=" * 60)
    print("=== Synthesis Engine Standalone Diagnostic ===")
    print("=" * 60)

    # 1. Locate test image
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
            print(f"[CLI] Created temporary test image: {test_img}")

    with open(test_img, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    # 2. Test prompt conditioning
    test_conditioning = CompiledConditioning(
        prompt=(
            "An eye-level medium format view looking across the street: A 3-storey Craigleith sandstone "
            "Georgian townhouse crescent with plumb vertical facades, crisp rectangular sash windows, "
            "and level slate rooflines. Authentic honey ashlar masonry with subtle soot patina in reveals "
            "and lush organic sycamore trees. Calibrated 5400K crisp midday solar illumination with sharp "
            "directional shadows across a clean, static street completely free of pedestrians and vehicles."
        ),
        spatial_mode="3D_RECTIFICATION",
        model_name="gemini-3.1-flash-image",
        temperature=0.2,
        top_p=0.30,
        metadata={"word_count": 200}
    )

    print(f"[CLI] Dispatching image synthesis request to {test_conditioning.model_name}...")
    result = synthesize_twin_image(test_conditioning, img_b64)

    # 3. Save resulting image to disk for verification
    output_path = Path("test_synthesized_twin.png")
    raw_output_b64 = result.image_b64.split(",")[-1]
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(raw_output_b64))

    print(f"[CLI] Synthesis Successful!")
    print(f"[CLI] Model       : {result.model_name}")
    print(f"[CLI] Latency     : {result.latency_ms:.1f} ms")
    print(f"[CLI] Image Saved : {output_path.resolve()}")
    print("=" * 60)
    print("[CLI] Step 3 Complete. Ready for Step 4 (Archiver).")
    print("=" * 60)