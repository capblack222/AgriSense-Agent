"""
database.py — MongoDB connection (singleton pattern).

One Motor client is created when this module is first imported and reused
across every request. This avoids the overhead of opening a new connection
per API call.

Collections:
    users    → account credentials (email, hashed password)
    memories → per-user farm decision history
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()   # reads .env so os.getenv() finds MONGODB_URL

# ---------------------------------------------------------------------------
# Client — created once, shared everywhere
# Motor is non-blocking: it works with FastAPI's async event loop natively.
# ---------------------------------------------------------------------------
_MONGODB_URL = os.getenv("MONGODB_URL")
if not _MONGODB_URL:
    raise RuntimeError(
        "MONGODB_URL is not set. "
        "Copy .env.example to .env and fill in your Atlas connection string."
    )

# AsyncIOMotorClient manages an internal connection pool automatically.
# max_pool_size=10 means up to 10 concurrent DB operations can run at once —
# more than enough for this application.
client: AsyncIOMotorClient = AsyncIOMotorClient(_MONGODB_URL, maxPoolSize=10)

# The database is named "agrisense" — Atlas will create it automatically
# on first write if it doesn't exist yet.
db = client["agrisense"]

# ---------------------------------------------------------------------------
# Collections — think of these as tables, but schema-flexible
# ---------------------------------------------------------------------------
users_collection    = db["users"]     # { email, hashed_password, created_at }
memories_collection = db["memories"]  # { user_id, crop, location, stage, history: [] }
