import requests
import agrisense.backend.weather as weather


class FakeResponse:
    def __init__(self, payload=None, raise_exc=None):
        self._payload = payload
        self._raise_exc = raise_exc

    def json(self):
        if self._raise_exc:
            raise self._raise_exc
        return self._payload


def test_geocode_request_failure(monkeypatch):
    def fake_get(*args, **kwargs):
        raise requests.RequestException("network down")

    # monkeypatch.setattr(weather, "requests", weather.requests)
    monkeypatch.setattr(weather, "requests", __import__("requests"))
    monkeypatch.setattr(weather.requests, "get", fake_get)

    out = weather.fetch_weather("Nowhere")
    assert "error" in out and "Geocoding request failed" in out["error"]


def test_location_not_found(monkeypatch):
    geo_payload = {"results": []}

    def fake_get_geo(*args, **kwargs):
        return FakeResponse(geo_payload)

    monkeypatch.setattr(weather.requests, "get", fake_get_geo)

    out = weather.fetch_weather("Atlantis")
    assert "error" in out
    assert "not found" in out["error"]


def test_successful_fetch(monkeypatch):
    geo_payload = {"results": [{"latitude": 10.0, "longitude": 20.0, "name": "MockCity"}]}
    hourly = {
        "temperature_2m": [21.5],
        "precipitation": [0.0],
        "relative_humidity_2m": [55.0],
    }
    weather_payload = {"hourly": hourly}

    def fake_get(url, params=None, timeout=None):
        if "geocoding-api.open-meteo" in url:
            return FakeResponse(geo_payload)
        else:
            return FakeResponse(weather_payload)

    monkeypatch.setattr(weather.requests, "get", fake_get)

    out = weather.fetch_weather("MockCity")
    assert "hourly" in out
    assert out["summary"]["temp"] == 21.5
    assert out["summary"]["precip"] == 0.0
    assert out["summary"]["humidity"] == 55.0
    assert out["location_resolved"] == "MockCity"
