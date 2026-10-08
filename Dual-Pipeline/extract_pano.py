import re
import base64

def extract_pano_id(url):
    # Pattern 1: Look for official Google Street View coverage id (22 chars)
    pattern_thumb = r'(?:panoid%3D|panoid=)([A-Za-z0-9_-]+)'
    match = re.search(pattern_thumb, url)
    if match:
        return match.group(1)

    # Pattern 2: Detect if it's a user-uploaded photo sphere (Look for the !1s marker)
    # These often extract as a 22-character shorthand token in the URL data
    pattern_data = r'!1s([A-Za-z0-9_-]{22})'
    match_data = re.search(pattern_data, url)
    
    if match_data:
        short_id = match_data.group(1)
        
        # If the short ID starts with 'CIHM', it's a user photo sphere. 
        # External mapping tools need the full API-compliant long string.
        if short_id.startswith('CIHM'):
            try:
                # Reconstruct the long-form 'CAMSS...' Pano ID required by external tools
                raw_bytes = b'\x08\x01\x12\x16' + short_id.encode('utf-8')
                long_id = base64.b64encode(raw_bytes).decode('utf-8').replace('=', '')
                return f"CAMSS{long_id}"
            except Exception:
                return short_id # Fallback if encoding fails
        return short_id
        
    return None

print("--- Upgraded Google Maps Pano ID Extractor ---")
print("Paste your URL and press Enter. Type 'exit' or 'q' to quit.\n")

while True:
    user_input = input("Paste Google Maps URL: ").strip()
    
    if user_input.lower() in ['exit', 'q']:
        print("Exiting tool. Goodbye!")
        break
        
    if not user_input:
        continue
        
    pano_id = extract_pano_id(user_input)
    
    if pano_id:
        print(f"-> Compatible Pano ID: {pano_id}\n")
    else:
        print("-> [Error] Could not find a Panorama ID in that URL.\n")
