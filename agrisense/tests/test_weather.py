import httpx
import pytest
import agrisense.backend.weather as weather


# ---------------------------------------------------------------------------
# Async mock helpers
# ---------------------------------------------------------------------------

def _make_http_get(*responses):
    """
    Returns an async _http_get mock that yields each response dict in order.
    Raises httpx.RequestError if a response is an exception instance.
    """
    calls = list(responses)
    idx   = {"n": 0}

    async def fake_http_get(url, params, timeout=10):
        response = calls[idx["n"]]
        idx["n"] += 1
        if isinstance(response, Exception):
            raise response
        return response

    return fake_http_get


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geocode_request_failure(monkeypatch):
    """Network error on geocoding → error dict returned."""
    monkeypatch.setattr(
        weather, "_http_get",
        _make_http_get(httpx.RequestError("network down")),
    )
    out = await weather.fetch_weather("Nowhere")
    assert "error" in out
    assert "Geocoding request failed" in out["error"]


@pytest.mark.asyncio
async def test_location_not_found(monkeypatch):
    """Empty results from geocoder → error dict returned."""
    monkeypatch.setattr(
        weather, "_http_get",
        _make_http_get({"results": []}),
    )
    out = await weather.fetch_weather("Atlantis")
    assert "error" in out
    assert "not found" in out["error"]


@pytest.mark.asyncio
async def test_successful_fetch(monkeypatch):
    """Happy path: geocode + weather both succeed → full summary returned."""
    geo_payload = {
        "results": [{"latitude": 10.0, "longitude": 20.0, "name": "MockCity"}]
    }
    hourly = {
        "temperature_2m":        [21.5],
        "precipitation":         [0.0],
        "relative_humidity_2m":  [55.0],
    }
    weather_payload = {"hourly": hourly}

    monkeypatch.setattr(
        weather, "_http_get",
        _make_http_get(geo_payload, weather_payload),
    )

    out = await weather.fetch_weather("MockCity")
    assert "hourly" in out
    assert out["summary"]["temp"]     == 21.5
    assert out["summary"]["precip"]   == 0.0
    assert out["summary"]["humidity"] == 55.0
    assert out["location_resolved"]   == "MockCity"
