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

# Domain Key Inputs
domain_keys = meta.get('domain_keys', {})
user_geology = domain_keys.get('geology_lithology', '').strip()
user_era = domain_keys.get('era_architecture_style', '').strip()
user_weathering = domain_keys.get('weathering_patina', '').strip()

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

# Solar / time of day text
if time_setting != 'auto':
    time_desc = f"{time_setting.capitalize()} sun angle matched in clay model."
else:
    time_desc = f"Solar orientation matched to ISO timestamp {datetime_iso}."

# 4. Latent Space Archaeology: Domain Key Synthesis Engine
print("Synthesizing Domain Key Stack (Latent Space Archeology)...")

# Lens 1: Geology & Lithology
if user_geology:
    geology_lens = user_geology
elif location_name:
    geology_lens = f"Native bedrock lithology and regional quarry stone characteristics of {location_name}"
else:
    geology_lens = "Authentic load-bearing stone masonry, igneous rock strata, and regional mineral soil"

# Lens 2: Architecture & Period Craft
if user_era:
    architecture_lens = user_era
elif location_name:
    architecture_lens = f"Period-accurate architectural vernacular, timber joinery, and structural masonry native to {location_name}"
else:
    architecture_lens = "Historic architectural masonry, period window mullion profiles, and hand-tooled facades"

# Lens 3: Material Weathering & Patina
if user_weathering:
    weathering_lens = user_weathering
else:
    weathering_lens = "Natural environmental efflorescence, historic masonry corner wear, subtle rainwater staining, and organic moss patina"

# 5. Construct Structured Multi-Domain Prompt (Target Model: Nano Banana 2 / gemini-3.1-flash-image)
prompt = (
    f"Photorealistic 8k architectural master photograph located at {location_name if location_name else 'GIS location'} "
    f"(lat: {lat:.5f}, lon: {lon:.5f}), camera elevation {alt:.1f}m, pitch {pitch:.1f}°, heading {heading:.1f}°. "
    f"{time_desc}\n\n"
    f"--- DOMAIN KEY LATENT EXPANSION STACK ---\n"
    f"[GEOLOGY & LITHOLOGY LENS]: {geology_lens}.\n"
    f"[ARCHITECTURAL & PERIOD CRAFT LENS]: {architecture_lens}.\n"
    f"[CIVIL ENGINEERING & STRUCTURAL LOGIC LENS]: Authentic structural load paths, heavy foundation anchors, precise roof pitches, and gravity-aligned wall planes.\n"
    f"[ATMOSPHERIC & SOLAR PHYSICS LENS]: {weather_desc}. Direct sun vectors calibrated to clay shadows, microclimate atmospheric scattering, and ambient ray bounce.\n"
    f"[MATERIAL WEATHERING & PATINA LENS]: {weathering_lens}.\n\n"
    f"--- 5-PASS SPATIAL CONTROL DIRECTIVES (Nano Banana 2) ---\n"
    f"- depth_map.png (grayscale linear depth): Controls camera depth bounds, volumetric distance, and spatial occlusion.\n"
    f"- lineart_map.png (architectural outlines): Drives sharp 90° wall corners, window sash frames, and rooflines.\n"
    f"- normal_map.png (surface orientation vectors): Enforces physical wall directions, specular reflections, and surface normal alignment.\n"
    f"- clay_map.png (shaded clay model): Dictates exact solar shadow angles, key light direction, and ambient occlusion balance.\n"
    f"- base_photogrammetry.png: Provides real-world contextual layout and ground truth layout.\n\n"
    f"FINISHING CARPENTRY & MESH REFINEMENT DIRECTIVE:\n"
    f"Eliminate photogrammetry artifacts and low-poly mesh distortions. Render crisp 8k architectural stonework, sharp glass window panes, and lush photorealistic vegetation illuminated by {weather_desc} lighting."
)

# Determine safe output directory
output_dir = os.path.dirname(os.path.abspath(__file__))

# 6. Save Prompt to prompt.txt
prompt_path = os.path.join(output_dir, 'prompt.txt')
with open(prompt_path, 'w') as f:
    f.write(prompt)

# 7. Helper to decode base64 PNGs directly
def save_base64_png(base64_str, output_filename):
    if not base64_str:
        return
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
    image_bytes = base64.b64decode(base64_str)
    filepath = os.path.join(output_dir, output_filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)

# 8. Save All Image Files
save_base64_png(payload.get('rgb_image'), 'base_photogrammetry.png')
save_base64_png(payload.get('depth_image'), 'depth_map.png')

if 'clay_image' in payload and payload['clay_image']:
    save_base64_png(payload['clay_image'], 'clay_map.png')

if 'normal_image' in payload and payload['normal_image']:
    save_base64_png(payload['normal_image'], 'normal_map.png')

if 'edge_image' in payload and payload['edge_image']:
    save_base64_png(payload['edge_image'], 'lineart_map.png')

print("--- GENERATED MULTI-DOMAIN SPATIAL PROMPT ---")
print(prompt)
print("---------------------------------------------\n")

print("Successfully saved files in project directory:")
print(f" -> {os.path.join(output_dir, 'prompt.txt')}")
print(f" -> {os.path.join(output_dir, 'base_photogrammetry.png')}")
print(f" -> {os.path.join(output_dir, 'depth_map.png')}")
if 'clay_image' in payload:
    print(f" -> {os.path.join(output_dir, 'clay_map.png')}")
if 'normal_image' in payload:
    print(f" -> {os.path.join(output_dir, 'normal_map.png')}")
if 'edge_image' in payload:
    print(f" -> {os.path.join(output_dir, 'lineart_map.png')}")