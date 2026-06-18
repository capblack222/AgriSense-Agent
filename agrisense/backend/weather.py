"""
weather.py — Open-Meteo API wrapper.

Single responsibility: given a city name, return structured weather data.
No business logic lives here — that's rules.py's job.

If you ever swap weather providers, only this file changes.
"""

import requests

# Open-Meteo is free and requires no API key
_GEO_URL     = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_weather(location: str) -> dict:
    """
    Fetch the current-hour weather for a given city.

    Args:
        location: city or region name (e.g., "Mumbai", "Ranchi")

    Returns:
        On success:
            {
                "hourly":  { raw Open-Meteo hourly block },
                "summary": { "temp": float, "precip": float, "humidity": float },
                "location_resolved": str   ← the name Open-Meteo matched
            }
        On failure:
            { "error": str }
    """

    # ── Step 1: Geocode the city name to lat/lon ─────────────────────────────
    try:
        geo_res = requests.get(
            _GEO_URL,
            params={"name": location, "count": 1},
            timeout=10,
        ).json()
    except requests.RequestException as e:
        return {"error": f"Geocoding request failed: {e}"}

    if "results" not in geo_res or not geo_res["results"]:
        return {"error": f"Location '{location}' not found. Try a nearby city name."}

    result   = geo_res["results"][0]
    lat      = result["latitude"]
    lon      = result["longitude"]
    resolved = result.get("name", location)   # the name Open-Meteo matched

    # ── Step 2: Fetch hourly forecast ────────────────────────────────────────
    try:
        weather_res = requests.get(
            _WEATHER_URL,
            params={
                "latitude":  lat,
                "longitude": lon,
                "hourly":    "temperature_2m,precipitation,relative_humidity_2m",
            },
            timeout=10,
        ).json()
    except requests.RequestException as e:
        return {"error": f"Weather request failed: {e}"}

    if "hourly" not in weather_res:
        return {"error": "Weather API returned an unexpected response. Please try again."}

    hourly = weather_res["hourly"]

    # ── Step 3: Extract a clean summary for the current hour (index 0) ───────
    # Index 0 = the first hour of the forecast window (effectively "now").
    # We expose this as a flat dict so callers don't need to know the
    # Open-Meteo response structure.
    summary = {
        "temp":     hourly["temperature_2m"][0],
        "precip":   hourly["precipitation"][0],
        "humidity": hourly["relative_humidity_2m"][0],
    }

    return {
        "hourly":             hourly,
        "summary":            summary,
        "location_resolved":  resolved,
    }
