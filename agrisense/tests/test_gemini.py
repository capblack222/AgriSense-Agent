import json
import pytest
import agrisense.backend.gemini as gemini


# ---------------------------------------------------------------------------
# Helper: async mock for _call_gemini
# ---------------------------------------------------------------------------

def _async_return(value):
    """Wrap a plain value in an async function for monkeypatching async callables."""
    async def _inner(prompt):
        return value
    return _inner


# ---------------------------------------------------------------------------
# validate_crop tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_crop_no_api_key_fails_open(monkeypatch):
    """Without an API key validate_crop should fail open (is_valid=True)."""
    monkeypatch.setattr(gemini, "_API_KEY", None)
    out = await gemini.validate_crop("Pizza")
    assert out["is_valid"] is True
    assert out["message"] == ""


@pytest.mark.asyncio
async def test_validate_crop_invalid_crop(monkeypatch):
    """Gemini says not a crop → is_valid=False with a non-empty message."""
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")
    fake = {"is_valid": False, "message": "Pizza isn't a recognised crop."}
    monkeypatch.setattr(gemini, "_call_gemini", _async_return(json.dumps(fake)))

    out = await gemini.validate_crop("Pizza")
    assert out["is_valid"] is False
    assert "Pizza" in out["message"]


@pytest.mark.asyncio
async def test_validate_crop_valid_crop(monkeypatch):
    """Gemini says it's a real crop → is_valid=True, empty message."""
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")
    fake = {"is_valid": True, "message": ""}
    monkeypatch.setattr(gemini, "_call_gemini", _async_return(json.dumps(fake)))

    out = await gemini.validate_crop("Wheat")
    assert out["is_valid"] is True
    assert out["message"] == ""


@pytest.mark.asyncio
async def test_validate_crop_gemini_failure_fails_open(monkeypatch):
    """If _call_gemini returns None (network error etc.), fail open."""
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")
    monkeypatch.setattr(gemini, "_call_gemini", _async_return(None))

    out = await gemini.validate_crop("Wheat")
    assert out["is_valid"] is True


# ---------------------------------------------------------------------------
# decide_and_advise tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_api_key_returns_none(monkeypatch):
    """Clear API key to emulate missing configuration."""
    monkeypatch.setattr(gemini, "_API_KEY", None)
    out = await gemini.decide_and_advise(
        "Wheat", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50}
    )
    assert out is None


@pytest.mark.asyncio
async def test_invalid_crop_response(monkeypatch):
    """Provide a fake API key so the function proceeds."""
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")

    fake = {
        "is_valid_crop": False,
        "invalid_crop_message": "I don't recognise that crop."
    }
    monkeypatch.setattr(gemini, "_call_gemini", _async_return(json.dumps(fake)))

    out = await gemini.decide_and_advise(
        "Pizza", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50}
    )
    assert isinstance(out, dict)
    assert out.get("_invalid_crop") is True
    assert "recognise" in out.get("message") or "recognize" in out.get("message")


@pytest.mark.asyncio
async def test_valid_response_shape(monkeypatch):
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")

    fake = {
        "is_valid_crop": True,
        "invalid_crop_message": "",
        "actions": ["Do X", "Do Y"],
        "explanations": ["Because A", "Because B"],
        "summary": "A short summary."
    }
    monkeypatch.setattr(gemini, "_call_gemini", _async_return(json.dumps(fake)))

    out = await gemini.decide_and_advise(
        "Wheat", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50}
    )
    assert out is not None
    assert out.get("actions") == fake["actions"]
    assert out.get("explanations") == fake["explanations"]
    assert out.get("summary") == fake["summary"]
