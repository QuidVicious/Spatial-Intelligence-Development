"""
Atmosphere & Lighting Engine: Deterministic physical illumination and weather physics.
Calculates NOAA solar ephemeris (Azimuth, Elevation, CCT, Lux), queries real-time live weather
and true coordinate timezone via Open-Meteo, and produces screen-space relighting directives.
"""

import math
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None
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


# NWS station lookups are stable for a location, so cache them.
_NWS_STATION_CACHE: Dict[str, Any] = {}
_NWS_HEADERS = {
    "User-Agent": "(SquidBlackSpatial, spatial-intelligence-pipeline)",
    "Accept": "application/geo+json"
}


def _nws_stations(lat: float, lon: float) -> Optional[list]:
    """Nearest observation stations, closest first. None outside NWS coverage."""
    key = f"{lat:.2f},{lon:.2f}"
    if key in _NWS_STATION_CACHE:
        return _NWS_STATION_CACHE[key]
    try:
        pt = requests.get(f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
                          headers=_NWS_HEADERS, timeout=5)
        if pt.status_code != 200:
            _NWS_STATION_CACHE[key] = None
            return None
        stations_url = pt.json().get("properties", {}).get("observationStations")
        if not stations_url:
            _NWS_STATION_CACHE[key] = None
            return None
        st = requests.get(stations_url, headers=_NWS_HEADERS, timeout=5)
        if st.status_code != 200:
            _NWS_STATION_CACHE[key] = None
            return None
        ids = [f.get("properties", {}).get("stationIdentifier")
               for f in st.json().get("features", [])]
        ids = [i for i in ids if i][:5]
        _NWS_STATION_CACHE[key] = ids or None
        return _NWS_STATION_CACHE[key]
    except Exception as e:
        print(f"[NWS Warning] station lookup: {e}")
        _NWS_STATION_CACHE[key] = None
        return None


def get_nws_observation(lat: float, lon: float, max_age_min: int = 120) -> Optional[Dict[str, Any]]:
    """
    Actual sky cover from the nearest US observation station.

    This is a measurement, not a model interpolation. Open-Meteo reports the
    latest numerical model run for a grid cell, which near coastlines can
    disagree sharply with what is overhead. Cloud amount here comes from
    METAR octas: CLR/SKC, FEW, SCT, BKN, OVC.
    """
    stations = _nws_stations(lat, lon)
    if not stations:
        return None

    for station in stations:
        try:
            r = requests.get(
                f"https://api.weather.gov/stations/{station}/observations/latest",
                headers=_NWS_HEADERS, timeout=5
            )
            if r.status_code != 200:
                continue
            props = r.json().get("properties", {}) or {}

            ts = props.get("timestamp")
            if ts:
                try:
                    obs_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    age_min = (datetime.now(timezone.utc) - obs_dt).total_seconds() / 60.0
                    if age_min > max_age_min:
                        continue
                except Exception:
                    age_min = None
            else:
                age_min = None

            layers = props.get("cloudLayers") or []
            if not layers:
                continue  # AWOS station with no sky sensor; try the next one

            order = {"CLR": 0, "SKC": 0, "FEW": 1, "SCT": 2, "BKN": 3, "OVC": 4}
            amounts = [(l.get("amount") or "").upper() for l in layers]
            top = max(amounts, key=lambda a: order.get(a, 0)) if amounts else "CLR"

            temp_c = (props.get("temperature") or {}).get("value")
            text = (props.get("textDescription") or "").lower()

            if any(w in text for w in ("snow", "sleet", "flurr")):
                condition, label = "SNOW", "Snow (observed)"
            elif any(w in text for w in ("rain", "drizzle", "shower", "thunder")):
                condition, label = "RAIN", "Rain (observed)"
            elif any(w in text for w in ("fog", "mist", "haze")):
                condition, label = "FOG", "Fog / Mist (observed)"
            elif top == "OVC":
                condition, label = "OVERCAST", "Overcast (observed)"
            elif top == "BKN":
                condition, label = "PARTLY", "Broken Cloud (observed)"
            elif top == "SCT":
                condition, label = "PARTLY", "Scattered Cloud (observed)"
            elif top == "FEW":
                condition, label = "SUNNY", "Few Clouds (observed)"
            else:
                condition, label = "SUNNY", "Clear (observed)"

            pct = {"CLR": 0, "SKC": 0, "FEW": 20, "SCT": 40, "BKN": 75, "OVC": 100}.get(top, 0)

            return {
                "condition": condition,
                "label": label,
                "temperature_c": temp_c if temp_c is not None else 15.0,
                "precipitation_mm": 0.0,
                "cloud_cover_pct": pct,
                "weather_code": None,
                "source": "NWS",
                "station": station,
                "sky_cover": top,
                "observation_age_min": round(age_min, 1) if age_min is not None else None,
                "text_description": props.get("textDescription")
            }
        except Exception as e:
            print(f"[NWS Warning] {station}: {e}")
            continue
    return None


