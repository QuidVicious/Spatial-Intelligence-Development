"""
Atmosphere & Lighting Engine: Deterministic physical illumination and weather physics.
Calculates NOAA solar ephemeris (Azimuth, Elevation, CCT, Lux), queries real-time live weather
and true coordinate timezone via Open-Meteo, and produces screen-space relighting directives.
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
    """Fetches real-time weather and coordinate timezone from Open-Meteo."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
        f"&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,cloud_cover,wind_speed_10m"
        f"&timezone=auto"
    )
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            resp_json = resp.json()
            data = resp_json.get("current", {})
            code = data.get("weather_code", 0)
            temp_c = data.get("temperature_2m", 15.0)
            precip = data.get("precipitation", 0.0)
            clouds = data.get("cloud_cover", 20)
            utc_offset_sec = resp_json.get("utc_offset_seconds", 0)
            tz_name = resp_json.get("timezone", "UTC")

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
                "weather_code": code,
                "utc_offset_seconds": utc_offset_sec,
                "timezone": tz_name
            }
    except Exception as e:
        print(f"[Weather API Warning]: {e}")

    return {
        "condition": "SUNNY",
        "label": "Clear (Default)",
        "temperature_c": 18.0,
        "precipitation_mm": 0.0,
        "cloud_cover_pct": 10,
        "weather_code": 0,
        "utc_offset_seconds": int(lon / 15.0 * 3600),
        "timezone": "UTC"
    }


def _compute_solar_position(lat: float, lon: float, dt_utc: datetime) -> Tuple[float, float]:
    """Computes deterministic Solar Elevation and Azimuth (0° True North, clockwise) using standard NOAA equations."""
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
        
        # NOAA piecewise quadrant correction (0° = True North, clockwise)
        if ha_deg > 0:
            azimuth_deg = (raw_azimuth + 180.0) % 360.0
        else:
            azimuth_deg = (540.0 - raw_azimuth) % 360.0

    return round(azimuth_deg, 2), round(elevation_deg, 2)


def _classify_relative_light_vector(solar_azimuth: float, camera_heading: float) -> Dict[str, str]:
    """High-density telegraphic spatial tokenization of lighting and shadow trajectories."""
    rel = (solar_azimuth - camera_heading) % 360.0

    if rel <= 22.5 or rel > 337.5:
        return {
            "summary": "direct front-lighting",
            "screen_sun": "behind camera",
            "facade_lighting": "front facades directly illuminated",
            "shadow_trajectory": "cast shadows project away behind structures"
        }
    elif 22.5 < rel <= 67.5:
        return {
            "summary": "quarter-front light from upper-right",
            "screen_sun": "in upper-right quadrant",
            "facade_lighting": "right facades lit, left facades shaded",
            "shadow_trajectory": "cast shadows project diagonally to LEFT"
        }
    elif 67.5 < rel <= 112.5:
        return {
            "summary": "hard raking side-light from camera-right",
            "screen_sun": "at camera-right",
            "facade_lighting": "right walls in direct sun, left walls in deep shadow",
            "shadow_trajectory": "long lateral shadows project across ground to LEFT"
        }
    elif 112.5 < rel <= 157.5:
        return {
            "summary": "rear-right backlight",
            "screen_sun": "background upper-right",
            "facade_lighting": "backlit silhouettes with right rim lighting",
            "shadow_trajectory": "shadows project forward toward lower-LEFT"
        }
    elif 157.5 < rel <= 202.5:
        return {
            "summary": "direct backlighting",
            "screen_sun": "directly ahead in center background",
            "facade_lighting": "backlit silhouettes with halo rim light; camera-facing facades in shadow",
            "shadow_trajectory": "shadows project directly forward toward camera"
        }
    elif 202.5 < rel <= 247.5:
        return {
            "summary": "rear-left backlight",
            "screen_sun": "background upper-left",
            "facade_lighting": "backlit silhouettes with left rim lighting",
            "shadow_trajectory": "shadows project forward toward lower-RIGHT"
        }
    elif 247.5 < rel <= 292.5:
        return {
            "summary": "hard raking side-light from camera-left",
            "screen_sun": "at camera-left",
            "facade_lighting": "left walls in direct sun, right walls in deep shadow",
            "shadow_trajectory": "long lateral shadows project across ground to RIGHT"
        }
    else:
        return {
            "summary": "quarter-front light from upper-left",
            "screen_sun": "in upper-left quadrant",
            "facade_lighting": "left facades lit, right facades shaded",
            "shadow_trajectory": "cast shadows project diagonally to RIGHT"
        }


