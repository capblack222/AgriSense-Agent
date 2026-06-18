"""
memory.py — MongoDB-backed persistent farm memory.

Replaces the in-memory FarmMemory class from the notebook.
Each user's memory is one document in the 'memories' collection,
keyed by user_id (their email address).

Document shape in MongoDB:
{
    "user_id":  "nish@example.com",
    "crop":     "Wheat",
    "location": "Ranchi",
    "stage":    "Vegetative",
    "history": [
        {
            "timestamp":       "2026-06-18 10:30:00",
            "crop":            "Wheat",
            "location":        "Ranchi",
            "stage":           "Vegetative",
            "weather_snapshot": { "temp": 28.5, "precip": 0.0, "humidity": 72 },
            "actions_suggested": [...],
            "explanations":    [...],
            "llm_summary":     "..."   ← Gemini's natural language summary
        },
        ...
    ]
}

All methods are async because Motor (the MongoDB driver) is non-blocking.
"""

from datetime import datetime
from database import memories_collection


class FarmMemory:
    """
    Persistent farm memory for a single user.
    Pass the user's email (or any unique ID) on construction.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id

    # ── Read ─────────────────────────────────────────────────────────────────

    async def get(self) -> dict:
        """Return the full memory document for this user, or an empty default."""
        doc = await memories_collection.find_one(
            {"user_id": self.user_id},
            {"_id": 0},   # exclude MongoDB's internal _id field from results
        )
        if doc is None:
            return {
                "user_id":  self.user_id,
                "crop":     None,
                "location": None,
                "stage":    None,
                "history":  [],
            }
        return doc

    async def get_last(self) -> dict | None:
        """Return the most recent decision entry, or None if no history."""
        doc = await self.get()
        history = doc.get("history", [])
        return history[-1] if history else None

    # ── Write ────────────────────────────────────────────────────────────────

    async def set_farm_details(self, crop: str, location: str, stage: str | None = None):
        """
        Save or update the user's current crop/location/stage.
        Uses upsert=True: creates the document if it doesn't exist yet,
        updates it if it does. One operation, no existence check needed.
        """
        await memories_collection.update_one(
            {"user_id": self.user_id},
            {"$set": {"crop": crop, "location": location, "stage": stage}},
            upsert=True,
        )

    async def add_entry(self, entry: dict):
        """
        Append a new decision entry to the user's history.
        $push adds to the array without replacing the whole document.
        """
        entry["timestamp"] = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        await memories_collection.update_one(
            {"user_id": self.user_id},
            {"$push": {"history": entry}},
            upsert=True,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def get_history_summary(self, n_last: int = 5) -> list[dict]:
        """
        Return the last n decision entries as plain dicts.
        Used by the frontend history panel.
        """
        doc = await self.get()
        history = doc.get("history", [])
        return history[-n_last:] if history else []
