import json
import base64
import glob
import os
import urllib.request
import urllib.parse
import time
import random


def load_native_env(env_filename='.env'):
    """Native Python parser to load variables from local or external directory paths."""
    possible_paths = [
        r'C:\DEV\Squid\SquidBlack\.env',          # Target external directory
        os.path.expanduser(f'~/{env_filename}'),  # C:\Users\...\.env
        r'C:\DEV\.env',                           # DEV root folder
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', env_filename)),     # 1 folder up
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', env_filename)), # 2 folders up
        os.path.join(os.path.dirname(os.path.abspath(__file__)), env_filename),  # Script directory
        os.path.join(os.getcwd(), env_filename)  # Current working directory
    ]
    for env_path in possible_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            key, val = line.split('=', 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            os.environ[key] = val
                print(f"Loaded environment variables from: {env_path}")
                return
            except Exception as e:
                print(f"Warning: Failed to parse .env file at {env_path}: {e}")
    print("Warning: No .env file found in any configured search directory.")


def get_location_context(lat, lon):
    """Uses Python standard library to reverse-geocode coordinates for text context."""
    override = os.environ.get("LOCATION_OVERRIDE", "").strip()
    if override:
        print(f"Using LOCATION_OVERRIDE from .env: {override}")
        return override

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CesiumGroundTruthPipeline/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            address = data.get('address', {})
            
            suburb = address.get('suburb') or address.get('neighbourhood') or address.get('quarter') or ''
            city = address.get('city') or address.get('town') or address.get('county') or ''
            country = address.get('country') or ''

            parts = [p for p in [suburb, city, country] if p]
            if parts:
                return ", ".join(parts)
            return data.get('display_name', '')
    except Exception:
        return None


def get_live_weather(lat, lon):
    """Queries Open-Meteo free API to get current live weather for lat/lon without API keys."""
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        req = urllib.request.Request(url, headers={'User-Agent': 'CesiumGroundTruthPipeline/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            current = data.get('current_weather', {})
            code = current.get('weathercode', 0)
            temp = current.get('temperature', '')

            wmo_map = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Foggy", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
                95: "Thunderstorm"
            }
            condition = wmo_map.get(code, "Overcast daylight")
            return f"{condition}, {temp}°C"
    except Exception:
        return "Overcast diffuse daylight, 18°C"


def clean_b64(b64):
    """Utility to remove data header prefix from base64 string if present."""
    if not b64:
        return ""
    return b64.split(",")[1] if "," in b64 else b64


def resolve_mother_stack_native(location_name, lat, lon, rgb_b64, api_key, domain_keys=None, model_name="gemini-3.6-flash"):
    """Stage 1: Multimodal Material & Visual Surface Inspector.
    Analyzes Image 1 specifically to extract factual surface materials and color tones while forbidding hallucinated architectural nouns."""
    domain_keys = domain_keys or {}
    user_geo = domain_keys.get("geology_lithology", "").strip()
    user_arch = domain_keys.get("era_architecture_style", "").strip()
    user_patina = domain_keys.get("weathering_patina", "").strip()

    loc_label = location_name if location_name else f"lat: {lat:.5f}, lon: {lon:.5f}"

    fallback_stack = {
        "geology": user_geo or f"Observe and describe the specific stone colors and masonry types in Image 1.",
        "architecture": user_arch or f"Observe the structural layout of buildings in Image 1 without adding decorative features.",
        "patina": user_patina or f"Observe surface weathering and patina visible in Image 1."
    }

    if user_geo and user_arch and user_patina:
        print("Using user-defined domain keys from metadata overrides.")
        return fallback_stack

    if not api_key:
        print("Warning: GEMINI_API_KEY missing for Stage 1. Using fallback domain keys.")
        return fallback_stack

    print(f"Resolving Material & Surface Inspection via Gemini API ({model_name})...")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        prompt_text = (
            f"You are a strict material and visual surface inspector analyzing a raw 3D photogrammetry image (Image 1) "
            f"located near {loc_label}.\n\n"
            f"STRICT NON-HALLUCINATION RULES:\n"
            f"- Describe ONLY the visual materials, colors, and structural layouts directly visible in Image 1.\n"
            f"- Do NOT name specific landmark buildings, famous streets, or historical monuments.\n"
            f"- Do NOT use ornamental architectural nouns (such as 'columns', 'pilasters', 'pediments', 'statues', 'balconies', 'domes', 'porticos') "
            f"UNLESS they are plainly and unmistakably visible in Image 1.\n"
            f"- Note color variations between different adjacent buildings (e.g., dark grey stone on building A, light cream render on building B).\n\n"
            f"Return ONLY a JSON object with 3 keys:\n"
            f"- 'geology': List the exact surface materials (e.g. ashlar stone, brick, concrete, glass, slate) and color tones observed per visible structure.\n"
            f"- 'architecture': Describe the basic structural shapes, rooflines, and window arrangements strictly as framed in Image 1.\n"
            f"- 'patina': Describe surface weathering, water staining, or soot accumulation visible on these specific surfaces."
        )

        parts_list = []
        if rgb_b64:
            parts_list.append({"inlineData": {"mimeType": "image/png", "data": clean_b64(rgb_b64)}})
        parts_list.append({"text": prompt_text})

        request_body = {
            "contents": [{"parts": parts_list}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            text_result = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            if text_result.startswith("```"):
                text_result = text_result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed_stack = json.loads(text_result)
            return {
                "geology": user_geo or parsed_stack.get("geology", fallback_stack["geology"]),
                "architecture": user_arch or parsed_stack.get("architecture", fallback_stack["architecture"]),
                "patina": user_patina or parsed_stack.get("patina", fallback_stack["patina"])
            }
            
    except Exception as e:
        print(f"Warning: Surface Inspection API call failed ({e}). Using native fallbacks.\n")
        return fallback_stack


def call_gemini_image_api(prompt, images_b64_list, api_key, temp, top_p, thinking_level="HIGH", model_name="gemini-3.1-flash-image", max_retries=4):
    """Generic REST dispatcher for Gemini Image Generation with imageConfig (4K, 16:9),
    thinkingConfig support, and exponential backoff retry handling for transient HTTP errors."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    parts_list = []
    for b64 in images_b64_list:
        if b64:
            parts_list.append({"inlineData": {"mimeType": "image/png", "data": clean_b64(b64)}})
    
    parts_list.append({"text": prompt})

    request_body = {
        "contents": [{"parts": parts_list}],
        "generationConfig": {
            "temperature": float(temp),
            "topP": float(top_p),
            "responseModalities": ["IMAGE"],  
            "imageConfig": {
                "aspectRatio": "16:9",
                "imageSize": "4K"
            },
            "thinkingConfig": {
                "thinkingLevel": str(thinking_level).upper()
            }
        }
    }

    retries = 0
    backoff = 3.0
    while True:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(request_body).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                
                valid_images = []
                for candidate in res_data.get('candidates', []):
                    for part in candidate.get('content', {}).get('parts', []):
                        if part.get('thought') is True:
                            continue
                            
                        img_data = part.get('inlineData') or part.get('inline_data')
                        if img_data and img_data.get('data'):
                            valid_images.append(img_data['data'])
                        elif 'text' in part:
                            print(f"\n[MODEL TEXT RESPONSE OUTPUT]: {part['text'][:300]}...")

                if valid_images:
                    return valid_images[-1]

                raise Exception(f"API response from {model_name} contained no valid final image payload.")
                
        except urllib.error.HTTPError as e:
            if e.code in [429, 500, 502, 503, 504] and retries < max_retries:
                sleep_time = backoff + random.uniform(0.1, 1.0)
                print(f"API returned transient error {e.code} ({e.reason}). Retrying in {sleep_time:.2f} seconds (Attempt {retries + 1}/{max_retries})...")
                time.sleep(sleep_time)
                backoff *= 2.0
                retries += 1
            else:
                raise e


def save_base64_png(base64_str, output_filename, output_dir):
    """Helper to decode base64 PNGs directly to disk."""
    if not base64_str:
        return False
    base64_str = clean_b64(base64_str)
    image_bytes = base64.b64decode(base64_str)
    filepath = os.path.join(output_dir, output_filename)
    with open(filepath, 'wb') as f:
        f.write(image_bytes)
    return True


# --- MAIN AUTOMATED EXECUTION PIPELINE ---
if __name__ == "__main__":
    load_native_env()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GEMINI_KEY", "").strip()

    downloads_files = glob.glob(os.path.expanduser('~/Downloads/ground_truth_*.json'))
    local_files = glob.glob('ground_truth_*.json')
    list_of_files = list(set(downloads_files + local_files))

    if not list_of_files:
        print("Error: No ground_truth_*.json file found!")
        exit(1)

    latest_file = max(list_of_files, key=os.path.getmtime)
    print(f"Reading latest export: {os.path.basename(latest_file)}\n")

    with open(latest_file, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    meta = payload['metadata']
    lat = meta['geographic_location']['latitude']
    lon = meta['geographic_location']['longitude']
    alt = meta['geographic_location']['altitude_meters']
    heading = meta['camera_transform']['heading_deg']
    pitch = meta['camera_transform']['pitch_deg']
    datetime_iso = meta.get('environment', {}).get('datetime_iso', 'N/A')
    user_weather = meta.get('environment', {}).get('weather_setting', '').strip()
    domain_keys = meta.get('domain_keys', {})

    pipeline_params = payload.get('pipeline_parameters', {})
    
    pass1_temp = pipeline_params.get('pass1_temperature', float(os.environ.get("PASS1_TEMP", 0.35)))
    pass1_top_p = pipeline_params.get('pass1_top_p', float(os.environ.get("PASS1_TOP_P", 0.70)))
    pass2_temp = pipeline_params.get('pass2_temperature', float(os.environ.get("PASS2_TEMP", 0.15)))
    pass2_top_p = pipeline_params.get('pass2_top_p', float(os.environ.get("PASS2_TOP_P", 0.25)))
    thinking_level = pipeline_params.get('thinking_level', os.environ.get("THINKING_LEVEL", "HIGH"))

    output_dir = os.path.dirname(os.path.abspath(__file__))

    rgb_b64 = payload.get('rgb_image')
    depth_b64 = payload.get('depth_image')

    save_base64_png(rgb_b64, 'base_photogrammetry.png', output_dir)
    save_base64_png(depth_b64, 'depth_map.png', output_dir)

    location_name = get_location_context(lat, lon)
    weather_desc = user_weather if user_weather else get_live_weather(lat, lon)

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is missing from .env file!")
        exit(1)

    # Stage 1: Multimodal call to gemini-3.6-flash
    ai_stack = resolve_mother_stack_native(
        location_name, lat, lon, rgb_b64, GEMINI_API_KEY, 
        domain_keys=domain_keys, model_name="gemini-3.6-flash"
    )

    # Note: Landmark names are omitted from the image prompt to prevent location jumping.
    coord_label = f"lat: {lat:.5f}, lon: {lon:.5f}"

    # --- PASS 1: GEOMETRIC & STRUCTURAL LOCK RECONSTRUCTION ---
    print("\n==================================================")
    print(" EXECUTING PASS 1: GEOMETRIC & STRUCTURAL LOCK (4K 16:9)")
    print(f" -> Model: gemini-3.1-flash-image | Temp: {pass1_temp} | Top P: {pass1_top_p} | Thinking: {thinking_level}")
    print("==================================================")

    pass1_prompt = (
        f"Image 1 is a raw 3D photogrammetry render showing base colors, textures, and building layouts.\n"
        f"Image 2 is depth_map.png showing exact 3D distance and structural geometry.\n\n"
        f"TASK (STRUCTURAL & GEOMETRIC RECONSTRUCTION):\n"
        f"Synthesize a clean, structurally sound architectural photograph at 4K resolution (16:9 aspect ratio) "
        f"from the exact camera perspective, horizon line, and elevation ratio set by Image 2 (coordinates: {coord_label}).\n\n"
        f"[ANTI-HALLUCINATION & ZERO-ADDITION DIRECTIVE]\n"
        f"- You are cleaning, un-melting, and sharpening EXISTING geometry visible in Image 1.\n"
        f"- Do NOT add new architectural features, statues, columns, balconies, pediments, dormers, domes, or decorative trim that do not exist in Image 1.\n"
        f"- Do NOT render or jump to nearby famous landmarks or monuments that are not framed in Image 1.\n"
        f"- If a facade in Image 1 is plain, flat, or modern, it MUST remain plain, flat, or modern.\n\n"
        f"[GEOMETRIC OVERPAINT & STRAIGHT LINES]\n"
        f"- Fully overwrite low-resolution mesh blur, wobbly edges, and melted artifacts from Image 1.\n"
        f"- Force all existing architectural edges, window frames, lintels, and rooflines to be perfectly straight and parallel.\n\n"
        f"[PER-BUILDING MATERIAL BOUNDARIES]\n"
        f"- Respect the distinct building boundaries and material variations visible in Image 1.\n"
        f"- Apply surface materials on a per-building basis using the observed colors in Image 1 and material guide:\n"
        f"  * Structural Guide: {ai_stack['architecture']}\n"
        f"  * Material & Surface Guide: {ai_stack['geology']}\n\n"
        f"[LIGHTING & ATMOSPHERE]\n"
        f"- Atmosphere & Sky: {weather_desc}.\n\n"
        f"Render as a clean, sharp, structurally truthful architectural photograph."
    )

    pass1_b64_output = call_gemini_image_api(
        pass1_prompt, 
        [rgb_b64, depth_b64], 
        GEMINI_API_KEY, 
        temp=pass1_temp, 
        top_p=pass1_top_p,
        thinking_level=thinking_level,
        model_name="gemini-3.1-flash-image"
    )
    
    pass1_filepath = os.path.join(output_dir, 'pass1_structural_reconstruction.png')
    save_base64_png(pass1_b64_output, 'pass1_structural_reconstruction.png', output_dir)
    print(f" -> Pass 1 Complete: Saved to {pass1_filepath}")

    # --- PASS 2: MATERIAL, TEXTURE & PATINA REFINEMENT ---
    print("\n==================================================")
    print(" EXECUTING PASS 2: MATERIAL, TEXTURE & PATINA REFINEMENT (4K 16:9)")
    print(f" -> Model: gemini-3.1-flash-image | Temp: {pass2_temp} | Top P: {pass2_top_p} | Thinking: {thinking_level}")
    print("==================================================")

    pass2_prompt = (
        f"Image 1 is pass1_structural_reconstruction.png providing clean 4K geometry and straight architectural lines.\n"
        f"Image 2 is depth_map.png providing exact spatial depth anchors.\n\n"
        f"TASK (HIGH-FREQUENCY TEXTURE & PATINA POLISH):\n"
        f"Enhance Image 1 into a masterwork architectural photograph at 4K resolution (16:9 aspect ratio).\n\n"
        f"[STRICT GEOMETRIC LOCK & ZERO ADDITION]\n"
        f"- Maintain 100% geometric alignment with Image 1. Do NOT shift window positions, rooflines, camera perspective, or building boundaries.\n"
        f"- Do NOT add any new architectural elements, ornaments, or features not present in Image 1.\n\n"
        f"[TACTILE MATERIAL & PATINA DETAIL]\n"
        f"- Inject ultra-high-frequency tactile surface textures into masonry, stone grain, mortar joints, slate roofs, and glass reflections.\n"
        f"- Masonry & Surface Texture: {ai_stack['geology']}.\n"
        f"- Weathering & Patina: {ai_stack['patina']}.\n"
        f"- Lighting & Shadow Dynamics: Natural, photo-real shadows and realistic ambient occlusion calibrated to {weather_desc}.\n\n"
        f"Render as an ultra-sharp, professional architectural photograph shot on a 35mm prime lens."
    )

    pass2_b64_output = call_gemini_image_api(
        pass2_prompt, 
        [pass1_b64_output, depth_b64], 
        GEMINI_API_KEY, 
        temp=pass2_temp, 
        top_p=pass2_top_p,
        thinking_level=thinking_level,
        model_name="gemini-3.1-flash-image"
    )

    final_filepath = os.path.join(output_dir, 'final_photoreal_render.png')
    save_base64_png(pass2_b64_output, 'final_photoreal_render.png', output_dir)

    print("\n==================================================")
    print(" PIPELINE COMPLETE!")
    print(f" -> Pass 1 Output: {pass1_filepath}")
    print(f" -> Pass 2 Final 4K Render: {final_filepath}")
    print("==================================================\n")