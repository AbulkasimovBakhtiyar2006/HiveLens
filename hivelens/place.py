"""Where a farm is and what the weather is doing there.

Coordinates come from a Google Maps link (or plain "lat, lon"), otherwise from the
place name through the Open-Meteo geocoder. Weather comes from Open-Meteo too;
both are free and need no API key.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request

USER_AGENT = "HiveLens/0.1 (apiary dashboard)"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_TTL_S = 15 * 60

_cache: dict[tuple[float, float], tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _get_json(url: str, timeout: float = 8.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _final_url(url: str, timeout: float = 8.0) -> str:
    """Follows a short link (maps.app.goo.gl) to the full Google Maps URL."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.geturl()


def _valid(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180


_COORD_PATTERNS = [
    r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)",            # exact pin in /place/ links
    r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)",                 # map centre
    r"[?&](?:q|query|ll|center|destination)=(-?\d+(?:\.\d+)?)(?:,|%2C)\s*(-?\d+(?:\.\d+)?)",
    r"^\s*(-?\d{1,2}(?:\.\d+)?)\s*[, ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$",  # plain "43.30, 77.24"
]


def parse_coordinates(text: str) -> tuple[float, float] | None:
    """Latitude and longitude from a Google Maps URL or a "lat, lon" string."""
    text = urllib.parse.unquote(text or "")
    for pattern in _COORD_PATTERNS:
        m = re.search(pattern, text)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            if _valid(lat, lon):
                return lat, lon
    return None


def is_maps_link(text: str) -> bool:
    host = urllib.parse.urlsplit(text.strip()).netloc.lower()
    return host.endswith(("google.com", "goo.gl", "maps.app.goo.gl", "google.kz", "google.ru")) or "maps" in host


def geocode(text: str) -> dict | None:
    """Best match for a place name. Falls back to shorter forms ("Talgar Mountain, sector A" → "Talgar")."""
    text = (text or "").strip()
    if not text:
        return None
    tries: list[str] = []
    for part in [text, *[p.strip() for p in text.split(",")]]:
        words = part.split()
        tries += [" ".join(words[:n]) for n in range(len(words), 0, -1)]
    seen = set()
    for name in tries:
        if len(name) < 2 or name.lower() in seen:
            continue
        seen.add(name.lower())
        data = _get_json(f"{GEOCODE_URL}?{urllib.parse.urlencode({'name': name, 'count': 1, 'format': 'json'})}")
        hit = (data.get("results") or [None])[0]
        if hit:
            label = ", ".join(x for x in (hit.get("name"), hit.get("admin1"), hit.get("country")) if x)
            return {"lat": hit["latitude"], "lon": hit["longitude"], "place": label,
                    "country_code": hit.get("country_code"), "elevation_m": hit.get("elevation")}
    return None


def resolve(location: str, maps: str) -> dict | None:
    """Coordinates for a farm: the map link wins, then the place name. None if neither works."""
    maps = (maps or "").strip()
    if maps:
        coords = parse_coordinates(maps)
        if coords is None and is_maps_link(maps):
            coords = parse_coordinates(_final_url(maps))
        if coords:
            near = _reverse_label(*coords)
            return {"lat": round(coords[0], 5), "lon": round(coords[1], 5), **near}
    hit = geocode(location)
    return {**hit, "lat": round(hit["lat"], 5), "lon": round(hit["lon"], 5)} if hit else None


def _reverse_label(lat: float, lon: float) -> dict:
    """Open-Meteo has no reverse geocoder; the timezone/elevation from the forecast is enough context."""
    try:
        data = _get_json(f"{FORECAST_URL}?latitude={lat}&longitude={lon}&current=temperature_2m&timezone=auto")
        return {"place": f"{lat:.4f}, {lon:.4f}", "timezone": data.get("timezone"), "elevation_m": data.get("elevation")}
    except Exception:
        return {"place": f"{lat:.4f}, {lon:.4f}"}


# ── Weather ─────────────────────────────────────────────────────────────

# WMO weather codes → (description, scene used by the dashboard illustration)
WMO = {
    0: ("Clear", "clear"), 1: ("Mostly clear", "clear"), 2: ("Partly cloudy", "partly"), 3: ("Overcast", "cloudy"),
    45: ("Fog", "fog"), 48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"), 53: ("Drizzle", "drizzle"), 55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"), 57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"), 63: ("Rain", "rain"), 65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"), 67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"), 73: ("Snow", "snow"), 75: ("Heavy snow", "snow"), 77: ("Snow grains", "snow"),
    80: ("Rain showers", "rain"), 81: ("Rain showers", "rain"), 82: ("Violent rain showers", "rain"),
    85: ("Snow showers", "snow"), 86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "thunder"), 96: ("Thunderstorm with hail", "thunder"), 99: ("Thunderstorm with hail", "thunder"),
}

# Foraging thresholds used across beekeeping guides: honey bees rarely fly below about
# 10 °C, foraging is reduced below 13 °C and in wind above about 6–7 m/s (24 km/h).
FLIGHT_MIN_C = 10.0
FLIGHT_GOOD_C = 13.0
WIND_LIMITED_MS = 6.5
WIND_NO_FLIGHT_MS = 10.0


