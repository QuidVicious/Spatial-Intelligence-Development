"""
Lighting Engine: Deterministic illumination physics and delighting rig.
Calculates astronomical solar ephemeris (Sun Azimuth, Elevation, Kelvin CCT)
or camera-locked optical floodlight vectors for synthetic relighting.
"""

import math
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional, Tuple


class LightingMode(str, Enum):
    SOLAR = "SOLAR"
    FLOODLIGHT = "FLOODLIGHT"


@dataclass
class LightingState:
    """Strongly typed output contract for the lighting state."""
    mode: LightingMode
    prompt_directive: str
    delighting_directive: str
    geojson_stratum: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _compute_solar_position(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float]:
    """
    Computes deterministic Solar Elevation and Solar Azimuth from Lat/Lon/UTC time
    using standard NOAA Solar Position equations (pure Python).
    Returns (azimuth_deg, elevation_deg).
    """
    # Day of year and fractional hour
    day_of_year = dt_utc.timetuple().tm_yday
    hour_float = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    # Fractional year in radians
    gamma = 2.0 * math.pi / 365.0 * (day_of_year - 1 + (hour_float - 12.0) / 24.0)

    # Equation of time (in minutes)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )

    # Solar declination angle (in radians)
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
        - 0.002697 * math.cos(3.0 * gamma)
        + 0.001480 * math.sin(3.0 * gamma)
    )

    # True solar time (in minutes)
    time_offset = eqtime + 4.0 * lon
    tst = (hour_float * 60.0 + time_offset) % 1440.0

    # Solar hour angle (degrees to radians)
    ha_deg = (tst / 4.0) - 180.0
    ha_rad = math.radians(ha_deg)
    lat_rad = math.radians(lat)

    # Solar zenith & elevation
    cos_zenith = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith_rad = math.acos(cos_zenith)
    elevation_deg = 90.0 - math.degrees(zenith_rad)

    # Solar azimuth (degrees clockwise from North)
    sin_zenith = math.sin(zenith_rad)
    if sin_zenith < 1e-4:
        azimuth_deg = 180.0
    else:
        cos_azimuth = (math.sin(lat_rad) * math.cos(zenith_rad) - math.sin(decl)) / (math.cos(lat_rad) * sin_zenith)
        cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
        raw_azimuth = math.degrees(math.acos(cos_azimuth))
        if ha_deg > 0:
            azimuth_deg = (360.0 - raw_azimuth) % 360.0
        else:
            azimuth_deg = raw_azimuth % 360.0

    return round(azimuth_deg, 2), round(elevation_deg, 2)


def _classify_relative_light_vector(solar_azimuth: float, camera_heading: float) -> str:
    """Calculates where the sun is relative to the camera view axis."""
    rel = (solar_azimuth - camera_heading) % 360.0
    if rel <= 22.5 or rel > 337.5:
        return "Direct front-lighting (Sun behind camera illuminating facades directly)"
    elif 22.5 < rel <= 67.5:
        return "Quarter-front lighting from camera-right"
    elif 67.5 < rel <= 112.5:
        return "Hard raking side-lighting from camera-right (90°)"
    elif 112.5 < rel <= 157.5:
        return "Rear-right rim lighting / backlight"
    elif 157.5 < rel <= 202.5:
        return "Direct backlighting / silhouetting (Sun facing camera)"
    elif 202.5 < rel <= 247.5:
        return "Rear-left rim lighting / backlight"
    elif 247.5 < rel <= 292.5:
        return "Hard raking side-lighting from camera-left (90°)"
    else:
        return "Quarter-front lighting from camera-left"


