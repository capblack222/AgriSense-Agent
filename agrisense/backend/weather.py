"""
weather.py - Open-Meteo API wrapper.

Single responsibility: given a city name, return structured weather data.
No business logic lives here - that's rules.py's job.

Uses httpx.AsyncClient so the weather fetch is non-blocking inside FastAPI's
async event loop. The previous sync `requests` implementation blocked the
entire event loop for ~1-2 s per call.

If you ever swap weather providers, only this file changes.
"""

import httpx

# Open-Meteo is free and requires no API key
_GEO_URL     = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


async def _http_get(url: str, params: dict, timeout: int = 10) -> dict:
    """
    Async HTTP GET returning parsed JSON.
    Extracted as a standalone coroutine so tests can monkeypatch it cleanly
    without needing to mock httpx internals.
    Raises httpx.RequestError on network failures.
    """
    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=timeout)
        return r.json()


async def fetch_weather(location: str) -> dict:
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
        geo_data = await _http_get(_GEO_URL, {"name": location, "count": 1})
    except httpx.RequestError as e:
        return {"error": f"Geocoding request failed: {e}"}

    if "results" not in geo_data or not geo_data["results"]:
        return {"error": f"Location '{location}' not found. Try a nearby city name."}

    result   = geo_data["results"][0]
    lat      = result["latitude"]
    lon      = result["longitude"]
    resolved = result.get("name", location)   # the name Open-Meteo matched

    # ── Step 2: Fetch hourly forecast ────────────────────────────────────────
    try:
        weather_data = await _http_get(
            _WEATHER_URL,
            {
                "latitude":  lat,
                "longitude": lon,
                "hourly":    "temperature_2m,precipitation,relative_humidity_2m",
            },
        )
    except httpx.RequestError as e:
        return {"error": f"Weather request failed: {e}"}

    if "hourly" not in weather_data:
        return {"error": "Weather API returned an unexpected response. Please try again."}

    hourly = weather_data["hourly"]

    # ── Step 3: Extract a clean summary for the current hour (index 0) ───────
    # Index 0 = the first hour of the forecast window (effectively "now").
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
