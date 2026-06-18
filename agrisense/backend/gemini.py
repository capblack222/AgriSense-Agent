"""
gemini.py — Gemini LLM reasoning layer.

Takes the rule engine's structured output (actions + explanations + weather)
and synthesises it into a single, clear, farmer-friendly paragraph.

The rule engine is the source of truth for WHAT to do.
Gemini's job is to make it readable and human — not to invent new advice.

If the Gemini call fails for any reason, we gracefully fall back to
joining the rule engine actions into plain text so the app never breaks.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_API_KEY = os.getenv("GEMINI_API_KEY")
if _API_KEY:
    genai.configure(api_key=_API_KEY)

# We use gemini-1.5-flash: fast, cheap, and more than capable for
# text synthesis tasks like this. No need for the heavier Pro model.
_MODEL_NAME = "gemini-1.5-flash"


def synthesise_advice(
    crop: str,
    location: str,
    stage: str,
    weather_summary: dict,
    actions: list[str],
    explanations: list[str],
) -> str:
    """
    Call Gemini to synthesise the rule engine output into natural language.

    Args:
        crop, location, stage  — farm context
        weather_summary        — { temp, precip, humidity }
        actions                — list of imperative recommendations from rules.py
        explanations           — one-sentence reasoning per action

    Returns:
        A single plain-language paragraph the farmer can read and act on.
        Falls back to a joined action list if the API call fails.
    """
    if not _API_KEY:
        # No API key configured — return a clean fallback without crashing
        return _fallback(actions)

    # ── Build the prompt ─────────────────────────────────────────────────────
    # We give Gemini the full context and the rule engine output.
    # We're explicit that it should NOT invent advice beyond what the rules say.
    actions_text      = "\n".join(f"- {a}" for a in actions)
    explanations_text = "\n".join(f"- {e}" for e in explanations)

    prompt = f"""You are AgriSense, a helpful farm assistant designed to support smallholder farmers.

A farmer is growing {crop} in {location} at the {stage} stage.

Current weather:
- Temperature: {weather_summary.get('temp')}°C
- Precipitation: {weather_summary.get('precip')} mm
- Humidity: {weather_summary.get('humidity')}%

Our rule engine has produced the following recommendations:
{actions_text}

Supporting explanations:
{explanations_text}

Your task:
Write a single, warm, clear paragraph (4–6 sentences) that:
1. Acknowledges today's weather conditions briefly
2. Explains the most important actions the farmer should take today
3. Mentions why the growth stage matters for these decisions
4. Uses simple, plain language — the audience may not be technically trained

Important: Do NOT invent advice beyond what the rule engine has provided above.
Do NOT use bullet points. Write in flowing prose. Be practical and encouraging.
"""

    # ── Call Gemini ──────────────────────────────────────────────────────────
    try:
        model    = genai.GenerativeModel(_MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Any API error (quota, network, bad key) → fall back gracefully
        print(f"[gemini.py] Gemini call failed: {e}")
        return _fallback(actions)


def _fallback(actions: list[str]) -> str:
    """
    Readable fallback when Gemini is unavailable (no API key or network error).
    Strips stage-context prefixes (already shown as cards) and joins the
    remaining action sentences into a clean paragraph.
    """
    if not actions:
        return (
            "Based on today's weather, no urgent actions are needed. "
            "Monitor your crop and check back tomorrow."
        )

    # Drop the stage-context lines — they're already shown as colour-coded cards
    clean = [
        a.split("] ", 1)[-1] if (a.startswith("[") and "] " in a) else a
        for a in actions
        if not (a.startswith("[") and "Stage]" in a)
    ]
    if not clean:
        clean = actions

    # Ensure each sentence ends with a period, then join into one paragraph
    sentences = [s.strip().rstrip(".") + "." for s in clean]
    return " ".join(sentences)
