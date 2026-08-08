import os
import sys
import json
import base64
import urllib.request
import urllib.parse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY")
OUTPUT_DIR = "./output_pass_payloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_b64_image(b64_string: str, output_filepath: str):
    """Saves a base64 image string directly to a PNG file (No PIL required)."""
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]
    image_bytes = base64.b64decode(b64_string)
    with open(output_filepath, "wb") as f:
        f.write(image_bytes)


def extract_raw_b64(b64_string: str) -> str:
    """Strips data URL header if present."""
    if "," in b64_string:
        return b64_string.split(",")[1]
    return b64_string


def save_pass_images(payload: dict, timestamp: int) -> dict:
    """Saves all 5 exported control passes to local disk."""
    passes = {
        "base_photogrammetry": payload["rgb_image"],
        "depth_map": payload["depth_image"],
        "clay_map": payload["clay_image"],
        "normal_map": payload["normal_image"],
        "lineart_map": payload["edge_image"],
    }
    
    saved_paths = {}
    for pass_name, b64_data in passes.items():
        file_path = os.path.join(OUTPUT_DIR, f"{timestamp}_{pass_name}.png")
        save_b64_image(b64_data, file_path)
        saved_paths[pass_name] = file_path

    return saved_paths


def construct_spatial_prompt(metadata: dict) -> str:
    """Builds a deterministic, physically accurate prompt from GIS telemetry."""
    geo = metadata.get("geographic_location", {})
    cam = metadata.get("camera_transform", {})
    env = metadata.get("environment", {})
    arch_notes = metadata.get("architectural_notes", "Modern urban architecture")
    weather = env.get("weather_setting") or "Clear skies, direct sun illumination"
    time_setting = env.get("time_of_day_setting", "auto")
    iso_time = env.get("datetime_iso", "")

    return (
        f"Photorealistic 8k ultra-detailed architectural render.\n\n"
        f"Spatial Telemetry Context:\n"
        f"- Location: Lat {geo.get('latitude', 0):.5f}, Long {geo.get('longitude', 0):.5f}, Alt {geo.get('altitude_meters', 0):.1f}m\n"
        f"- Camera Orientation: Heading {cam.get('heading_deg', 0):.1f}°, Pitch {cam.get('pitch_deg', 0):.1f}°, Roll {cam.get('roll_deg', 0):.1f}°\n"
        f"- Lighting / Solar Time: ISO {iso_time} (Preset Mode: {time_setting})\n"
        f"- Weather/Atmosphere: {weather}\n"
        f"- Architectural Style & Materials: {arch_notes}\n\n"
        f"Control Conditioning Rules:\n"
        f"1. Strictly align all architectural footprints, structural facades, and volumetric boundaries to the provided LineArt Edge Map and Normal Map.\n"
        f"2. Retain precise depth hierarchy from the Depth Map.\n"
        f"3. Use the Clay Model shadow profiles to establish exact directional light and self-shadowing.\n"
        f"4. Replace low-res 3D tile artifacts from the Photogrammetry baseline with high-fidelity, photorealistic building materials, glass reflections, structural steel, and crisp urban details."
    )


def process_ground_truth_payload(json_file_path: str):
    """Main pipeline execution function using standard library REST requests."""
    print(f"Loading Ground-Truth Payload: {json_file_path}")
    with open(json_file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    metadata = payload["metadata"]
    timestamp = int(os.path.basename(json_file_path).split("_")[-1].replace(".json", "")) if "_" in json_file_path else 1000

    # 1. Unpack & Save 5-Pass Controls to disk
    print("Unpacking 5 spatial control passes...")
    save_pass_images(payload, timestamp)

    # 2. Build Structured Prompt
    prompt_text = construct_spatial_prompt(metadata)
    print("\nGenerated Spatial Telemetry Prompt:\n" + "-" * 40 + f"\n{prompt_text}\n" + "-" * 40)

    # 3. Construct Gemini REST API Body (Multimodal Prompt + Control Passes)
    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": extract_raw_b64(payload["clay_image"])
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": extract_raw_b64(payload["normal_image"])
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": extract_raw_b64(payload["edge_image"])
                        }
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": extract_raw_b64(payload["rgb_image"])
                        }
                    }
                ]
            }
        ]
    }

    # 4. Direct REST Call to Gemini API (No external SDK needed)
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    print("Calling Gemini API Endpoint...")
    json_data = json.dumps(request_body).encode("utf-8")
    req = urllib.request.Request(endpoint, data=json_data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            print("\n✅ API Response Received:")
            try:
                text_response = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(text_response)
            except (KeyError, IndexError):
                print(json.dumps(res_json, indent=2))

    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.read().decode('utf-8')}")
    except Exception as e:
        print(f"❌ Execution Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        payload_path = sys.argv[1]
    else:
        json_files = [f for f in os.listdir(".") if f.startswith("cesium_ground_truth_") and f.endswith(".json")]
        if not json_files:
            print("No payload JSON file found. Run index.html and click 'Export 5-Pass Payload' first.")
            sys.exit(1)
        payload_path = sorted(json_files)[-1]

    process_ground_truth_payload(payload_path)