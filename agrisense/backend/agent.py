"""
agent.py - FarmAgent orchestrator.

Coordinates the full agent pipeline:
    1. fetch_weather()    → get live weather data
    2. decide_actions()   → apply rule engine
    3. synthesise_advice()→ Gemini LLM natural language summary
    4. FarmMemory.add_entry() → persist to MongoDB

This class has no I/O of its own and no Jupyter dependencies.
It is called by main.py routes and is fully testable in isolation.
"""

from weather import fetch_weather
from rules   import decide_actions
from gemini  import synthesise_advice
from memory  import FarmMemory


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

        # ── Step 2: Apply rule engine ────────────────────────────────────────
        decision     = decide_actions(weather, crop, stage)
        actions      = decision["actions"]
        explanations = decision["explanations"]

        # ── Step 3: LLM synthesis ────────────────────────────────────────────
        # Gemini reads the rule output and writes a farmer-friendly paragraph.
        llm_summary = synthesise_advice(
            crop            = crop,
            location        = location,
            stage           = stage,
            weather_summary = weather_summary,
            actions         = actions,
            explanations    = explanations,
        )

        # ── Step 4: Persist to MongoDB ───────────────────────────────────────
        # Save farm details (crop/location/stage for future sessions)
        await self.memory.set_farm_details(crop, location, stage)

        # Append this run to the user's history
        await self.memory.add_entry({
            "crop":             crop,
            "location":         location,
            "stage":            stage,
            "weather_snapshot": weather_summary,
            "actions_suggested": actions,
            "explanations":     explanations,
            "llm_summary":      llm_summary,
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
