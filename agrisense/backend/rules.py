"""
rules.py - Crop-specific agronomy decision engine.

Pure functions only: no I/O, no database, no API calls.
Input:  weather dict, crop name, growth stage
Output: list of actions + explanations

This design makes the logic easy to test in isolation and easy to extend
(add a new crop → touch CROP_CONFIG only; add a new stage → touch STAGE_MODIFIERS only).
"""

# ---------------------------------------------------------------------------
# Crop configuration
# Each crop has three properties:
#   heat_threshold  - °C above which heat stress warnings are issued
#   humidity_risk   - % above which fungal/pest risk warnings are issued
#   water_need      - irrigation urgency when no rain is forecast
# ---------------------------------------------------------------------------
CROP_CONFIG: dict[str, dict] = {
    "Wheat": {
        "heat_threshold": 32,
        "humidity_risk": 75,
        "water_need": "moderate",
    },
    "Tomato": {
        "heat_threshold": 30,
        "humidity_risk": 70,
        "water_need": "high",
    },
    "Rice": {
        "heat_threshold": 34,
        "humidity_risk": 80,
        "water_need": "very-high",
    },
    "Maize": {
        "heat_threshold": 33,
        "humidity_risk": 70,
        "water_need": "moderate",
    },
    "Soybean": {
        "heat_threshold": 32,
        "humidity_risk": 72,
        "water_need": "moderate",
    },
    "Cotton": {
        "heat_threshold": 35,
        "humidity_risk": 65,
        "water_need": "moderate",
    },
    "Sugarcane": {
        "heat_threshold": 35,
        "humidity_risk": 80,
        "water_need": "very-high",
    },
}

# Fallback config for crops not in CROP_CONFIG
_DEFAULT_CROP_CONFIG = {
    "heat_threshold": 32,
    "humidity_risk": 75,
    "water_need": "moderate",
}

# ---------------------------------------------------------------------------
# Stage modifiers
# Each stage shifts the effective thresholds by a delta and adds a
# stage-specific note to the advice.
#
# Why deltas instead of absolute values?
#   → Adding a new crop doesn't require specifying thresholds for every stage.
#   → The relationship "Flowering is always 3°C more sensitive than Vegetative"
#     holds across all crops automatically.
# ---------------------------------------------------------------------------
STAGE_MODIFIERS: dict[str, dict] = {
    "Seedling": {
        "heat_threshold_delta": -2,   # seedlings are more sensitive to heat
        "humidity_risk_delta": -5,    # susceptible to fungal damping-off
        "stage_note": (
            "Seedling stage: keep soil consistently moist but avoid waterlogging. "
            "Damping-off (fungal disease) is the biggest risk at this stage."
        ),
    },
    "Vegetative": {
        "heat_threshold_delta": 0,
        "humidity_risk_delta": 0,
        "stage_note": None,           # no extra note needed at baseline stage
    },
    "Flowering": {
        "heat_threshold_delta": -3,   # heat during flowering causes pollen sterility
        "humidity_risk_delta": -5,    # fungal infection of flowers
        "stage_note": (
            "Flowering stage: this is the most critical period - heat and water stress "
            "now directly reduce yield. Prioritise irrigation and shade."
        ),
    },
    "Harvest": {
        "heat_threshold_delta": +2,   # mature crops tolerate heat better
        "humidity_risk_delta": -10,   # high humidity causes mold/rot in grain
        "stage_note": (
            "Harvest stage: reduce irrigation to allow the crop to dry. "
            "Watch humidity closely - mold can destroy a ready harvest quickly."
        ),
    },
}

_DEFAULT_STAGE_MOD = {"heat_threshold_delta": 0, "humidity_risk_delta": 0, "stage_note": None}


