"""
Atmosphere & Lighting Engine: Deterministic physical illumination and weather physics.
Calculates NOAA solar ephemeris (Azimuth, Elevation, CCT, Lux), queries real-time live weather
via Open-Meteo, and produces screen-space relighting and shadow-inversion directives.
"""

import math
from datetime import datetime, timezone, timedelta
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
    natural_description: str
    prompt_directive: str
    geojson_stratum: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def get_live_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Fetches real-time weather from Open-Meteo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover,wind_speed_10m"
    )
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json().get("current", {})
            code = data.get("weather_code", 0)
            temp_c = data.get("temperature_2m", 15.0)
            precip = data.get("precipitation", 0.0)
            clouds = data.get("cloud_cover", 20)

            if code in [71, 73, 75, 77, 85, 86]:
                condition = "SNOW"
                label = "Snowfall / Winter Flurries"
            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                condition = "RAIN"
                label = "Active Rain / Precipitation"
            elif code in [45, 48]:
                condition = "FOG"
                label = "Dense Ground Fog & Mist"
            elif clouds > 70 or code in [3]:
                condition = "OVERCAST"
                label = "100% Overcast Sky"
            else:
                condition = "SUNNY"
                label = "Clear Sky"

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

    return {
        "condition": "SUNNY",
        "label": "Clear (Default)",
        "temperature_c": 18.0,
        "precipitation_mm": 0.0,
        "cloud_cover_pct": 10,
        "weather_code": 0
    }


def _compute_solar_position(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float]:
    """Computes deterministic Solar Elevation and Azimuth using standard NOAA equations."""
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


def _classify_relative_light_vector(solar_azimuth: float, camera_heading: float) -> Dict[str, str]:
    """
    Translates NOAA solar angles into explicit screen-space 2D rendering instructions
    relative to the camera heading.
    """
    rel = (solar_azimuth - camera_heading) % 360.0

    if rel <= 22.5 or rel > 337.5:
        return {
            "summary": "direct front-lighting (Sun directly behind observer)",
            "screen_sun": "behind the camera",
            "facade_lighting": "all visible front-facing facades and structures are fully illuminated",
            "shadow_trajectory": "cast shadows fall directly away into the background behind objects",
            "shadow_erasure": "Overwrite all left- or right-angled side shadows with flat terrain albedo."
        }
    elif 22.5 < rel <= 67.5:
        return {
            "summary": "quarter-front light from camera-right",
            "screen_sun": "upper-right quadrant of the frame",
            "facade_lighting": "right-facing facades and the right side of monuments are brightly lit; left-facing facades are shaded",
            "shadow_trajectory": "cast shadows project diagonally to the LEFT across the ground",
            "shadow_erasure": "Erase any pre-existing shadows on the right; render newly lit surfaces on the right."
        }
    elif 67.5 < rel <= 112.5:
        return {
            "summary": "hard raking side-light from camera-right (East)",
            "screen_sun": "directly at the RIGHT edge of the frame",
            "facade_lighting": "all right-facing walls and the right side of the obelisk are in bright direct sun; left-facing walls are in deep shadow",
            "shadow_trajectory": "long horizontal cast shadows project across the terrain to the LEFT",
            "shadow_erasure": "Overwrite any pre-existing shadows on the right lawn with sunlit grass."
        }
    elif 112.5 < rel <= 157.5:
        return {
            "summary": "rear-right backlight",
            "screen_sun": "in the background to the upper-right",
            "facade_lighting": "structures are backlit silhouettes with bright rim lighting along right edges; front facades are in soft skylight",
            "shadow_trajectory": "long cast shadows project forward toward the lower-LEFT of the frame",
            "shadow_erasure": "Erase any sideways or rearward shadows from contradictory sun angles."
        }
    elif 157.5 < rel <= 202.5:
        return {
            "summary": "direct backlighting (Sun directly ahead near horizon)",
            "screen_sun": "directly ahead in the center background",
            "facade_lighting": "structures are backlit silhouettes with glowing halo rim light; all camera-facing surfaces are in shadow",
            "shadow_trajectory": "long cast shadows project directly forward toward the observer/bottom of the frame",
            "shadow_erasure": "Erase all sideways shadows; project all shadows forward."
        }
    elif 202.5 < rel <= 247.5:
        return {
            "summary": "rear-left backlight",
            "screen_sun": "in the background to the upper-left",
            "facade_lighting": "structures are backlit silhouettes with bright rim lighting along left edges; front facades are in soft skylight",
            "shadow_trajectory": "long cast shadows project forward toward the lower-RIGHT of the frame",
            "shadow_erasure": "Erase all pre-existing morning shadows cast to the left; project shadows toward the lower-right."
        }
    elif 247.5 < rel <= 292.5:
        return {
            "summary": "hard raking side-light from camera-left (West)",
            "screen_sun": "directly at the LEFT edge of the frame",
            "facade_lighting": "all left-facing walls and the left side of the obelisk/monument are in bright direct sunlight; right-facing walls are in shadow",
            "shadow_trajectory": "long directional cast shadows project across the terrain to the RIGHT",
            "shadow_erasure": "MANDATORY: Completely erase the pre-existing morning shadow on the left lawn and render as sunlit green grass. Cast the new shadow of the monument across the lawn to the RIGHT."
        }
    else:  # 292.5 to 337.5
        return {
            "summary": "quarter-front light from camera-left (West)",
            "screen_sun": "upper-left quadrant of the frame",
            "facade_lighting": "left-facing facades and the left side of monuments are brightly lit; right-facing facades are shaded",
            "shadow_trajectory": "cast shadows project diagonally to the RIGHT across the ground",
            "shadow_erasure": "MANDATORY: Completely erase the pre-existing morning shadow on the left lawn and render as sunlit green grass. Cast the new shadow toward the RIGHT."
        }


