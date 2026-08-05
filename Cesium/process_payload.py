import json
import base64
import glob
import os
import urllib.request

# -------------------------------------------------------------------
# ARCHITECTURAL MATERIAL SETTINGS
# Leave blank for 100% auto-detection, or set to force custom materials.
# -------------------------------------------------------------------
MATERIAL_OVERRIDE = "Historic Georgian architecture, authentic 200-year-old Craigleith sandstone masonry, slate roofing, period timber sash windows"


def get_location_context(lat, lon):
    """Uses Python standard library to reverse-geocode coordinates into real-world place names."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CesiumGroundTruthPipeline/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            address = data.get('address', {})
            parts = [
                address.get('suburb') or address.get('neighbourhood') or address.get('quarter'),
                address.get('city') or address.get('town') or address.get('county'),
                address.get('country')
            ]
            valid_parts = [p for p in parts if p]
            if valid_parts:
                return ", ".join(valid_parts)
            return data.get('display_name', '')
    except Exception:
        return ""

# 1. Search Downloads folder for the latest ground_truth export
downloads_path = os.path.expanduser('~/Downloads/ground_truth_*.json')
list_of_files = glob.glob(downloads_path)

if not list_of_files:
    list_of_files = glob.glob('ground_truth_*.json')

if not list_of_files:
    print("Error: No ground_truth_*.json file found in Downloads or local folder!")
    exit()

latest_file = max(list_of_files, key=os.path.getctime)
print(f"Reading latest export: {latest_file}\n")

with open(latest_file, 'r') as f:
    payload = json.load(f)

# 2. Extract GIS Metadata
meta = payload['metadata']
lat = meta['geographic_location']['latitude']
lon = meta['geographic_location']['longitude']
alt = meta['geographic_location']['altitude_meters']
heading = meta['camera_transform']['heading_deg']
pitch = meta['camera_transform']['pitch_deg']
datetime_iso = meta.get('environment', {}).get('datetime_iso', 'N/A')

# 3. Lookup GIS Location Name
print("Resolving GIS location context...")
location_name = get_location_context(lat, lon)
if location_name:
    print(f"Location identified: {location_name}\n")

# Determine material prompt text
if MATERIAL_OVERRIDE.strip():
    materials_desc = MATERIAL_OVERRIDE
elif location_name:
    materials_desc = f"Authentic regional architecture and historic building materials native to {location_name}"
else:
    materials_desc = "Authentic historic stone masonry, period building materials, and natural foliage"

# 4. Construct 4-Pass Spatial Conditioning Prompt
prompt = (
    f"Photorealistic 8k architectural photograph located at {location_name if location_name else 'GIS location'} "
    f"(lat: {lat:.5f}, lon: {lon:.5f}), camera height {alt:.1f} meters, pitch {pitch:.1f}°, heading {heading:.1f}°. "
    f"Solar time and illumination match ISO timestamp {datetime_iso}.\n\n"
    f"ARCHITECTURAL MATERIALS & STYLE:\n"
    f"{materials_desc}.\n\n"
    f"4-PASS CONTROL INSTRUCTIONS:\n"
    f"- Use depth_map.png (grayscale depth) for camera perspective and spatial distance bounds.\n"
    f"- Use normal_map.png (surface orientation vectors) for crisp 90° building edges, window sashes, and light reflection directions.\n"
    f"- Use clay_map.png (shaded clay model) for structural shadow angles and sun illumination.\n"
    f"- Use base_photogrammetry.png for real-world environmental layout and context.\n\n"
    f"CLEANUP DIRECTIVES:\n"
    f"Replace any low-poly photogrammetry mesh blobs with crisp 8k architectural masonry, sharp window frames, and realistic high-resolution foliage."
)

# 5. Save Prompt to prompt.txt
with open('prompt.txt', 'w') as f:
    f.write(prompt)

# 6. Helper to decode base64 PNGs
def save_base64_png(base64_str, output_filename):
    if not base64_str:
        return
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    image_bytes = base64.b64decode(base64_str)
    with open(output_filename, 'wb') as f:
        f.write(image_bytes)

# 7. Save Image Files
save_base64_png(payload.get('rgb_image'), 'base_photogrammetry.png')
save_base64_png(payload.get('depth_image'), 'depth_map.png')

if 'clay_image' in payload and payload['clay_image']:
    save_base64_png(payload['clay_image'], 'clay_map.png')

if 'normal_image' in payload and payload['normal_image']:
    save_base64_png(payload['normal_image'], 'normal_map.png')

print("--- GENERATED SPATIAL PROMPT ---")
print(prompt)
print("--------------------------------\n")

print("Successfully saved files in your folder:")
print(" -> prompt.txt")
print(" -> base_photogrammetry.png")
print(" -> depth_map.png")
if 'clay_image' in payload:
    print(" -> clay_map.png")
if 'normal_image' in payload:
    print(" -> normal_map.png")