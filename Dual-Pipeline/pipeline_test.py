import os
from pathlib import Path
from io import BytesIO
import requests
from PIL import Image
from dotenv import load_dotenv
import torch
from transformers import pipeline

# ==============================================================================
# 1. LOAD ENVIRONMENT VARIABLES FROM .ENV
# ==============================================================================
# Direct path to your .env file:
ENV_PATH = Path(r"C:\DEV\Squid\SquidBlack\.env")

if not ENV_PATH.exists():
    # Fallback to 2 directories up if run from a subfolder
    ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

load_dotenv(dotenv_path=ENV_PATH)

# Fetch key with fallback names:
GOOGLE_MAPS_API_KEY = (
    os.getenv("GOOGLE_MAPS_API_KEY") 
    or os.getenv("GOOGLE_API_KEY") 
    or os.getenv("MAPS_API_KEY")
)

if not GOOGLE_MAPS_API_KEY:
    raise ValueError(
        f"Could not find GOOGLE_MAPS_API_KEY in '{ENV_PATH}'. "
        "Please make sure it is defined in your .env file."
    )

print(f"[+] Loaded API key successfully from: {ENV_PATH}")

# ==============================================================================
# 2. PIPELINE CONFIGURATION
# ==============================================================================
# Target location:
LOCATION = "55.9584, -3.1895" # London St., Edinburgh, UK example

# CHOOSE MODE: "STREET" or "AERIAL"
MODE = "AERIAL"

# --- AERIAL SETTINGS ---
AERIAL_ZOOM = 19        # 18 = neighborhood block, 19 = city block, 20 = close rooftops
IMAGE_SIZE = "1024x1024"

# --- STREET VIEW SETTINGS ---
STREET_HEADING = "0"    # 0 = North, 90 = East, 180 = South, 270 = West
STREET_PITCH = "0"      # 0 = Eye level
STREET_FOV = "90"       # Field of view

# ==============================================================================
# 3. FETCH THE RGB SOURCE IMAGE
# ==============================================================================
print(f"[*] Mode: {MODE} | Location: {LOCATION}")

if MODE == "AERIAL":
    # High-resolution satellite orthophoto (scale=2 gives crisp 1024x1024)
    url = (
        f"https://maps.googleapis.com/maps/api/staticmap"
        f"?center={LOCATION}"
        f"&zoom={AERIAL_ZOOM}"
        f"&size=512x512"
        f"&scale=2"
        f"&maptype=satellite"
        f"&key={GOOGLE_MAPS_API_KEY}"
    )
elif MODE == "STREET":
    url = (
        f"https://maps.googleapis.com/maps/api/streetview"
        f"?size={IMAGE_SIZE}"
        f"&location={LOCATION}"
        f"&heading={STREET_HEADING}"
        f"&pitch={STREET_PITCH}"
        f"&fov={STREET_FOV}"
        f"&key={GOOGLE_MAPS_API_KEY}"
    )
else:
    raise ValueError("MODE must be either 'STREET' or 'AERIAL'")

print(f"[*] Downloading {MODE.lower()} imagery from Google Maps...")
response = requests.get(url)

if response.status_code != 200:
    raise Exception(f"Failed to fetch image: HTTP {response.status_code} - {response.text}")

rgb_image = Image.open(BytesIO(response.content)).convert("RGB")
rgb_filename = f"output_{MODE.lower()}_rgb.png"
rgb_image.save(rgb_filename)
print(f"[+] Saved RGB reference: '{rgb_filename}'")

# ==============================================================================
# 4. RUN DEPTH ESTIMATION (DEPTH ANYTHING V2)
# ==============================================================================
print("[*] Initializing Depth Anything V2...")
device = 0 if torch.cuda.is_available() else -1

depth_estimator = pipeline(
    task="depth-estimation",
    model="depth-anything/Depth-Anything-V2-Small-hf",
    device=device
)

print(f"[*] Computing depth map for {MODE.lower()} scene...")
depth_result = depth_estimator(rgb_image)
depth_map = depth_result["depth"]

depth_filename = f"output_{MODE.lower()}_depth.png"
depth_map.save(depth_filename)
print(f"[+] Saved depth map: '{depth_filename}' successfully!")