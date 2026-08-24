"""
Atmosphere & Lighting Engine: Deterministic physical illumination and weather physics.
Calculates NOAA solar ephemeris (Azimuth, Elevation, CCT, Lux), queries real-time live weather
via Open-Meteo, and builds crisp delighting and atmospheric relighting directives.
"""

import math
from datetime import datetime, timezone, time as dtime
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, Any, Optional, Tuple

import requests


class LightingMode(str, Enum):
    SOLAR = "SOLAR"
    FLOODLIGHT = "FLOODLIGHT"


class WeatherMode(str, Enum):
    AUTO = "AUTO"
    SUNNY = "SUNNY"
    RAIN = "RAIN"
    FOG = "FOG"
    SNOW = "SNOW"
    OVERCAST = "OVERCAST"


@dataclass
class LightingState:
    """Strongly typed output contract for lighting & atmospheric state."""
    mode: LightingMode
    weather_mode: str
    prompt_directive: str
    delighting_directive: str
    geojson_stratum: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_live_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetches real-time weather from Open-Meteo (free, no API key required).
    Maps WMO codes to standardized condition states.
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover,wind_speed_10m"
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json().get("current", {})
            code = data.get("weather_code", 0)
            temp_c = data.get("temperature_2m", 15.0)
            precip = data.get("precipitation", 0.0)
            clouds = data.get("cloud_cover", 20)

            # WMO Weather interpretation
            if code in [71, 73, 75, 77, 85, 86]:
                condition = "SNOW"
                label = "Snow / Flurries"
            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                condition = "RAIN"
                label = "Rain / Showers"
            elif code in [45, 48]:
                condition = "FOG"
                label = "Fog / Mist"
            elif clouds > 70 or code in [3]:
                condition = "OVERCAST"
                label = "Overcast Sky"
            else:
                condition = "SUNNY"
                label = "Clear / Sunny"

            return {
                "condition": condition,
                "label": label,
                "temperature_c": temp_c,
                "precipitation_mm": precip,
                "cloud_cover_pct": clouds,
                "weather_code": code
            }
    except Exception as e:
        print(f"[Weather API Warning]: {e}")

    # Fallback default
    return {
        "condition": "SUNNY",
        "label": "Clear (Default)",
        "temperature_c": 18.0,
        "precipitation_mm": 0.0,
        "cloud_cover_pct": 10,
        "weather_code": 0
    }


def _compute_solar_position(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float]:
    """Computes deterministic Solar Elevation and Azimuth using NOAA equations."""
    day_of_year = dt_utc.timetuple().tm_yday
    hour_float = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0

    gamma = 2.0 * math.pi / 365.0 * (day_of_year - 1 + (hour_float - 12.0) / 24.0)

    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2.0 * gamma)
        - 0.040849 * math.sin(2.0 * gamma)
    )

    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2.0 * gamma)
        + 0.000907 * math.sin(2.0 * gamma)
        - 0.002697 * math.cos(3.0 * gamma)
        + 0.001480 * math.sin(3.0 * gamma)
    )

    time_offset = eqtime + 4.0 * lon
    tst = (hour_float * 60.0 + time_offset) % 1440.0

    ha_deg = (tst / 4.0) - 180.0
    ha_rad = math.radians(ha_deg)
    lat_rad = math.radians(lat)

    cos_zenith = math.sin(lat_rad) * math.sin(decl) + math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith_rad = math.acos(cos_zenith)
    elevation_deg = 90.0 - math.degrees(zenith_rad)

    sin_zenith = math.sin(zenith_rad)
    if sin_zenith < 1e-4:
        azimuth_deg = 180.0
    else:
        cos_azimuth = (math.sin(lat_rad) * math.cos(zenith_rad) - math.sin(decl)) / (math.cos(lat_rad) * sin_zenith)
        cos_azimuth = max(-1.0, min(1.0, cos_azimuth))
        raw_azimuth = math.degrees(math.acos(cos_azimuth))
        azimuth_deg = (360.0 - raw_azimuth) % 360.0 if ha_deg > 0 else raw_azimuth % 360.0

    return round(azimuth_deg, 2), round(elevation_deg, 2)


def _classify_relative_light_vector(solar_azimuth: float, camera_heading: float) -> str:
    """Calculates relative sun direction against camera view axis."""
    rel = (solar_azimuth - camera_heading) % 360.0
    if rel <= 22.5 or rel > 337.5:
        return "Direct front-lighting"
    elif 22.5 < rel <= 67.5:
        return "Quarter-front light from camera-right"
    elif 67.5 < rel <= 112.5:
        return "Hard raking side-light from camera-right"
    elif 112.5 < rel <= 157.5:
        return "Rear-right backlight"
    elif 157.5 < rel <= 202.5:
        return "Direct backlighting / silhouetting"
    elif 202.5 < rel <= 247.5:
        return "Rear-left backlight"
    elif 247.5 < rel <= 292.5:
        return "Hard raking side-light from camera-left"
    else:
        return "Quarter-front light from camera-left"


def _estimate_solar_cct_and_lux(elevation_deg: float) -> Tuple[int, int, str]:
    if elevation_deg > 50.0:
        return 5800, 85000, "High clear sun with short vertical shadows"
    elif elevation_deg > 25.0:
        return 5400, 60000, "Clean standard daylight with directional shadows"
    elif elevation_deg > 10.0:
        return 4500, 35000, "Late afternoon / mid-morning raking sunlight"
    elif elevation_deg > 1.0:
        return 3000, 10000, "Golden hour warm low-angle sunlight with long shadows"
    elif elevation_deg > -6.0:
        return 2400, 800, "Civil twilight blue hour with deep ambient glow"
    else:
        return 2000, 5, "Night scene with celestial ambient dome"


