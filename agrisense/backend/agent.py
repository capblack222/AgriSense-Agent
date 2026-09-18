"""
agent.py - FarmAgent orchestrator.

Coordinates the full agent pipeline:
    1. fetch_weather()      → get live weather data      ┐
       retrieve_context()  → RAG knowledge retrieval     ├─ concurrent via asyncio.gather
       get_history()       → MongoDB farm memory         ┘
    2. decide_and_advise()  → Gemini reasons from weather + RAG context (primary path)
       └─ fallback:           decide_actions() rule engine if Gemini unavailable
    3. FarmMemory.add_entry() → persist to MongoDB

Pipeline change from v1:
    Before: weather → rules → Gemini (rephrase)
    v2:     weather → Gemini (reason) → [rules fallback if needed]
    v3:     weather + RAG knowledge → Gemini (reason + grounded) → [rules fallback]

Gemini is now the decision-maker, not a copywriter.
RAG provides agronomic knowledge context to reduce hallucination.
rules.py is the safety net.
"""

import asyncio
import logging

from weather import fetch_weather
from gemini  import decide_and_advise
from rules   import decide_actions      # fallback only
from memory  import FarmMemory

logger = logging.getLogger(__name__)

# ── RAG retriever (loaded lazily — ingest must have been run first) ──────────
_retriever = None

def _get_retriever():
    """Load RAG retriever once and reuse. Returns None if index not built yet."""
    global _retriever
    if _retriever is None:
        try:
            from rag import Retriever
            _retriever = Retriever()
            print("[agent.py] ✅ RAG retriever loaded successfully")
        except Exception as exc:
            print(f"[agent.py] ⚠️  RAG retriever unavailable: {exc} — continuing without RAG")
            _retriever = False  # sentinel: don't retry on every call
    return _retriever if _retriever else None


async def _fetch_rag_context(crop: str, stage: str, weather_summary: dict) -> str:
    """
    Build a query from the current request and retrieve relevant knowledge chunks.
    Runs in a thread pool executor so it doesn't block the event loop.

    Returns a formatted context string (empty string if RAG is unavailable).
    """
    retriever = _get_retriever()
    if retriever is None:
        return ""

    # Build a rich query: crop + stage + weather signals
    temp = weather_summary.get("temp", "")
    humidity = weather_summary.get("humidity", "")
    query = f"{crop} crop {stage} stage irrigation management"
    if temp:
        query += f" temperature {temp}°C"
    if humidity:
        query += f" humidity {humidity}%"

    try:
        loop = asyncio.get_event_loop()
        context = await loop.run_in_executor(
            None, retriever.retrieve_and_format, query, 5, 2000
        )
        return context
    except Exception as exc:
        print(f"[agent.py] ⚠️  RAG retrieval failed: {exc}")
        return ""


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

        # ── Step 1: Concurrent fetch — weather + RAG context ────────────────────
        # Both are independent I/O; run them in parallel to reduce latency.
        # RAG is best-effort: a failure returns empty string, not an error.
        weather, rag_context = await asyncio.gather(
            fetch_weather(location),
            _fetch_rag_context(crop, stage, {}),  # empty weather dict OK here
        )

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

        # Re-fetch RAG with real weather data for a better query
        # (only if first attempt returned empty — i.e., weather was not yet known)
        if not rag_context:
            rag_context = await _fetch_rag_context(crop, stage, weather_summary)

        if rag_context:
            print(f"[agent.py] ✅ RAG context retrieved ({len(rag_context)} chars)")

        # ── Step 2: LLM decision engine (primary path) ───────────────────────
        # Gemini reasons from raw weather data + RAG knowledge context.
        # Returns None if unavailable — we fall back to rules.py below.
        llm_result = decide_and_advise(
            crop            = crop,
            location        = location,
            stage           = stage,
            weather_summary = weather_summary,
            rag_context     = rag_context,
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
