import json
import agrisense.backend.gemini as gemini


def test_no_api_key_returns_none(monkeypatch):
    # Clear API key to emulate missing configuration
    monkeypatch.setattr(gemini, "_API_KEY", None)
    out = gemini.decide_and_advise("Wheat", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50})
    assert out is None


def test_invalid_crop_response(monkeypatch):
    # Provide a fake API key so the function proceeds
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")

    fake = {
        "is_valid_crop": False,
        "invalid_crop_message": "I don't recognise that crop."
    }

    monkeypatch.setattr(gemini, "_call_gemini", lambda prompt: json.dumps(fake))

    out = gemini.decide_and_advise("Pizza", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50})
    assert isinstance(out, dict)
    assert out.get("_invalid_crop") is True
    assert "recognise" in out.get("message") or "recognize" in out.get("message")


def test_valid_response_shape(monkeypatch):
    monkeypatch.setattr(gemini, "_API_KEY", "fake-key")

    fake = {
        "is_valid_crop": True,
        "invalid_crop_message": "",
        "actions": ["Do X", "Do Y"],
        "explanations": ["Because A", "Because B"],
        "summary": "A short summary."
    }

    monkeypatch.setattr(gemini, "_call_gemini", lambda prompt: json.dumps(fake))

    out = gemini.decide_and_advise("Wheat", "Nowhere", "Vegetative", {"temp": 20, "precip": 0, "humidity": 50})
    assert out is not None
    assert out.get("actions") == fake["actions"]
    assert out.get("explanations") == fake["explanations"]
    assert out.get("summary") == fake["summary"]
