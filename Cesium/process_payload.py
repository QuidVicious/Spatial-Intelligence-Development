import json
import base64
import glob
import os
import urllib.request


def get_location_context(lat, lon):
    """Uses Python standard library to reverse-geocode coordinates into real-world place names globally."""
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


def get_live_weather(lat, lon):
    """Queries Open-Meteo free API to get current live weather for lat/lon without API keys."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'CesiumGroundTruthPipeline/1.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            current = data.get('current_weather', {})
            code = current.get('weathercode', 0)
            temp = current.get('temperature', '')

            # WMO Weather Code Table
            wmo_map = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                95: "Thunderstorm"
            }
            condition = wmo_map.get(code, "Clear sky")
            return f"{condition}, {temp}°C"
    except Exception:
        return "Clear sky, daylight"


# 1. Search Downloads folder or current directory for latest ground_truth export
downloads_path = os.path.expanduser('~/Downloads/ground_truth_*.json')
list_of_files = glob.glob(downloads_path)

if not list_of_files:
    list_of_files = glob.glob('ground_truth_*.json')

if not list_of_files:
    print("Error: No ground_truth_*.json file found in Downloads or local folder!")
    exit(1)

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
time_setting = meta.get('environment', {}).get('time_of_day_setting', 'auto')
user_weather = meta.get('environment', {}).get('weather_setting', '').strip()
user_notes = meta.get('architectural_notes', '').strip()

# 3. Lookup GIS Location Context & Weather
print("Resolving GIS location & live weather context...")
location_name = get_location_context(lat, lon)
if location_name:
    print(f"Location identified: {location_name}")

if user_weather:
    weather_desc = user_weather
    print(f"Weather (Custom UI Override): {weather_desc}\n")
else:
    weather_desc = get_live_weather(lat, lon)
    print(f"Weather (Live GIS Fetch): {weather_desc}\n")

# Determine material prompt text cleanly
if user_notes:
    materials_desc = user_notes
elif location_name:
    materials_desc = f"Authentic regional architecture and historic building materials native to {location_name}"
else:
    materials_desc = "Authentic historic stone masonry, period building materials, and natural foliage"

# Determine solar / time of day text
if time_setting != 'auto':
    time_desc = f"Time of Day: {time_setting.capitalize()} (Sun angle matched in clay model)."
else:
    time_desc = f"Solar time and illumination match ISO timestamp {datetime_iso}."

# 4. Construct 5-Pass Spatial Conditioning Prompt
prompt = (
    f"Photorealistic 8k architectural photograph located at {location_name if location_name else 'GIS location'} "
    f"(lat: {lat:.5f}, lon: {lon:.5f}), camera height {alt:.1f} meters, pitch {pitch:.1f}°, heading {heading:.1f}°. "
    f"{time_desc}\n\n"
    f"ATMOSPHERIC & WEATHER CONDITIONS:\n"
    f"{weather_desc}.\n\n"
    f"ARCHITECTURAL MATERIALS & STYLE:\n"
    f"{materials_desc}.\n\n"
    f"5-PASS CONTROL INSTRUCTIONS:\n"
    f"- Use depth_map.png (grayscale depth) for camera perspective and spatial distance bounds.\n"
    f"- Use lineart_map.png (clean architectural outlines) for exact 90° building silhouettes, window sashes, and rooflines.\n"
    f"- Use normal_map.png (surface orientation vectors) for wall plane directions and specular light reflections.\n"
    f"- Use clay_map.png (shaded clay model) for structural shadow angles and sun illumination.\n"
    f"- Use base_photogrammetry.png for real-world environmental layout and context.\n\n"
    f"FINISHING CARPENTRY & CLEANUP DIRECTIVES:\n"
    f"Replace any low-poly photogrammetry mesh blobs with crisp 8k architectural masonry, sharp window sashes, and realistic high-resolution foliage matching {weather_desc} atmospheric lighting."
)

# Determine safe output directory (same folder as script)
output_dir = os.path.dirname(os.path.abspath(__file__))

# 5. Save Prompt to prompt.txt
prompt_path = os.path.join(output_dir, 'prompt.txt')
with open(prompt_path, 'w') as f:
    f.write(prompt)

# 6. Safe helper to decode base64 PNGs directly to current folder
def save_base64_png(base64_str, output_filename):
    if not base64_str:
        return
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    image_bytes = base64.b64decode(base64_str)
    filepath = os.path.join(output_dir, output_filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

# 7. Save All Image Files
save_base64_png(payload.get('rgb_image'), 'base_photogrammetry.png')
save_base64_png(payload.get('depth_image'), 'depth_map.png')

if 'clay_image' in payload and payload['clay_image']:
    save_base64_png(payload['clay_image'], 'clay_map.png')

if 'normal_image' in payload and payload['normal_image']:
    save_base64_png(payload['normal_image'], 'normal_map.png')

if 'edge_image' in payload and payload['edge_image']:
    save_base64_png(payload['edge_image'], 'lineart_map.png')

print("--- GENERATED SPATIAL PROMPT ---")
print(prompt)
print("--------------------------------\n")

print("Successfully saved files in your project directory:")
print(f" -> {os.path.join(output_dir, 'prompt.txt')}")
print(f" -> {os.path.join(output_dir, 'base_photogrammetry.png')}")
print(f" -> {os.path.join(output_dir, 'depth_map.png')}")
if 'clay_image' in payload:
    print(f" -> {os.path.join(output_dir, 'clay_map.png')}")
if 'normal_image' in payload:
    print(f" -> {os.path.join(output_dir, 'normal_map.png')}")
if 'edge_image' in payload:
    print(f" -> {os.path.join(output_dir, 'lineart_map.png')}")