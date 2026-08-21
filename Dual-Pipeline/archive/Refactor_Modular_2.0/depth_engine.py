"""
Depth Engine - Monocular Depth Estimation Module (Perception Layer)
Encapsulates Depth Anything V2 Large for architectural geometry extraction.
"""

import os
import sys
import time
import glob
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Optional
import numpy as np
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoModelForDepthEstimation


@dataclass
class DepthResult:
    """Standardized output contract for depth estimation."""
    depth_image: Image.Image       # 8-bit visual grayscale depth map
    depth_array: np.ndarray        # Float32 normalized array (0.0=near, 1.0=far)
    latency_ms: float              # Inference execution time
    model_id: str                  # Model checkpoint identifier
    device: str                    # Compute device (cuda / cpu)


class DepthEngine:
    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to keep weights resident in GPU VRAM across calls."""
        if cls._instance is None:
            cls._instance = super(DepthEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        model_id: str = "depth-anything/Depth-Anything-V2-Large-hf",
        device: Optional[str] = None,
        dtype: torch.dtype = torch.float16,
    ):
        if getattr(self, "_initialized", False):
            return

        self.model_id = model_id
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self.dtype = dtype if self.device == "cuda" else torch.float32

        print(f"[DepthEngine] Initializing {self.model_id} on {self.device} ({self.dtype})...")
        self.processor = AutoImageProcessor.from_pretrained(self.model_id)
        self.model = AutoModelForDepthEstimation.from_pretrained(
            self.model_id,
            dtype=self.dtype,
        ).to(self.device)
        self.model.eval()
        self._initialized = True
        device_name = torch.cuda.get_device_name(0) if self.device == "cuda" else "CPU"
        print(f"[DepthEngine] Loaded and ready on {device_name}.")

    @torch.inference_mode()
    def estimate(self, image_input: Union[str, Path, Image.Image]) -> DepthResult:
        """
        Runs monocular depth estimation on an input RGB image.
        Returns a structured DepthResult with visual and raw depth data.
        """
        if isinstance(image_input, (str, Path)):
            image = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, Image.Image):
            image = image_input.convert("RGB")
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")

        orig_w, orig_h = image.size
        start_time = time.perf_counter()

        # Preprocess input image for the vision transformer
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {
            k: v.to(device=self.device, dtype=self.dtype if v.dtype == torch.float32 else v.dtype)
            for k, v in inputs.items()
        }

        # Model forward pass
        outputs = self.model(**inputs)
        predicted_depth = outputs.predicted_depth

        # Ensure tensor is 4D (batch, channels, height, width) for spatial interpolation
        if predicted_depth.ndim == 3:
            predicted_depth = predicted_depth.unsqueeze(1)

        # Bilinear/Bicubic upscale to match original resolution
        prediction = torch.nn.functional.interpolate(
            predicted_depth,
            size=(orig_h, orig_w),
            mode="bicubic",
            align_corners=False,
        ).squeeze()

        # Convert to numpy float32
        depth_np = prediction.detach().cpu().numpy().astype(np.float32)

        # Relative normalization to [0.0, 1.0]
        depth_min = depth_np.min()
        depth_max = depth_np.max()
        if depth_max > depth_min:
            norm_depth = (depth_np - depth_min) / (depth_max - depth_min)
        else:
            norm_depth = np.zeros_like(depth_np)

        # Create 8-bit visual grayscale image (255 = near, 0 = far)
        visual_depth = (norm_depth * 255.0).astype(np.uint8)
        depth_pil = Image.fromarray(visual_depth, mode="L")

        latency = (time.perf_counter() - start_time) * 1000.0

        return DepthResult(
            depth_image=depth_pil,
            depth_array=norm_depth,
            latency_ms=latency,
            model_id=self.model_id,
            device=self.device,
        )


# --- Standalone CLI Runner for Testing ---
if __name__ == "__main__":
    print("=== Depth Engine Standalone Diagnostic ===")
    engine = DepthEngine()

    test_image_path = None
    if len(sys.argv) > 1:
        test_image_path = sys.argv[1]
    else:
        # Search for any previous viewport capture in spatial_twin_runs
        run_captures = glob.glob("spatial_twin_runs/**/viewport_capture.jpg", recursive=True)
        if run_captures:
            test_image_path = sorted(run_captures, key=os.path.getmtime)[-1]
            print(f"[CLI] Found latest run capture: {test_image_path}")

    if not test_image_path or not os.path.exists(test_image_path):
        print("[CLI] No existing run capture found. Generating synthetic test image...")
        dummy = Image.new("RGB", (768, 512), color=(100, 140, 180))
        test_image_path = "test_input.jpg"
        dummy.save(test_image_path)

    print(f"[CLI] Running inference on: {test_image_path}")
    result = engine.estimate(test_image_path)

    output_path = "test_depth_preview.png"
    result.depth_image.save(output_path)

    print("-" * 50)
    print(f"[CLI] Execution Complete!")
    print(f"[CLI] Compute Device : {result.device}")
    print(f"[CLI] Inference Time : {result.latency_ms:.2f} ms")
    print(f"[CLI] Depth Map Saved: {os.path.abspath(output_path)}")
    print(f"[CLI] Array Shape    : {result.depth_array.shape}")
    print(f"[CLI] Array Range    : min={result.depth_array.min():.3f}, max={result.depth_array.max():.3f}")
    print("-" * 50)