def _estimate_solar_cct_and_lux(elevation_deg: float, solar_azimuth: float) -> Tuple[int, int, str]:
    """AM / PM ephemeris color temperature and lux estimation."""
    is_morning = solar_azimuth < 180.0

    if elevation_deg > 50.0:
        return 5800, 85000, "High clear sun with short vertical shadows and neutral daylight"
    elif elevation_deg > 25.0:
        epoch = "Clean morning daylight" if is_morning else "Clean afternoon daylight"
        return 5400, 60000, f"{epoch} with crisp directional shadows"
    elif elevation_deg > 10.0:
        epoch = "Mid-morning raking sunlight" if is_morning else "Late afternoon raking sunlight with warm golden highlights"
        return 4500, 35000, epoch
    elif elevation_deg > 1.0:
        epoch = "Dawn / early sunrise low-angle golden hour" if is_morning else "Dusk / late sunset low-angle amber golden hour"
        return 3000, 12000, f"{epoch} with elongated cast shadows"
    elif elevation_deg > -6.0:
        return 2200, 800, "Civil twilight blue hour with indigo sky dome and soft ambient contact shadows"
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
    
    # 1. Resolve Weather & True Timezone Offset
    weather_info = get_live_weather(lat, lon)
    active_weather = weather_info["condition"] if weather_mode.upper() == "AUTO" else weather_mode.upper()
    utc_offset_sec = weather_info.get("utc_offset_seconds", 0)

    # 2. Resolve DateTime
    if date_str and time_of_day_hours is not None:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            h = int(time_of_day_hours)
            m = int((time_of_day_hours - h) * 60)
            s = int((((time_of_day_hours - h) * 60) - m) * 60)
            local_dt = datetime(d.year, d.month, d.day, h, m, s)
            dt = (local_dt - timedelta(seconds=utc_offset_sec)).replace(tzinfo=timezone.utc)
        except Exception as e:
            print(f"[Time Resolution Warning]: {e}")
            dt = datetime.now(timezone.utc)
    elif timestamp_utc:
        try:
            dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    # 3. FLOODLIGHT Mode
    if mode.upper() == LightingMode.FLOODLIGHT.value:
        natural_desc = f"Coaxial 5600K spotlight from observer ({camera_heading:.1f}° heading). Weather: {active_weather}."
        prompt_directive = f"LIGHTING: Coaxial 5600K spotlight from camera heading {camera_heading:.1f}°. Pure forward illumination."

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

        return LightingState(
            mode=LightingMode.FLOODLIGHT,
            weather_mode=active_weather,
            natural_description=natural_desc,
            prompt_directive=prompt_directive,
            geojson_stratum=geojson_stratum,
            metadata={"mode": "FLOODLIGHT", "weather": active_weather, "timestamp_utc": dt.isoformat()}
        )

    # 4. SOLAR Mode (Deterministic Ephemeris)
    solar_azimuth, solar_elevation = _compute_solar_position(lat, lon, dt)
    cct, lux, epoch_desc = _estimate_solar_cct_and_lux(solar_elevation, solar_azimuth)
    shadow_azimuth = round((solar_azimuth + 180.0) % 360.0, 1)

    is_explicit_overcast = (weather_mode.upper() == "OVERCAST")
    is_custom_datetime = (date_str is not None)

    if solar_elevation <= 0.0:
        is_blue_hour = solar_elevation > -6.0
        twilight_type = "Blue Hour Civil Twilight" if is_blue_hour else "Nocturnal Night Scene"
        natural_desc = f"Calibrated {cct}K {twilight_type} (Elevation {solar_elevation:.1f}°). Weather: {active_weather}."
        prompt_directive = (
            f"LIGHTING: {cct}K {twilight_type}. Sun elevation {solar_elevation:.1f}°. "
            f"Zero direct sunlight. Extinguish daytime cast shadows. Diffuse indigo ambient skylight with soft contact occlusion."
        )
    elif is_explicit_overcast or (active_weather in ["OVERCAST", "FOG"] and not is_custom_datetime):
        weather_diffuse_directives = {
            "OVERCAST": "100% overcast cloud cover. Soft omnidirectional 6500K diffuse skylight. Zero harsh directional cast shadows; render ambient contact occlusion under cornices and ledges only.",
            "FOG": "Dense ground mist and atmospheric fog. Light-scattering depth haze, low horizon contrast, muted diffuse ambient illumination."
        }
        diffuse_rule = weather_diffuse_directives.get(active_weather, weather_diffuse_directives["OVERCAST"])
        natural_desc = f"Calibrated {cct}K diffuse daylight under {active_weather} conditions (Sun Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°)."
        prompt_directive = f"ATMOSPHERIC LIGHTING ({active_weather}): {diffuse_rule}"
    else:
        # Solar Ephemeris is authoritative for custom date/time and sunny/clear conditions
        rel_map = _classify_relative_light_vector(solar_azimuth, camera_heading)
        natural_desc = (
            f"Calibrated {cct}K {epoch_desc} ({rel_map['summary']}, Sun Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°). Clear sky."
        )
        prompt_directive = (
            f"SOLAR LIGHT VECTOR ({cct}K {epoch_desc}): Sun {rel_map['screen_sun']} (Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°). "
            f"{rel_map['facade_lighting']}. {rel_map['shadow_trajectory']}."
        )

    is_diffuse_state = is_explicit_overcast or (active_weather in ["OVERCAST", "FOG"] and not is_custom_datetime)

    geojson_stratum = {
        "type": "Feature",
        "id": "stratum_7_atmospheric_state",
        "geometry": None,
        "properties": {
            "stratum": "atmospheric_state",
            "lighting_rig": "SOLAR_EPHEMERIS",
            "timestamp_utc": dt.isoformat(),
            "weather_state": active_weather,
            "solar_azimuth_deg": solar_azimuth,
            "solar_elevation_deg": solar_elevation,
            "shadow_azimuth_deg": shadow_azimuth if (solar_elevation > 0.0 and not is_diffuse_state) else None,
            "color_temperature_k": cct,
            "ambient_illuminance_lux": lux
        }
    }

    return LightingState(
        mode=LightingMode.SOLAR,
        weather_mode=active_weather,
        natural_description=natural_desc,
        prompt_directive=prompt_directive,
        geojson_stratum=geojson_stratum,
        metadata={
            "mode": "SOLAR",
            "weather": active_weather,
            "timestamp_utc": dt.isoformat(),
            "solar_azimuth": solar_azimuth,
            "solar_elevation": solar_elevation,
            "color_temperature_k": cct,
            "lux": lux
        }
    )