import io
import base64
import torch
from PIL import Image
from transformers import pipeline

# 1. Initialize Depth Anything V2 once on import
print("[*] Initializing Depth Anything V2 engine...")
device = 0 if torch.cuda.is_available() else -1

depth_estimator = pipeline(
    task="depth-estimation",
    model="depth-anything/Depth-Anything-V2-Small-hf",
    device=device
)
print(f"[+] Depth service ready on {'GPU' if device == 0 else 'CPU'}")


def process_depth_from_base64(image_base64: str) -> str:
    """
    Takes a base64 RGB string from the Cesium canvas,
    runs Depth Anything V2, and returns a clean base64 depth map PNG.
    """
    # 1. Decode incoming base64 image
    if "," in image_base64:
        header, encoded = image_base64.split(",", 1)
    else:
        encoded = image_base64

    image_bytes = base64.b64decode(encoded)
    rgb_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 2. Run depth estimation
    depth_result = depth_estimator(rgb_image)
    depth_map = depth_result["depth"]

    # 3. Encode resulting depth map to base64 PNG
    buffered = io.BytesIO()
    depth_map.save(buffered, format="PNG")
    depth_base64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode("utf-8")

    return depth_base64