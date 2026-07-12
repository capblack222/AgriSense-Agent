"""
gemini.py - Gemini LLM reasoning engine.

Uses the Gemini REST API directly via httpx — no google-generativeai SDK.

Reason: google-generativeai depends on protobuf's C extension
(google._upb._message) which crashes on Python 3.14 with:
    TypeError: Metaclasses with custom tp_new are not supported.
Calling the REST API directly eliminates that dependency entirely.
Same fix pattern as the passlib → bcrypt migration.

API docs: https://ai.google.dev/api/generate-content
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

_API_KEY   = os.getenv("GEMINI_API_KEY")
_MODEL     = "gemini-1.5-flash-8b"
_BASE_URL  = "https://generativelanguage.googleapis.com/v1beta/models"
_ENDPOINT  = f"{_BASE_URL}/{_MODEL}:generateContent"

# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------
_SCHEMA_RULES = """
Return ONLY valid JSON in this exact shape — no extra keys, no markdown fences:
{
  "is_valid_crop": true,
  "invalid_crop_message": "",
  "actions": [
    "short imperative recommendation",
    "..."
  ],
  "explanations": [
    "one-sentence reason for the recommendation above",
    "..."
  ],
  "summary": "A warm paragraph summarising today's plan for the farmer."
}

If the crop name is not a real agricultural crop (e.g. "Pizza", "Keyboard", "Blarg"):
  - Set is_valid_crop to false
  - Set invalid_crop_message to a short, warm message telling the farmer the name
    wasn't recognised and suggesting they check the spelling or try a common crop
  - Leave actions as [], explanations as [], summary as ""

If the crop is real:
  - Set is_valid_crop to true, invalid_crop_message to ""
  - Fill actions, explanations, summary normally

Other strict constraints:
- actions and explanations must be the same length (one explanation per action).
- summary is a single flowing paragraph, not a list.
- No keys beyond the six above.
"""


def _call_gemini(prompt: str) -> str | None:
    """
    Make a direct REST call to the Gemini API.

    Returns the raw response text on success, None on any failure.
    Using httpx (already a project dependency) — no extra packages needed.
    """
    if not _API_KEY:
        return None

    try:
        r = httpx.post(
            _ENDPOINT,
            params={"key": _API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature":        0,              # deterministic output
                    "response_mime_type": "application/json",
                },
            },
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except httpx.HTTPStatusError as e:
        print(f"[gemini.py] HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[gemini.py] Gemini call failed: {e}")
        return None


def decide_and_advise(
    crop: str,
    location: str,
    stage: str,
    weather_summary: dict,
) -> dict | None:
    """
    Use Gemini to reason about today's farm conditions and return
    structured recommendations.

    Returns:
        On success (valid crop):
            {
                "actions":      [str, ...],
                "explanations": [str, ...],
                "summary":      str,
            }
        On invalid crop:
            {"_invalid_crop": True, "message": str}
        On failure (no key, quota, network):
            None  →  agent.py falls back to rule engine
    """
    if not _API_KEY:
        return None

    temp     = weather_summary.get("temp")
    precip   = weather_summary.get("precip")
    humidity = weather_summary.get("humidity")

    prompt = f"""You are AgriSense, an experienced agronomist advising smallholder farmers.

A farmer is growing {crop} in {location} at the {stage} growth stage.

Today's weather conditions:
- Temperature:   {temp}°C
- Precipitation: {precip} mm expected today
- Humidity:      {humidity}%

Produce a practical daily farm plan following these guidelines:
1. Give 3–5 specific, actionable recommendations tailored to {crop} at the {stage} stage.
2. Ground every recommendation in the actual weather numbers above — avoid generic advice.
3. Explicitly account for how the {stage} growth stage changes this crop's sensitivity
   to heat, water stress, and humidity.
4. Use plain, simple language — the farmer may not have technical training.
5. The summary should be warm, practical, and encouraging (4–6 sentences).

{_SCHEMA_RULES}"""

    raw = _call_gemini(prompt)
    if raw is None:
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[gemini.py] JSON parse failed: {e} | raw={raw[:200]}")
        return None

    # ── Case 1: invalid crop ─────────────────────────────────────────────────
    if parsed.get("is_valid_crop") is False:
        msg = parsed.get("invalid_crop_message") or (
            "I don't recognise that as an agricultural crop. "
            "Please check the spelling or try a crop like Wheat, Rice, or Tomato."
        )
        return {"_invalid_crop": True, "message": msg}

    # ── Case 2: valid crop — validate shape ──────────────────────────────────
    if (
        isinstance(parsed.get("actions"), list)
        and isinstance(parsed.get("explanations"), list)
        and isinstance(parsed.get("summary"), str)
        and len(parsed["actions"]) > 0
        and len(parsed["actions"]) == len(parsed["explanations"])
    ):
        return parsed

    print(f"[gemini.py] Unexpected response shape: {list(parsed.keys())} — falling back")
    return None