def _estimate_solar_cct_and_lux(elevation_deg: float) -> Tuple[int, int, str]:
    if elevation_deg > 50.0:
        return 5800, 85000, "High clear sun with short vertical shadows and neutral daylight"
    elif elevation_deg > 25.0:
        return 5400, 60000, "Clean standard daylight with distinct directional shadows"
    elif elevation_deg > 10.0:
        return 4500, 35000, "Late afternoon / mid-morning raking sunlight with warm highlights"
    elif elevation_deg > 1.0:
        return 3000, 12000, "Golden hour warm low-angle amber sunset illumination with long shadows"
    elif elevation_deg > -6.0:
        return 2200, 800, "Civil twilight blue hour with deep indigo ambient dome and soft shadows"
    else:
        return 2000, 5, "Night scene with celestial ambient illumination"


def resolve_lighting_state(
    lat: float,
    lon: float,
    camera_heading: float = 0.0,
    camera_pitch: float = -45.0,
    date_str: Optional[str] = None,
    time_of_day_hours: Optional[float] = None,
    timestamp_utc: Optional[str] = None,
    mode: str = "SOLAR",
    weather_mode: str = "AUTO"
) -> LightingState:
    """
    Authoritative physical illumination, NOAA ephemeris, and screen-space relighting engine.
    """

    # 1. Resolve DateTime & Timezone
    if date_str and time_of_day_hours is not None:
        try:
            tz_offset_hours = lon / 15.0
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            h = int(time_of_day_hours)
            m = int((time_of_day_hours - h) * 60)
            s = int((((time_of_day_hours - h) * 60) - m) * 60)
            local_dt = datetime(d.year, d.month, d.day, h, m, s)
            dt = (local_dt - timedelta(hours=tz_offset_hours)).replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"[Time Warning] {e}")
            dt = datetime.now(timezone.utc)
    elif timestamp_utc:
        try:
            dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # 2. Resolve Weather
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

    weather_descriptions = {
        "RAIN": "Active rain with wet, mirror-reflective asphalt, subtle puddles, and soft diffuse ambient sky illumination.",
        "FOG": "Dense ground fog and mist with light-scattering depth haze and softened horizon contrast.",
        "SNOW": "Crisp winter snow accumulation on horizontal ledges, roofs, and pavement edges under cool diffuse daylight.",
        "OVERCAST": "100% overcast cloud cover with soft, omnidirectional 6500K diffuse skylight and zero harsh shadow lines.",
        "SUNNY": "Crisp clear sky with direct solar exposure."
    }
    weather_text = weather_descriptions.get(active_weather, weather_descriptions["SUNNY"])

    # 3. FLOODLIGHT Mode
    if mode.upper() == LightingMode.FLOODLIGHT.value:
        natural_desc = (
            f"Pitch-black 0-lux night illuminated solely by a coaxial 5600K spotlight mounted at the observer viewpoint "
            f"({camera_heading:.1f}° heading) with realistic inverse-square falloff into darkness. {weather_text}"
        )
        prompt_directive = f"DELIGHTING & FLOODLIGHT RELIGHTING: {natural_desc}"

        geojson_stratum = {
            "type": "Feature",
            "id": "stratum_7_atmospheric_state",
            "geometry": None,
            "properties": {
                "stratum": "atmospheric_state",
                "lighting_rig": "CAMERA_FLOODLIGHT",
                "timestamp_utc": dt.isoformat(),
                "weather_state": active_weather,
                "ambient_lux": 0,
                "color_temperature_k": 5600,
                "beam_vector": {"heading_deg": round(camera_heading, 1), "pitch_deg": round(camera_pitch, 1)}
            }
        }

        metadata = {
            "mode": LightingMode.FLOODLIGHT.value,
            "weather": active_weather,
            "timestamp_utc": dt.isoformat(),
            "color_temperature_k": 5600,
            "lux": 0
        }

        return LightingState(
            mode=LightingMode.FLOODLIGHT,
            weather_mode=active_weather,
            natural_description=natural_desc,
            prompt_directive=prompt_directive,
            geojson_stratum=geojson_stratum,
            metadata=metadata
        )

    # 4. SOLAR Mode (Default)
    solar_azimuth, solar_elevation = _compute_solar_position(lat, lon, dt)
    cct, lux, epoch_desc = _estimate_solar_cct_and_lux(solar_elevation)
    rel_map = _classify_relative_light_vector(solar_azimuth, camera_heading)
    shadow_azimuth = round((solar_azimuth + 180.0) % 360.0, 1)

    natural_desc = (
        f"Calibrated {cct}K natural solar illumination ({epoch_desc}) with {rel_map['summary']} "
        f"(Sun Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°), casting directional shadows along {shadow_azimuth}°. {weather_text}"
    )

    # Screen-space relighting master directive
    prompt_directive = (
        f"SOLAR RELIGHTING DIRECTIVE ({cct}K {epoch_desc}):\n"
        f"- SUN POSITION IN SCREEN SPACE: Sun is located {rel_map['screen_sun']} (Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°).\n"
        f"- FACADE ILLUMINATION: {rel_map['facade_lighting']}.\n"
        f"- CAST SHADOW DIRECTION: {rel_map['shadow_trajectory']}.\n"
        f"- SHADOW OVERWRITE RULE: {rel_map['shadow_erasure']}\n"
        f"- WEATHER/SKY: {weather_text}"
    )

    geojson_stratum = {
        "type": "Feature",
        "id": "stratum_7_atmospheric_state",
        "geometry": None,
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
        }
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
        natural_description=natural_desc,
        prompt_directive=prompt_directive,
        geojson_stratum=geojson_stratum,
        metadata=metadata
    )