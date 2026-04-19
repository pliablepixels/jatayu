#!/usr/bin/env python3
"""weather.py — weather plugin for Jatayu.

Usage:
  python3 plugins/weather/weather.py --location "<address or place>" [--days 3]

Two free, keyless backends:
  - Nominatim (OpenStreetMap) for geocoding. Handles full postal addresses,
    city names, neighborhoods, landmarks. Requires a User-Agent header.
  - Open-Meteo for the forecast. Takes lat/lon, returns current conditions
    and up to 7 days of hourly/daily data.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "jatayu-weather/1.0 (https://github.com/pliablepixels/jatayu)"
TIMEOUT_S = 10

# WMO weather interpretation codes, trimmed to what's useful in a short reply.
# https://open-meteo.com/en/docs
WMO = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "heavy rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}


def _get_json(url: str, headers: dict | None = None) -> object:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _nominatim(q: str) -> list[dict]:
    params = urllib.parse.urlencode({
        "q": q, "format": "jsonv2", "limit": 1, "addressdetails": 0,
    })
    data = _get_json(f"{NOMINATIM_URL}?{params}", {"User-Agent": USER_AGENT})
    return data if isinstance(data, list) else []


def geocode(location: str) -> tuple[float, float, str] | None:
    """Return (lat, lon, display_name) from Nominatim, or None.

    Tries the full query first. If that misses — common for residential
    addresses not indexed in OSM — drops leading comma-separated segments
    one at a time (street number, street, unit) until we find *something*.
    Worst case: we match the city at the end.
    """
    parts = [p.strip() for p in location.split(",")]
    for i in range(len(parts)):
        q = ", ".join(parts[i:]).strip()
        if not q:
            continue
        try:
            hits = _nominatim(q)
        except Exception:
            continue
        if hits:
            r = hits[0]
            return float(r["lat"]), float(r["lon"]), r.get("display_name") or q
    return None


def fetch_forecast(lat: float, lon: float, days: int) -> dict:
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
        "forecast_days": max(1, min(int(days), 7)),
    })
    return _get_json(f"{FORECAST_URL}?{params}")


def _wmo(code: int | None) -> str:
    if code is None:
        return "unknown"
    return WMO.get(int(code), f"code {code}")


def _short_name(display_name: str) -> str:
    """Nominatim's display_name is long ('123 Main St, Town, County, State, …,
    Country, Postcode'). Keep the first 3 segments for a readable header."""
    parts = [p.strip() for p in (display_name or "").split(",") if p.strip()]
    return ", ".join(parts[:3]) if parts else (display_name or "")


def format_reply(name: str, data: dict) -> str:
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    lines: list[str] = [f"Weather — {_short_name(name)}"]

    if current:
        temp = current.get("temperature_2m")
        feels = current.get("apparent_temperature")
        cond = _wmo(current.get("weather_code"))
        wind = current.get("wind_speed_10m")
        humidity = current.get("relative_humidity_2m")
        bits = [f"{temp:.0f}°F" if isinstance(temp, (int, float)) else None]
        if isinstance(feels, (int, float)) and abs((feels or 0) - (temp or 0)) >= 3:
            bits.append(f"feels {feels:.0f}°F")
        bits.append(cond)
        if isinstance(wind, (int, float)):
            bits.append(f"wind {wind:.0f} mph")
        if isinstance(humidity, (int, float)):
            bits.append(f"humidity {humidity:.0f}%")
        lines.append("Now: " + ", ".join(b for b in bits if b))

    dates = daily.get("time") or []
    codes = daily.get("weather_code") or []
    highs = daily.get("temperature_2m_max") or []
    lows = daily.get("temperature_2m_min") or []
    pops = daily.get("precipitation_probability_max") or []
    for i, date in enumerate(dates):
        parts = [date]
        if i < len(highs) and i < len(lows):
            parts.append(f"{lows[i]:.0f}–{highs[i]:.0f}°F")
        if i < len(codes):
            parts.append(_wmo(codes[i]))
        if i < len(pops) and pops[i] is not None and pops[i] > 0:
            parts.append(f"{pops[i]:.0f}% precip")
        lines.append("  " + ", ".join(parts))

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Current + short-range forecast (Nominatim + Open-Meteo)")
    ap.add_argument("--location", required=True, help="Address, place name, neighborhood, etc.")
    ap.add_argument("--days", default="3", help="Forecast days (1–7, default 3)")
    args = ap.parse_args()

    try:
        geo = geocode(args.location)
    except Exception as e:
        print(f"Error geocoding {args.location!r}: {e}", file=sys.stderr)
        return 1
    if geo is None:
        print(f"Location not found: {args.location!r}", file=sys.stderr)
        return 1
    lat, lon, name = geo

    try:
        data = fetch_forecast(lat, lon, int(args.days))
    except Exception as e:
        print(f"Error fetching forecast: {e}", file=sys.stderr)
        return 1

    print(format_reply(name, data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
