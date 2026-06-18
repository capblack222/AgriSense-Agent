"""
models.py - Pydantic request and response models.

These define the data contract for every API endpoint.
FastAPI uses them to:
    - Validate incoming JSON automatically (returns 422 if invalid)
    - Generate the interactive API docs at /docs
    - Serialize outgoing responses cleanly

Keep request and response models separate - the internal DB shape
can change without breaking the public API contract.
"""

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Body for POST /auth/register"""
    email:    EmailStr           # Pydantic validates email format automatically
    password: str = Field(min_length=6, description="Minimum 6 characters")


class LoginRequest(BaseModel):
    """Body for POST /auth/login"""
    email:    EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response from POST /auth/login"""
    access_token: str
    token_type:   str = "bearer"


# ---------------------------------------------------------------------------
# Agent models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    """Body for POST /agent/run"""
    crop:     str = Field(description="Crop name, e.g. 'Wheat', 'Tomato'")
    location: str = Field(description="City or region name, e.g. 'Ranchi'")
    stage:    str = Field(
        default="Vegetative",
        description="Growth stage: Seedling | Vegetative | Flowering | Harvest",
    )


class WeatherSnapshot(BaseModel):
    """Current weather values used in a decision run"""
    temp:     float | None
    precip:   float | None
    humidity: float | None


class RunResponse(BaseModel):
    """Response from POST /agent/run"""
    crop:             str
    location:         str
    stage:            str
    weather:          WeatherSnapshot
    actions:          list[str]        # rule engine output
    explanations:     list[str]        # one explanation per action
    llm_summary:      str              # Gemini's natural language synthesis


class HistoryEntry(BaseModel):
    """A single past decision run, as stored in MongoDB"""
    timestamp:        str
    crop:             str
    location:         str
    stage:            str | None
    weather_snapshot: dict
    actions_suggested: list[str]
    explanations:     list[str]
    llm_summary:      str | None = None


class HistoryResponse(BaseModel):
    """Response from GET /agent/history"""
    user_id: str
    history: list[HistoryEntry]