# ---------------------------------------------------------------------------
# Main decision function
# ---------------------------------------------------------------------------
def decide_actions(weather: dict, crop: str, stage: str | None = None) -> dict:
    """
    Apply agronomy rules to weather data and return recommended actions.

    Args:
        weather: dict returned by fetch_weather() - must contain 'hourly' key
        crop:    crop name (matched against CROP_CONFIG; falls back to defaults)
        stage:   growth stage string (matched against STAGE_MODIFIERS)

    Returns:
        {
            "actions":      [str, ...],   # short imperative recommendations
            "explanations": [str, ...],   # one-sentence reasoning per action
        }
    """
    actions: list[str] = []
    explanations: list[str] = []

    # ── Guard: API returned an error or missing hourly block ─────────────────
    if "hourly" not in weather:
        actions.append(
            "Could not fetch weather data. Please check the location name and try again."
        )
        explanations.append(
            "The weather API did not return hourly data, so rule-based evaluation "
            "could not be performed."
        )
        return {"actions": actions, "explanations": explanations}

    hourly = weather["hourly"]
    temp     = hourly["temperature_2m"][0]
    precip   = hourly["precipitation"][0]
    humidity = hourly["relative_humidity_2m"][0]

    # ── Load crop thresholds ─────────────────────────────────────────────────
    crop_cfg  = CROP_CONFIG.get(crop, _DEFAULT_CROP_CONFIG)
    heat_th   = crop_cfg["heat_threshold"]
    humid_th  = crop_cfg["humidity_risk"]
    water_need = crop_cfg["water_need"]

    # ── Apply stage modifiers ────────────────────────────────────────────────
    stage_key = stage.strip().title() if stage else "Vegetative"
    stage_mod = STAGE_MODIFIERS.get(stage_key, _DEFAULT_STAGE_MOD)

    heat_th  += stage_mod["heat_threshold_delta"]
    humid_th += stage_mod["humidity_risk_delta"]

    # Stage-specific contextual note (prepended so it reads first)
    if stage_mod["stage_note"]:
        actions.append(f"[{stage_key} Stage] {stage_mod['stage_note']}")
        explanations.append(f"Growth-stage context for {stage_key}.")

    # ── Rule 1: Irrigation ───────────────────────────────────────────────────
    if precip < 1:
        if water_need == "very-high":
            actions.append(
                "Irrigate generously today - no rain expected and this crop has very high water demand."
            )
            explanations.append(
                f"Precipitation forecast is {precip} mm. {crop} requires intensive irrigation "
                "at this stage to prevent yield loss."
            )
        elif water_need == "high":
            actions.append(
                "Irrigate today - no rain expected and this crop needs consistent moisture."
            )
            explanations.append(
                f"Precipitation forecast is {precip} mm. {crop} has high water demand "
                "and cannot tolerate dry periods."
            )
        else:
            actions.append(
                "Irrigate lightly - no significant rain expected."
            )
            explanations.append(
                f"Precipitation forecast is {precip} mm. {crop} has moderate water needs; "
                "a light irrigation is sufficient."
            )
    else:
        actions.append("Skip irrigation today - rain is expected. Conserve water.")
        explanations.append(
            f"Precipitation forecast is {precip} mm, which is sufficient. "
            "Irrigating on top of expected rain risks waterlogging."
        )

    # ── Rule 2: Heat stress ──────────────────────────────────────────────────
    if temp > heat_th:
        actions.append(
            f"Heat alert ({temp}°C): apply mulch or provide shade to reduce heat stress."
        )
        explanations.append(
            f"Temperature {temp}°C exceeds the effective threshold of {heat_th}°C for {crop} "
            f"at the {stage_key} stage. Prolonged exposure risks cellular damage."
        )
    else:
        actions.append(
            f"Temperature is safe ({temp}°C) - no heat protection needed today."
        )
        explanations.append(
            f"Temperature {temp}°C is within the safe range (threshold: {heat_th}°C) "
            f"for {crop} at the {stage_key} stage."
        )

    # ── Rule 3: Humidity / fungal risk ───────────────────────────────────────
    if humidity > humid_th:
        actions.append(
            f"High humidity ({humidity}%): fungal and pest risk is elevated - "
            "improve airflow and consider a preventive spray."
        )
        explanations.append(
            f"Humidity {humidity}% exceeds the risk threshold of {humid_th}% for {crop} "
            f"at the {stage_key} stage, creating favourable conditions for fungal disease."
        )
    else:
        actions.append(
            f"Humidity is normal ({humidity}%) - no fungal or pest alert today."
        )
        explanations.append(
            f"Humidity {humidity}% is below the risk threshold ({humid_th}%) "
            f"for {crop} at the {stage_key} stage."
        )

    return {"actions": actions, "explanations": explanations}
