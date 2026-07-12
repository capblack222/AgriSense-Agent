import json
from agrisense.backend import rules


def base_hourly(temp=25, precip=0.0, humidity=50):
    return {
        "temperature_2m": [temp],
        "precipitation": [precip],
        "relative_humidity_2m": [humidity],
    }


def test_missing_hourly_returns_error():
    out = rules.decide_actions({}, "Wheat")
    assert "actions" in out and "explanations" in out
    assert len(out["actions"]) == 1
    assert "Could not fetch weather data" in out["actions"][0]


def test_irrigation_for_very_high_water_need():
    weather = {"hourly": base_hourly(temp=20, precip=0.0, humidity=40)}
    out = rules.decide_actions(weather, "Rice")
    # Rice is configured as very-high water_need → first irrigation recommendation
    assert any("Irrigate generously" in a for a in out["actions"]) 
    # Explanation should mention precipitation and the need to irrigate
    assert any("Precipitation forecast" in e for e in out["explanations"]) 


def test_heat_alert_triggered():
    # Use Tomato: heat_threshold 30 → with Vegetative (0 delta) threshold 30
    weather = {"hourly": base_hourly(temp=35, precip=5.0, humidity=40)}
    out = rules.decide_actions(weather, "Tomato", stage="Vegetative")
    assert any("Heat alert" in a for a in out["actions"]) 
    # Also since precip=5, irrigation should recommend skipping
    assert any("Skip irrigation" in a for a in out["actions"]) 


def test_humidity_alert_triggered():
    # Wheat humidity risk 75; set humidity above it
    weather = {"hourly": base_hourly(temp=20, precip=0.0, humidity=80)}
    out = rules.decide_actions(weather, "Wheat")
    assert any("High humidity" in a for a in out["actions"]) 


def test_stage_note_is_prepended():
    weather = {"hourly": base_hourly(temp=20, precip=0.0, humidity=40)}
    out = rules.decide_actions(weather, "Wheat", stage="Seedling")
    # First action should be the Seedling stage note
    assert out["actions"][0].startswith("[Seedling Stage]")
    assert "Damping-off" in out["actions"][0]