def resolve_lighting_state(
    lat: float,
    lon: float,
    camera_heading: float,
    camera_pitch: float,
    date_str: Optional[str] = None,
    time_of_day_hours: Optional[float] = None,
    timestamp_utc: Optional[str] = None,
    mode: str = "SOLAR",
    weather_mode: str = "AUTO"
) -> LightingState:
    """
    Sole authority for deterministic illumination, delighting, and weather physics.
    """
    # 1. Base Delighting Directive
    delighting_directive = (
        "DELIGHTING: Discard all baked photogrammetric sunlight, source shadow maps, and specular highlights. "
        "Treat input geometry strictly as an unlit structural reference. "
    )

    # 2. Resolve DateTime
    if timestamp_utc:
        try:
            dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    elif date_str and time_of_day_hours is not None:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            h = int(time_of_day_hours)
            m = int((time_of_day_hours - h) * 60)
            dt = datetime.combine(d, dtime(hour=h, minute=m), tzinfo=timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # 3. Resolve Weather
    if weather_mode.upper() == "AUTO":
        weather_info = get_live_weather(lat, lon)
        active_weather = weather_info["condition"]
    else:
        active_weather = weather_mode.upper()
        weather_info = {
            "condition": active_weather,
            "label": active_weather,
            "temperature_c": 15.0,
            "precipitation_mm": 5.0 if active_weather == "RAIN" else 0.0,
            "cloud_cover_pct": 100 if active_weather in ["RAIN", "OVERCAST"] else 10,
            "weather_code": 0
        }

    # Weather Directives
    weather_shaders = {
        "RAIN": "Weather: Active rain. Wet, mirror-reflective asphalt and pavement with crisp surface puddles; soft diffuse skylight.",
        "FOG": "Weather: Dense ground fog and mist with light-scattering depth haze and low horizon visibility.",
        "SNOW": "Weather: Crisp winter dusting and snow accumulation on horizontal ledges, roofs, and pavement edges; cold diffuse daylight.",
        "OVERCAST": "Weather: 100% overcast cloud cover. Soft omnidirectional diffuse skylight (6500K) with zero harsh cast shadow edges.",
        "SUNNY": "Weather: Crisp clear sky with direct solar exposure."
    }
    weather_text = weather_shaders.get(active_weather, weather_shaders["SUNNY"])

    # 4. Handle FLOODLIGHT Mode
    if mode.upper() == LightingMode.FLOODLIGHT.value:
        prompt_directive = (
            f"{delighting_directive}"
            f"DYNAMIC RELIGHTING (ON-CAMERA FLOODLIGHT): Pitch-black 0-lux night. "
            f"Scene lit solely by a coaxial 5600K spotlight mounted on camera ({camera_heading:.1f}° heading) "
            f"with 1/(d²) falloff. Immediate facades brightly illuminated while background falls into black void. "
            f"{weather_text}"
        )

        geojson_stratum = {
            "type": "Feature",
            "id": "stratum_7_atmospheric_state",
            "properties": {
                "stratum": "atmospheric_state",
                "lighting_rig": "CAMERA_FLOODLIGHT",
                "timestamp_utc": dt.isoformat(),
                "weather_state": active_weather,
                "ambient_lux": 0,
                "color_temperature_k": 5600,
                "beam_vector": {"heading_deg": round(camera_heading, 1), "pitch_deg": round(camera_pitch, 1)}
            },
            "geometry": None
        }

        metadata = {
            "mode": LightingMode.FLOODLIGHT.value,
            "weather": active_weather,
            "timestamp_utc": dt.isoformat(),
            "color_temperature_k": 5600
        }

        return LightingState(
            mode=LightingMode.FLOODLIGHT,
            weather_mode=active_weather,
            prompt_directive=prompt_directive,
            delighting_directive=delighting_directive,
            geojson_stratum=geojson_stratum,
            metadata=metadata
        )

    # 5. Handle SOLAR Mode (Default)
    solar_azimuth, solar_elevation = _compute_solar_position(lat, lon, dt)
    cct, lux, desc = _estimate_solar_cct_and_lux(solar_elevation)
    rel_light = _classify_relative_light_vector(solar_azimuth, camera_heading)
    shadow_azimuth = round((solar_azimuth + 180.0) % 360.0, 1)

    prompt_directive = (
        f"{delighting_directive}"
        f"DYNAMIC RELIGHTING: Sun Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}° ({desc}). "
        f"{rel_light}, calibrated {cct}K solar irradiance casting crisp shadows along {shadow_azimuth}° vector. "
        f"{weather_text}"
    )

    geojson_stratum = {
        "type": "Feature",
        "id": "stratum_7_atmospheric_state",
        "properties": {
            "stratum": "atmospheric_state",
            "lighting_rig": "SOLAR_EPHEMERIS",
            "timestamp_utc": dt.isoformat(),
            "weather_state": active_weather,
            "temperature_c": weather_info.get("temperature_c"),
            "solar_azimuth_deg": solar_azimuth,
            "solar_elevation_deg": solar_elevation,
            "shadow_azimuth_deg": shadow_azimuth,
            "color_temperature_k": cct,
            "ambient_illuminance_lux": lux
        },
        "geometry": None
    }

    metadata = {
        "mode": LightingMode.SOLAR.value,
        "weather": active_weather,
        "timestamp_utc": dt.isoformat(),
        "solar_azimuth": solar_azimuth,
        "solar_elevation": solar_elevation,
        "color_temperature_k": cct,
        "lux": lux
    }

    return LightingState(
        mode=LightingMode.SOLAR,
        weather_mode=active_weather,
        prompt_directive=prompt_directive,
        delighting_directive=delighting_directive,
        geojson_stratum=geojson_stratum,
        metadata=metadata
    )