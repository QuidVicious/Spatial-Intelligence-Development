import os
import requests
from io import BytesIO
from PIL import Image
import torch
from transformers import pipeline

# ==========================================
# CONFIGURATION
# ==========================================
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_CLOUD_API_KEY_HERE"

# You can use "Lat,Long" OR an address/intersection string:
LOCATION = "40.7128, -74.0060" 

# Optional camera controls:
HEADING = "0"     # 0 = North, 90 = East, 180 = South, 270 = West
PITCH = "0"       # 0 = Eye level (-90 looking down, 90 looking up)
FOV = "90"        # Field of view (default 90)
SIZE = "1024x1024"# High-res square for image generation

# ==========================================
# 1. FETCH STREET VIEW RGB IMAGE
# ==========================================
print(f"[*] Fetching Street View image for location: {LOCATION}...")

url = (
    f"https://maps.googleapis.com/maps/api/streetview"
    f"?size={SIZE}"
    f"&location={LOCATION}"
    f"&heading={HEADING}"
    f"&pitch={PITCH}"
    f"&fov={FOV}"
    f"&key={GOOGLE_MAPS_API_KEY}"
)

response = requests.get(url)

if response.status_code != 200:
    raise Exception(f"Failed to fetch image: HTTP {response.status_code}")

rgb_image = Image.open(BytesIO(response.content)).convert("RGB")
rgb_image.save("streetview_rgb.png")
print("[+] Saved 'streetview_rgb.png'")

# ==========================================
# 2. RUN MONOCULAR DEPTH ESTIMATION
# ==========================================
print("[*] Loading Depth Anything V2 model...")

device = 0 if torch.cuda.is_available() else -1
depth_estimator = pipeline(
    task="depth-estimation",
    model="depth-anything/Depth-Anything-V2-Small-hf",
    device=device
)

print("[*] Generating depth map...")
depth_result = depth_estimator(rgb_image)
depth_map = depth_result["depth"]

# Save grayscale depth map
depth_map.save("streetview_depth.png")
print("[+] Saved 'streetview_depth.png' successfully!")