def describe(code: int | None) -> tuple[str, str]:
    return WMO.get(int(code), ("Unknown", "cloudy")) if code is not None else ("Unknown", "cloudy")


def bee_flight(temp_c: float | None, wind_ms: float | None, precip_mm: float | None, code: int | None,
               is_day: bool = True) -> dict:
    """Whether the weather lets bees forage: good / limited / none, with the reason."""
    scene = describe(code)[1]
    if not is_day:
        return {"level": "none", "reason": "Night: foragers stay in the hive."}
    if (precip_mm or 0) >= 0.2 or scene in ("rain", "drizzle", "snow", "thunder"):
        return {"level": "none", "reason": "Rain or snow keeps bees in the hive."}
    if temp_c is not None and temp_c < FLIGHT_MIN_C:
        return {"level": "none", "reason": f"Below {FLIGHT_MIN_C:.0f} °C bees stay in the cluster."}
    if wind_ms is not None and wind_ms >= WIND_NO_FLIGHT_MS:
        return {"level": "none", "reason": f"Wind of {wind_ms:.0f} m/s is too strong to fly."}
    if temp_c is not None and temp_c < FLIGHT_GOOD_C:
        return {"level": "limited", "reason": f"Cool: under {FLIGHT_GOOD_C:.0f} °C only short flights."}
    if wind_ms is not None and wind_ms >= WIND_LIMITED_MS:
        return {"level": "limited", "reason": "Windy: foraging is reduced."}
    if scene == "fog":
        return {"level": "limited", "reason": "Fog: poor visibility for foragers."}
    return {"level": "good", "reason": "Warm and calm enough for foraging."}


def forecast(lat: float, lon: float) -> dict:
    """Current conditions, the next 24 hours and 4 days, in °C, m/s and mm. Cached for 15 minutes."""
    key = (round(lat, 3), round(lon, 3))
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < WEATHER_TTL_S:
            return hit[1]
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 4, "wind_speed_unit": "ms",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,"
                   "cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,is_day",
        "hourly": "temperature_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m,"
                  "wind_direction_10m,wind_gusts_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                 "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max",
    }
    raw = _get_json(f"{FORECAST_URL}?{urllib.parse.urlencode(params)}")
    cur = raw.get("current", {})
    text, scene = describe(cur.get("weather_code"))
    current = {
        "time": cur.get("time"),
        "temp_c": cur.get("temperature_2m"),
        "feels_c": cur.get("apparent_temperature"),
        "humidity_pct": cur.get("relative_humidity_2m"),
        "precip_mm": cur.get("precipitation"),
        "cloud_pct": cur.get("cloud_cover"),
        "wind_ms": cur.get("wind_speed_10m"),
        "wind_dir_deg": cur.get("wind_direction_10m"),
        "gust_ms": cur.get("wind_gusts_10m"),
        "is_day": bool(cur.get("is_day", 1)),
        "code": cur.get("weather_code"),
        "text": text,
        "scene": scene,
    }
    current["flight"] = bee_flight(current["temp_c"], current["wind_ms"], current["precip_mm"], current["code"], current["is_day"])

    h = raw.get("hourly", {})
    times = h.get("time", [])
    start = next((i for i, t in enumerate(times) if t >= (cur.get("time") or "")[:13]), 0)
    hourly = []
    for i in range(start, min(start + 24, len(times))):
        code = h["weather_code"][i]
        text_h, scene_h = describe(code)
        row = {
            "time": times[i], "temp_c": h["temperature_2m"][i], "precip_prob": h["precipitation_probability"][i],
            "precip_mm": h["precipitation"][i], "wind_ms": h["wind_speed_10m"][i], "wind_dir_deg": h["wind_direction_10m"][i],
            "gust_ms": h["wind_gusts_10m"][i], "is_day": bool(h["is_day"][i]), "code": code, "text": text_h, "scene": scene_h,
        }
        row["flight"] = bee_flight(row["temp_c"], row["wind_ms"], row["precip_mm"], code, row["is_day"])
        hourly.append(row)

    d = raw.get("daily", {})
    daily = []
    for i, day in enumerate(d.get("time", [])):
        text_d, scene_d = describe(d["weather_code"][i])
        daily.append({
            "date": day, "code": d["weather_code"][i], "text": text_d, "scene": scene_d,
            "max_c": d["temperature_2m_max"][i], "min_c": d["temperature_2m_min"][i],
            "precip_mm": d["precipitation_sum"][i], "precip_prob": d["precipitation_probability_max"][i],
            "wind_ms": d["wind_speed_10m_max"][i], "gust_ms": d["wind_gusts_10m_max"][i],
        })

    result = {"timezone": raw.get("timezone"), "elevation_m": raw.get("elevation"),
              "current": current, "hourly": hourly, "daily": daily, "fetched": int(time.time())}
    with _cache_lock:
        _cache[key] = (time.time(), result)
    return result