def _estimate_solar_cct_and_lux(elevation_deg: float) -> Tuple[int, int, str]:
    """Calculates correlated color temperature (Kelvin), illuminance (Lux), and atmospheric description."""
    if elevation_deg > 50.0:
        return 5800, 85000, "High noon harsh clear daylight with short vertical shadows"
    elif elevation_deg > 25.0:
        return 5400, 60000, "Clean standard midday daylight with distinct directional shadows"
    elif elevation_deg > 10.0:
        return 4500, 35000, "Warm late-afternoon/mid-morning solar angle with lengthening shadows"
    elif elevation_deg > 1.0:
        return 3000, 10000, "Golden hour low-angle warm sunlight casting dramatic raking horizontal shadows"
    elif elevation_deg > -6.0:
        return 2400, 800, "Civil twilight / blue hour with deep ambient sky glow and fading horizon warm hues"
    else:
        return 2000, 5, "Night scene with near-zero solar lux and dark celestial ambient dome"


def resolve_lighting_state(
    lat: float,
    lon: float,
    camera_heading: float,
    camera_pitch: float,
    timestamp_utc: Optional[str] = None,
    mode: str = "SOLAR",
    custom_cct_k: Optional[int] = None
) -> LightingState:
    """
    Main entry point. Builds deterministic lighting parameters, prompt directives,
    and GeoJSON Stratum 7 data for either Solar Ephemeris or Camera Floodlight.
    """
    # 1. Base Delighting directive (enforces stripping baked capture light)
    delighting_directive = (
        "DELIGHTING DIRECTIVE: Treat the attached image strictly as an unlit 3D structural skeleton "
        "(geometry, perspective, massing, and placement). Completely strip, discard, and cancel all baked "
        "photogrammetric sunlight, source shadow maps, ambient occlusion, and specular highlights from the capture."
    )

    # 2. Resolve Timestamp
    if timestamp_utc:
        try:
            dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # Handle FLOODLIGHT Mode
    if mode.upper() == LightingMode.FLOODLIGHT.value:
        cct = custom_cct_k or 5600
        prompt_directive = (
            f"{delighting_directive} "
            f"DYNAMIC RELIGHTING (ON-CAMERA FLOODLIGHT): Pitch-black night environment (0 lux ambient sky). "
            f"Scene is illuminated exclusively by a high-intensity directional spotlight mounted coaxial on the camera "
            f"facing {camera_heading:.1f}° heading at {camera_pitch:.1f}° pitch. "
            f"Calibrated {cct}K clean white beam with steep 1/(d^2) inverse-square falloff—immediate foreground facades "
            f"and pavement are brightly illuminated while background drops into deep black void; "
            f"zero visible cast ground shadows along optical axis with razor-thin silhouette rim outlines."
        )

        geojson_stratum = {
            "type": "Feature",
            "id": "stratum_7_atmospheric_state",
            "properties": {
                "stratum": "atmospheric_state",
                "lighting_rig": "CAMERA_FLOODLIGHT",
                "timestamp_utc": dt.isoformat(),
                "ambient_lux": 0,
                "color_temperature_k": cct,
                "beam_vector": {
                    "heading_deg": round(camera_heading, 1),
                    "pitch_deg": round(camera_pitch, 1)
                },
                "optical_profile": "Inverse-square distance falloff, coaxial zero-shadow alignment"
            },
            "geometry": None
        }

        metadata = {
            "mode": LightingMode.FLOODLIGHT.value,
            "timestamp_utc": dt.isoformat(),
            "color_temperature_k": cct,
            "heading": camera_heading,
            "pitch": camera_pitch
        }

        return LightingState(
            mode=LightingMode.FLOODLIGHT,
            prompt_directive=prompt_directive,
            delighting_directive=delighting_directive,
            geojson_stratum=geojson_stratum,
            metadata=metadata
        )

    # Handle SOLAR Mode (Default)
    solar_azimuth, solar_elevation = _compute_solar_position(lat, lon, dt)
    cct, lux, desc = _estimate_solar_cct_and_lux(solar_elevation)
    if custom_cct_k:
        cct = custom_cct_k

    rel_light_desc = _classify_relative_light_vector(solar_azimuth, camera_heading)

    prompt_directive = (
        f"{delighting_directive} "
        f"DYNAMIC RELIGHTING (SOLAR EPHEMERIS): Scene relit with physically grounded astronomical solar vectors. "
        f"Sun Position: Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}° ({desc}). "
        f"Illumination Vector: {rel_light_desc}. "
        f"Color Temperature: Calibrated {cct}K Kelvin solar irradiance casting sharp, geometrically authentic "
        f"directional shadows aligned strictly to {((solar_azimuth + 180.0) % 360.0):.1f}° shadow vector."
    )

    geojson_stratum = {
        "type": "Feature",
        "id": "stratum_7_atmospheric_state",
        "properties": {
            "stratum": "atmospheric_state",
            "lighting_rig": "SOLAR_EPHEMERIS",
            "timestamp_utc": dt.isoformat(),
            "solar_azimuth_deg": solar_azimuth,
            "solar_elevation_deg": solar_elevation,
            "shadow_azimuth_deg": round((solar_azimuth + 180.0) % 360.0, 1),
            "color_temperature_k": cct,
            "ambient_illuminance_lux": lux,
            "relative_camera_lighting": rel_light_desc,
            "sky_condition": desc
        },
        "geometry": None
    }

    metadata = {
        "mode": LightingMode.SOLAR.value,
        "timestamp_utc": dt.isoformat(),
        "solar_azimuth": solar_azimuth,
        "solar_elevation": solar_elevation,
        "color_temperature_k": cct,
        "lux": lux
    }

    return LightingState(
        mode=LightingMode.SOLAR,
        prompt_directive=prompt_directive,
        delighting_directive=delighting_directive,
        geojson_stratum=geojson_stratum,
        metadata=metadata
    )


