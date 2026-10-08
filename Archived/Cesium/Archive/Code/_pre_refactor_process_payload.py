import json
import base64
import glob
import os
import urllib.request
import urllib.parse


def load_native_env(env_filename='.env'):
    """Native Python parser to load variables from a local .env file into os.environ without packages."""
    possible_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), env_filename),
        os.path.join(os.getcwd(), env_filename)
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
                break
            except Exception as e:
                print(f"Warning: Failed to parse .env file: {e}")


def get_location_context(lat, lon):
    """Uses Python standard library to reverse-geocode coordinates.
    Sanitizes common misattributions (like 'Haymarket' in EH3/Central Edinburgh)."""
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

            if suburb.lower() in ['haymarket', 'royal mile']:
                suburb = 'Stockbridge / Dean Village / New Town'

            parts = [p for p in [suburb, city, country] if p]
            if parts:
                return ", ".join(parts)
            return data.get('display_name', '')
    except Exception:
        return "Edinburgh, Scotland, United Kingdom"


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


def resolve_mother_stack_native(location_name, lat, lon, api_key, model_name="gemini-3.6-flash"):
    """Stage 1: Calls Gemini 3.6 Flash (Text LLM) to produce DESCRIPTIVE VISUAL prompts."""
    if not api_key:
        return {
            "geology": f"Constructed from local ashlar-cut buff sandstone with natural granular surface texture and tight mortar lines typical of {location_name}.",
            "architecture": f"Period-accurate classical Georgian and early Victorian residential architecture featuring proportioned sash windows, slate roofs, and stone cornices native to {location_name}.",
            "patina": "Subtle historic coal soot weathering in sheltered stone recesses, mild rainwater run-off staining on sills, and faint moss accumulation near base masonry."
        }

    print(f"Resolving Mother Stack via Gemini REST API ({model_name}) for: {location_name}...")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        prompt_text = (
            f"You are an expert architectural historian and visual director. "
            f"Analyze the location '{location_name}' at lat: {lat}, lon: {lon}.\n"
            f"Write descriptive visual guidance sentences (NOT short database bullet points or landmark names) for an image generator. "
            f"Return ONLY a JSON object with 3 keys:\n"
            f"- 'geology': Describe the specific stone texture, color, block sizing, and masonry mortar style.\n"
            f"- 'architecture': Describe the dominant facade style, window mullions/sashes, roof slates, and cornices for this neighborhood.\n"
            f"- 'patina': Describe realistic local environmental weathering, soot buildup, rain streaks, and masonry edge wear."
        )

        request_body = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(request_body).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            text_result = res_data['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text_result)
            
    except Exception as e:
        print(f"Warning: Mother Stack API resolution failed ({e}). Using native fallbacks.\n")
        return {
            "geology": f"Constructed from local ashlar-cut buff sandstone with natural granular surface texture and tight mortar lines typical of {location_name}.",
            "architecture": f"Period-accurate classical Georgian and early Victorian residential architecture featuring proportioned sash windows, slate roofs, and stone cornices native to {location_name}.",
            "patina": "Subtle historic coal soot weathering in sheltered stone recesses, mild rainwater run-off staining on sills, and faint moss accumulation near base masonry."
        }


def call_gemini_image_api(prompt, images_b64_list, api_key, temp, top_p, thinking_level="HIGH", model_name="gemini-3.1-flash-image"):
    """Generic REST dispatcher for Gemini Image Generation (gemini-3.1-flash-image / Nano Banana 2) with thinkingConfig support."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    def clean(b64):
        return b64.split(",")[1] if "," in b64 else b64

    parts_list = [{"text": prompt}]
    for b64 in images_b64_list:
        if b64:
            parts_list.append({"inlineData": {"mimeType": "image/png", "data": clean(b64)}})

    # Injects thinkingConfig into generationConfig REST payload
    request_body = {
        "contents": [{"parts": parts_list}],
        "generationConfig": {
            "temperature": float(temp),
            "topP": float(top_p),
            "thinkingConfig": {
                "thinkingLevel": str(thinking_level).upper()
            }
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )

    with urllib.request.urlopen(req, timeout=90) as response:
        res_data = json.loads(response.read().decode('utf-8'))
        
        # Parse candidates for image inlineData
        for candidate in res_data.get('candidates', []):
            for part in candidate.get('content', {}).get('parts', []):
                img_data = part.get('inlineData') or part.get('inline_data')
                if img_data:
                    return img_data['data']
                if 'text' in part:
                    print(f"\n[MODEL TEXT RESPONSE OUTPUT]: {part['text'][:300]}...")

        raise Exception(f"API response from {model_name} contained no image payload.")


def save_base64_png(base64_str, output_filename, output_dir):
    """Helper to decode base64 PNGs directly to disk."""
    if not base64_str:
        return False
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]
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

    pipeline_params = payload.get('pipeline_parameters', {})
    pass1_temp = pipeline_params.get('pass1_temperature', float(os.environ.get("PASS1_TEMP", 0.20)))
    pass1_top_p = pipeline_params.get('pass1_top_p', float(os.environ.get("PASS1_TOP_P", 0.25)))
    pass2_temp = pipeline_params.get('pass2_temperature', float(os.environ.get("PASS2_TEMP", 0.20)))
    pass2_top_p = pipeline_params.get('pass2_top_p', float(os.environ.get("PASS2_TOP_P", 0.40)))
    thinking_level = pipeline_params.get('thinking_level', os.environ.get("THINKING_LEVEL", "HIGH"))

    output_dir = os.path.dirname(os.path.abspath(__file__))

    rgb_b64 = payload.get('rgb_image')
    depth_b64 = payload.get('depth_image')

    save_base64_png(rgb_b64, 'base_photogrammetry.png', output_dir)
    save_base64_png(depth_b64, 'depth_map.png', output_dir)

    location_name = get_location_context(lat, lon)
    weather_desc = user_weather if user_weather else get_live_weather(lat, lon)

    # Stage 1: Calls gemini-3.6-flash for descriptive text generation
    ai_stack = resolve_mother_stack_native(location_name, lat, lon, GEMINI_API_KEY, model_name="gemini-3.6-flash")

    # --- PASS 1: SPATIAL LOCK RENDER ---
    print("\n==================================================")
    print(" EXECUTING PASS 1: SPATIAL BOUNDARY LOCK RENDER")
    print(f" -> Model: gemini-3.1-flash-image | Temp: {pass1_temp} | Top P: {pass1_top_p} | Thinking: {thinking_level}")
    print("==================================================")

    pass1_prompt = (
        f"Image 1 is a raw 3D photogrammetry render showing base colors and building layouts.\n"
        f"Image 2 is depth_map.png showing exact 3D distance and structural geometry.\n\n"
        f"TASK:\n"
        f"Synthesize a clean architectural photograph from the exact camera perspective, horizon line, "
        f"and elevation ratio set by Image 2 at {location_name} (lat: {lat:.5f}, lon: {lon:.5f}), "
        f"camera elevation {alt:.1f}m, pitch {pitch:.1f}°, heading {heading:.1f}°.\n\n"
        f"[STRICT SPATIAL BOUNDARY LOCK]\n"
        f"- Treat Image 2 (depth_map.png) as an absolute geometric anchor.\n"
        f"- Render ONLY the physical building structures and topography present in Image 2.\n"
        f"- Do NOT add unrequested towers, monuments, or foreign structures. Treat empty zones as open sky or valley terrain.\n\n"
        f"[LOCATION & DOMAIN STACK]\n"
        f"- Lithology & Stone: {ai_stack['geology']}\n"
        f"- Architecture & Style: {ai_stack['architecture']}\n"
        f"- Weathering & Patina: {ai_stack['patina']}\n"
        f"- Atmosphere: {weather_desc}.\n\n"
        f"Render as an architectural photograph. Clean structural lines and authentic material textures."
    )

    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is missing from .env file!")
        exit(1)

    # Stage 2 Pass 1: Calls gemini-3.1-flash-image with thinkingLevel: HIGH
    pass1_b64_output = call_gemini_image_api(
        pass1_prompt, 
        [rgb_b64, depth_b64], 
        GEMINI_API_KEY, 
        temp=pass1_temp, 
        top_p=pass1_top_p,
        thinking_level=thinking_level,
        model_name="gemini-3.1-flash-image"
    )
    
    save_base64_png(pass1_b64_output, 'pass1_spatial_anchor.png', output_dir)
    print("SUCCESS: Pass 1 spatial anchor generated and saved to pass1_spatial_anchor.png")

    # --- PASS 2: SEMANTIC VISUAL INFERENCE ---
    print("\n==================================================")
    print(" EXECUTING PASS 2: SEMANTIC VISUAL INFERENCE")
    print(f" -> Model: gemini-3.1-flash-image | Temp: {pass2_temp} | Top P: {pass2_top_p} | Thinking: {thinking_level}")
    print("==================================================")

    pass2_prompt = (
        f"Image 1 is a low-res 3D mesh render of {location_name}. Use Image 1 as a strict spatial template and base layer.\n\n"
        f"TASK:\n"
        f"Perform a high-definition 8K architectural render pass on Image 1, strictly preserving the original spatial arrangement while adding precise, realistic materials.\n\n"
        f"MATERIAL & TEXTURE DEFINITIONS:\n"
        f"- Facades: Reconstruct building facades using {ai_stack['geology']} with clean mortar joints and stone cornices.\n"
        f"- Roofs: Render precise dark slate roof tiles and stone chimneys.\n"
        f"- Windows & Accents: Sharp timber sash window frames with realistic glass, deep sills, and metal drainpipes casting thin shadows.\n"
        f"- Streets & Vegetation: Paved asphalt streets, stone curbs, and individual leaf definitions for the vegetation.\n\n"
        f"PRESERVATION LOCK:\n"
        f"Strictly preserve the exact spatial positions of all structures, roads, vegetation, and lighting vectors from Image 1."
    )

    # Stage 2 Pass 2: Calls gemini-3.1-flash-image with thinkingLevel: HIGH
    final_b64_output = call_gemini_image_api(
        pass2_prompt, 
        [pass1_b64_output], 
        GEMINI_API_KEY, 
        temp=pass2_temp, 
        top_p=pass2_top_p,
        thinking_level=thinking_level,
        model_name="gemini-3.1-flash-image"
    )

    save_base64_png(final_b64_output, 'final_photoreal_render.png', output_dir)
    print("\n==================================================")
    print(" PIPELINE COMPLETE! 8K RENDER SAVED TO:")
    print(f" -> {os.path.join(output_dir, 'final_photoreal_render.png')}")
    print("==================================================\n")