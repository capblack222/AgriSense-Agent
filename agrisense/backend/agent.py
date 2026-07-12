"""
agent.py - FarmAgent orchestrator.

Coordinates the full agent pipeline:
    1. fetch_weather()      → get live weather data
    2. decide_and_advise()  → Gemini reasons from weather data (primary path)
       └─ fallback:           decide_actions() rule engine if Gemini unavailable
    3. FarmMemory.add_entry() → persist to MongoDB

Pipeline change from v1:
    Before: weather → rules → Gemini (rephrase)
    After:  weather → Gemini (reason) → [rules fallback if needed]

Gemini is now the decision-maker, not a copywriter.
rules.py is the safety net, not the engine.
"""

from weather import fetch_weather
from gemini  import decide_and_advise
from rules   import decide_actions      # fallback only
from memory  import FarmMemory


def _summarise_from_actions(actions: list[str]) -> str:
    """
    Fallback when Gemini is unavailable.
    Returns empty string — the frontend hides the "AgriSense says:" section
    when llm_summary is empty, avoiding a pointless repeat of the action cards.
    """
    return ""


class FarmAgent:
    """
    Stateless orchestrator: each run_agent() call is independent.
    State (history, farm details) lives in MongoDB via FarmMemory.
    """

    def __init__(self, user_id: str):
        """
        Args:
            user_id: the authenticated user's email address.
                     Used as the key for MongoDB memory lookups.
        """
        self.user_id = user_id
        self.memory  = FarmMemory(user_id)

    async def run_agent(self, crop: str, location: str, stage: str) -> dict:
        """
        Run the full agent pipeline for a single crop/location/stage query.

        Returns a dict ready to be serialised as the API response:
        {
            "crop":         str,
            "location":     str,
            "stage":        str,
            "weather":      { temp, precip, humidity },
            "actions":      [str, ...],
            "explanations": [str, ...],
            "llm_summary":  str,
        }
        """

        # ── Step 1: Fetch weather ────────────────────────────────────────────
        weather = fetch_weather(location)

        # If the weather fetch failed, return early with a clear error.
        # main.py converts temp=None to HTTP 422 so the frontend error path fires.
        if "error" in weather:
            return {
                "crop":         crop,
                "location":     location,
                "stage":        stage,
                "weather":      {"temp": None, "precip": None, "humidity": None},
                "actions":      [weather["error"]],
                "explanations": [],
                "llm_summary":  weather["error"],
            }

        weather_summary = weather["summary"]   # { temp, precip, humidity }

        # ── Step 2: LLM decision engine (primary path) ───────────────────────
        # Gemini reasons from raw weather data and returns structured advice.
        # Returns None if unavailable — we fall back to rules.py below.
        llm_result = decide_and_advise(
            crop            = crop,
            location        = location,
            stage           = stage,
            weather_summary = weather_summary,
        )

        if llm_result is not None and llm_result.get("_invalid_crop"):
            # ── Crop rejected by LLM — return early, nothing to persist ───────
            # main.py sees temp=None and raises HTTP 422 with the message,
            # which the frontend shows as a chat bubble at the crop step.
            return {
                "crop":         crop,
                "location":     location,
                "stage":        stage,
                "weather":      {"temp": None, "precip": None, "humidity": None},
                "actions":      [],
                "explanations": [],
                "llm_summary":  llm_result["message"],
            }

        if llm_result is not None:
            # ── Happy path: Gemini succeeded ─────────────────────────────────
            actions      = llm_result["actions"]
            explanations = llm_result["explanations"]
            llm_summary  = llm_result["summary"]
        else:
            # ── Fallback: Gemini unavailable → rule engine ───────────────────
            # Same output shape — frontend works identically either way.
            print(f"[agent.py] Using rule engine fallback for {crop}/{location}/{stage}")
            decision     = decide_actions(weather, crop, stage)
            actions      = decision["actions"]
            explanations = decision["explanations"]
            llm_summary  = _summarise_from_actions(actions)

        # ── Step 3: Persist to MongoDB ───────────────────────────────────────
        await self.memory.set_farm_details(crop, location, stage)
        await self.memory.add_entry({
            "crop":              crop,
            "location":          location,
            "stage":             stage,
            "weather_snapshot":  weather_summary,
            "actions_suggested": actions,
            "explanations":      explanations,
            "llm_summary":       llm_summary,
        })

        # ── Return structured result ─────────────────────────────────────────
        return {
            "crop":         crop,
            "location":     location,
            "stage":        stage,
            "weather":      weather_summary,
            "actions":      actions,
            "explanations": explanations,
            "llm_summary":  llm_summary,
        }

    async def get_history(self, n_last: int = 5) -> list[dict]:
        """Return the user's last n decision entries from MongoDB."""
        return await self.memory.get_history_summary(n_last)