# --- Standalone Diagnostic Runner ---
if __name__ == "__main__":
    print("=" * 70)
    print("=== Lighting Engine (Ephemeris & Floodlight) Diagnostic ===")
    print("=" * 70)

    # Test Location: Edinburgh, Scotland (55.9533° N, 3.1883° W), Camera Heading 315° (NW)
    lat, lon, heading, pitch = 55.9533, -3.1883, 315.0, -12.0

    # 1. Test Solar Ephemeris at Solar Noon (Summer)
    summer_noon = "2026-06-21T12:30:00Z"
    solar_noon_state = resolve_lighting_state(lat, lon, heading, pitch, timestamp_utc=summer_noon, mode="SOLAR")
    print("\n[TEST 1: Solar Noon (Midsummer)]")
    print(f"Azimuth: {solar_noon_state.metadata['solar_azimuth']}° | Elevation: {solar_noon_state.metadata['solar_elevation']}° | CCT: {solar_noon_state.metadata['color_temperature_k']}K")
    print(f"Prompt Directive:\n{solar_noon_state.prompt_directive}\n")

    # 2. Test Solar Ephemeris at Golden Hour (Sunset)
    golden_hour = "2026-06-21T20:30:00Z"
    golden_state = resolve_lighting_state(lat, lon, heading, pitch, timestamp_utc=golden_hour, mode="SOLAR")
    print("[TEST 2: Golden Hour Sunset]")
    print(f"Azimuth: {golden_state.metadata['solar_azimuth']}° | Elevation: {golden_state.metadata['solar_elevation']}° | CCT: {golden_state.metadata['color_temperature_k']}K")
    print(f"Prompt Directive:\n{golden_state.prompt_directive}\n")

    # 3. Test Camera Night Floodlight
    floodlight_state = resolve_lighting_state(lat, lon, heading, pitch, mode="FLOODLIGHT")
    print("[TEST 3: Camera Night Floodlight]")
    print(f"Mode: {floodlight_state.mode} | Vector: Heading {heading}°, Pitch {pitch}°")
    print(f"Prompt Directive:\n{floodlight_state.prompt_directive}\n")
    print(f"Stratum 7 GeoJSON Payload:")
    import json
    print(json.dumps(floodlight_state.geojson_stratum, indent=2))
    print("=" * 70)