def get_live_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Observed conditions first (NWS, US only), model conditions second
    (Open-Meteo, worldwide). Timezone always comes from Open-Meteo since NWS
    does not supply a UTC offset.
    """
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

            # WMO weather_code is authoritative for sky state.
            #   0 clear, 1 mainly clear, 2 partly cloudy, 3 overcast
            # cloud_cover is TOTAL cloud fraction at all levels, so thin high
            # cirrus on a bright day reports 70-90% while the sun is fully out.
            # Using it to override the code turned sunny days into overcast ones.
            if code in [71, 73, 75, 77, 85, 86]:
                condition = "SNOW"
                label = "Snowfall / Winter Flurries"
            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                condition = "RAIN"
                label = "Active Rain / Precipitation"
            elif code in [45, 48]:
                condition = "FOG"
                label = "Dense Ground Fog & Mist"
            elif code == 3:
                condition = "OVERCAST"
                label = f"Overcast ({clouds:.0f}% cloud)"
            elif code == 2:
                condition = "PARTLY"
                label = f"Partly Cloudy ({clouds:.0f}% cloud)"
            elif code == 1:
                condition = "PARTLY" if clouds >= 50 else "SUNNY"
                label = f"Mainly Clear ({clouds:.0f}% cloud)"
            else:
                condition = "SUNNY"
                label = f"Clear Sky ({clouds:.0f}% cloud)"

            model = {
                "condition": condition,
                "label": label,
                "temperature_c": temp_c,
                "precipitation_mm": precip,
                "cloud_cover_pct": clouds,
                "weather_code": code,
                "source": "OPEN_METEO",
                "utc_offset_seconds": utc_offset_sec,
                "timezone": tz_name
            }

            obs = get_nws_observation(lat, lon)
            if obs:
                obs["utc_offset_seconds"] = utc_offset_sec
                obs["timezone"] = tz_name
                obs["model_condition"] = model["condition"]
                obs["model_cloud_cover_pct"] = model["cloud_cover_pct"]
                if obs["condition"] != model["condition"]:
                    print(f"[Weather] NWS {obs['station']} says {obs['condition']}, "
                          f"Open-Meteo model says {model['condition']}. Using observation.")
                return obs
            return model
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


def _shadow_length_clause(solar_elevation: float) -> str:
    """Shadow length as an explicit multiple of object height: L = h / tan(elev)."""
    if solar_elevation <= 0.5:
        return "Cast shadows are effectively infinite; render them running off the edge of the frame."
    ratio = 1.0 / math.tan(math.radians(solar_elevation))
    if ratio > 12.0:
        return ("Cast shadows are more than twelve times the height of the object casting them: "
                "extremely long, running off the edge of the frame.")
    return (f"Every cast shadow is {ratio:.1f} times as long as the height of the object casting it. "
            f"A 100 m tower casts a {ratio * 100:.0f} m shadow. Apply this ratio to every object in the scene.")


def _classify_relative_light_vector(solar_azimuth: float, camera_heading: float) -> Dict[str, str]:
    """
    Screen-space lighting derived from geometry rather than a lookup table.

    rel is the sun's bearing measured from the camera's viewing direction.
      depth   = cos(rel):  > 0 sun AHEAD of the camera  -> scene is backlit
                           < 0 sun BEHIND the camera    -> scene is front-lit
      lateral = sin(rel):  > 0 sun to camera-RIGHT, < 0 sun to camera-LEFT

    Shadows are cast directly away from the sun, so the shadow vector is the
    negation of the sun vector:
      shadow_fwd = -depth    > 0 shadows recede from the camera (up the frame)
      shadow_lat = -lateral  > 0 shadows fall to the RIGHT
    """
    rel = (solar_azimuth - camera_heading) % 360.0
    r = math.radians(rel)
    depth = math.cos(r)
    lateral = math.sin(r)
    shadow_fwd = -depth
    shadow_lat = -lateral

    AX = 0.38   # beyond this the axis dominates the description

    # ---- where the sun sits in frame ----
    if depth > AX and abs(lateral) <= AX:
        screen_sun = "directly ahead of the camera in the centre background"
    elif depth < -AX and abs(lateral) <= AX:
        screen_sun = "behind the camera, out of frame"
    elif abs(depth) <= AX and lateral > 0:
        screen_sun = "at the RIGHT edge of the frame, roughly level with the view direction"
    elif abs(depth) <= AX and lateral < 0:
        screen_sun = "at the LEFT edge of the frame, roughly level with the view direction"
    elif depth > 0 and lateral > 0:
        screen_sun = "ahead and to the RIGHT, in the upper-right background"
    elif depth > 0 and lateral < 0:
        screen_sun = "ahead and to the LEFT, in the upper-left background"
    elif depth < 0 and lateral > 0:
        screen_sun = "behind the camera and to the RIGHT, out of frame"
    else:
        screen_sun = "behind the camera and to the LEFT, out of frame"

    # ---- which surfaces are lit ----
    parts = []
    if depth < -AX:
        parts.append("all camera-facing facades are in full direct sunlight")
    elif depth > AX:
        parts.append("all camera-facing facades are in shadow, reading as backlit silhouettes with a bright rim along their sunward edges")
    else:
        parts.append("camera-facing facades receive grazing light and read as half-lit")

    if lateral > AX:
        parts.append("right-facing walls are brightly lit and left-facing walls are in deep shadow")
    elif lateral < -AX:
        parts.append("left-facing walls are brightly lit and right-facing walls are in deep shadow")
    else:
        parts.append("left- and right-facing walls are lit roughly equally")
    facade_lighting = "; ".join(parts)

    # ---- where shadows go ----
    if shadow_fwd > AX and abs(shadow_lat) <= AX:
        traj = "cast shadows recede directly away from the camera, up the frame and behind their objects"
    elif shadow_fwd < -AX and abs(shadow_lat) <= AX:
        traj = "cast shadows project directly toward the camera, down the frame"
    elif abs(shadow_fwd) <= AX and shadow_lat > 0:
        traj = "long lateral cast shadows run horizontally across the ground to the RIGHT"
    elif abs(shadow_fwd) <= AX and shadow_lat < 0:
        traj = "long lateral cast shadows run horizontally across the ground to the LEFT"
    elif shadow_fwd > 0 and shadow_lat > 0:
        traj = "cast shadows project diagonally away from the camera toward the upper-RIGHT"
    elif shadow_fwd > 0 and shadow_lat < 0:
        traj = "cast shadows project diagonally away from the camera toward the upper-LEFT"
    elif shadow_fwd < 0 and shadow_lat > 0:
        traj = "cast shadows project diagonally toward the camera and to the lower-RIGHT"
    else:
        traj = "cast shadows project diagonally toward the camera and to the lower-LEFT"

    # ---- summary ----
    if depth < -AX:
        summ = "front-lighting from behind the observer"
    elif depth > AX:
        summ = "backlighting from ahead of the observer"
    elif lateral > 0:
        summ = "hard raking side-light from camera-right"
    else:
        summ = "hard raking side-light from camera-left"

    if abs(shadow_lat) > 0.15:
        side = "RIGHT" if shadow_lat > 0 else "LEFT"
        lateral_emphasis = (f" Every shadow must be angled toward the {side}; a shadow running straight "
                            f"up or straight down the frame is wrong.")
    else:
        lateral_emphasis = ""

    erasure = (
        "MANDATORY: Erase every cast shadow present in the reference plate before relighting. "
        "Render all previously shadowed ground and facades as if that shadow never existed, then "
        f"cast entirely new shadows so that {traj}.{lateral_emphasis} "
        "Do not retain, tint, or reuse any shadow from the reference plate."
    )

    return {
        "summary": summ,
        "screen_sun": screen_sun,
        "facade_lighting": facade_lighting,
        "shadow_trajectory": traj,
        "shadow_erasure": erasure
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
    tz_name = weather_info.get("timezone")

    # 2. Resolve DateTime
    if date_str and time_of_day_hours is not None:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            h = int(time_of_day_hours)
            m = int((time_of_day_hours - h) * 60)
            s = int((((time_of_day_hours - h) * 60) - m) * 60)
            local_dt = datetime(d.year, d.month, d.day, h, m, s)

            # Open-Meteo's utc_offset_seconds is the offset RIGHT NOW, not on the
            # target date. Using it for a date in a different DST regime shifts the
            # sun by an hour: a December scene computed with a September BST offset
            # lands an hour early. Resolve the offset for the target date itself.
            dt = None
            if tz_name and ZoneInfo is not None:
                try:
                    aware_local = local_dt.replace(tzinfo=ZoneInfo(tz_name))
                    dt = aware_local.astimezone(timezone.utc)
                    resolved = aware_local.utcoffset().total_seconds()
                    if abs(resolved - utc_offset_sec) > 1:
                        print(f"[Time] {tz_name} offset on {date_str} is "
                              f"{resolved/3600:+.0f}h, not today's {utc_offset_sec/3600:+.0f}h. "
                              f"Using the target date's offset.")
                except Exception as tzerr:
                    print(f"[Time Warning] zoneinfo '{tz_name}' unavailable ({tzerr}); "
                          f"falling back to current offset. On Windows: pip install tzdata")
            if dt is None:
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

    # Conditions where there is no direct sun and no hard cast shadows.
    DIFFUSE = ("OVERCAST", "FOG", "RAIN", "SNOW")

    # A weather button other than AUTO is a deliberate override and always wins.
    # AUTO means live conditions; with a custom date set, live conditions belong
    # to a different day, so they only apply when the date is today's.
    is_explicit_weather = (weather_mode.upper() != "AUTO")
    is_custom_datetime = (date_str is not None)
    use_diffuse = active_weather in DIFFUSE and (is_explicit_weather or not is_custom_datetime)

    if solar_elevation <= 0.0:
        is_blue_hour = solar_elevation > -6.0
        twilight_type = "Blue Hour Civil Twilight" if is_blue_hour else "Nocturnal Night Scene"
        natural_desc = f"Calibrated {cct}K {twilight_type} (Elevation {solar_elevation:.1f}°). Weather: {active_weather}."
        prompt_directive = (
            f"LIGHTING: {cct}K {twilight_type}. Sun elevation {solar_elevation:.1f}°. "
            f"Zero direct sunlight. Extinguish daytime cast shadows. Diffuse indigo ambient skylight with soft contact occlusion."
        )
    elif use_diffuse:
        weather_diffuse_directives = {
            "OVERCAST": (
                "Fully overcast. The sun is not visible and casts no shadow anywhere in the scene. "
                "Soft omnidirectional 6500K skylight from a flat pale grey cloud deck. "
                "Zero directional cast shadows; render only ambient contact occlusion under cornices, sills, and ledges. "
                "Low overall contrast, muted colour saturation, no warm highlights."
            ),
            "FOG": (
                "Dense fog. The sun is not visible and casts no shadow anywhere in the scene. "
                "Light-scattering mist thickens with distance: near objects hold detail, mid-distance objects lose contrast and "
                "edge definition, far objects fade toward a flat pale grey. No horizon line. "
                "Damp, desaturated surfaces. Zero directional shadows and zero warm highlights."
            ),
            "RAIN": (
                "Active rainfall under a dark overcast sky. The sun is not visible and casts no shadow anywhere in the scene. "
                "Soaked, mirror-reflective paving and roadway with standing water and visible surface ripples; "
                "darkened, saturated stone and brickwork; water streaking down vertical surfaces and running at kerbs. "
                "Low contrast, cool grey ambient light, zero directional shadows."
            ),
            "SNOW": (
                "Snowfall under a heavy overcast sky. The sun is not visible and casts no shadow anywhere in the scene. "
                "Snow lying evenly on every horizontal surface: roofs, ledges, sills, steps, kerbs, branches, and ground. "
                "Flat bright ambient light bouncing off the snow, very low contrast, cold blue-grey shadowless tone."
            )
        }
        diffuse_rule = weather_diffuse_directives.get(active_weather, weather_diffuse_directives["OVERCAST"])
        natural_desc = f"Calibrated {cct}K diffuse daylight under {active_weather} conditions (Sun Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°)."
        prompt_directive = (
            f"ATMOSPHERIC LIGHTING ({active_weather}):\n"
            f"{diffuse_rule}\n"
            f"- SHADOW OVERWRITE RULE: MANDATORY: Erase every cast shadow present in the reference plate. "
            f"The reference plate was captured in direct sun; this scene has none. Render all previously shadowed "
            f"ground and facades as evenly lit under {active_weather.lower()} conditions, with no directional shadow anywhere."
        )
    else:
        # Solar Ephemeris is authoritative for custom date/time and sunny/clear conditions
        rel_map = _classify_relative_light_vector(solar_azimuth, camera_heading)
        weather_text = {
            "SUNNY": "Crisp clear sky with direct solar exposure.",
            "PARTLY": "Broken cloud with direct solar exposure; scattered soft cloud shadows across the ground.",
            "RAIN": "Wet, mirror-reflective paving and subtle standing water under bright sky.",
            "SNOW": "Snow lying on horizontal ledges, roofs, and pavement edges.",
            "FOG": "Thin haze softening distant contrast, sun still breaking through.",
        }.get(active_weather, "Crisp clear sky with direct solar exposure.")
        natural_desc = (
            f"Calibrated {cct}K {epoch_desc} ({rel_map['summary']}, Sun Azimuth {solar_azimuth:.1f}°, "
            f"Elevation {solar_elevation:.1f}°). {weather_text}"
        )
        prompt_directive = (
            f"SOLAR RELIGHTING DIRECTIVE ({cct}K {epoch_desc}):\n"
            f"- SUN POSITION IN SCREEN SPACE: Sun is {rel_map['screen_sun']} (True Azimuth {solar_azimuth:.1f}°, Elevation {solar_elevation:.1f}°).\n"
            f"- FACADE ILLUMINATION: {rel_map['facade_lighting']}.\n"
            f"- CAST SHADOW DIRECTION: {rel_map['shadow_trajectory']}.\n"
            f"- CAST SHADOW LENGTH: {_shadow_length_clause(solar_elevation)}\n"
            f"- SHADOW OVERWRITE RULE: {rel_map['shadow_erasure']}\n"
            f"- WEATHER/SKY: {weather_text}"
        )

    is_diffuse_state = use_diffuse

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