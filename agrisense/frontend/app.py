"""
frontend/app.py - AgriSense Streamlit chat interface.

Farmer-friendly UI with:
  - Warm earthy colour scheme (set in .streamlit/config.toml)
  - Colour-coded recommendation cards (irrigation / heat / humidity / stage)
  - Plain-language error messages - no stack traces shown to the user
  - Persistent session history in the sidebar

Run locally:
    streamlit run app.py

Change BACKEND_URL to deployed FastAPI URL when going live.
"""

import os
import re
import json
from datetime import datetime, timedelta
import streamlit as st
import httpx
import extra_streamlit_components as stx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Read from env var so the deployed frontend can point at the production API
# without code changes. Set BACKEND_URL in Streamlit Cloud secrets or your
# shell when deploying; falls back to localhost for local development.
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title = "AgriSense - Your Farm Assistant",
    page_icon  = "🌾",
    layout     = "centered",
)

# ---------------------------------------------------------------------------
# Cookie manager — persists JWT across page refreshes.
# Direct instantiation with a fixed key is the correct pattern for
# extra-streamlit-components: avoids the phantom reruns caused by
# @st.cache_resource + experimental_allow_widgets that break button clicks.
# ---------------------------------------------------------------------------
_cookies = stx.CookieManager(key="agrisense_cookies")

# ---------------------------------------------------------------------------
# Shared CSS - colour-coded recommendation cards
# Each card type maps to a keyword in the action text.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* ── Sidebar layout ── */
/* Remove the collapse/close button entirely */
div[data-testid="stSidebarHeader"] {
    display: none !important;
}
/* Make ONLY the top-level widget block a flex column (not nested expander blocks) */
div[data-testid="stSidebarContent"] > div[data-testid="stVerticalBlock"],
div[data-testid="stSidebarContent"] > div > div[data-testid="stVerticalBlock"] {
    display: flex !important;
    flex-direction: column !important;
    min-height: 100vh !important;
}
/* Spacer that pushes logout to the very bottom */
.sidebar-spacer {
    flex: 1 !important;
    min-height: 40px;
}

/* ── Shared card base ── */
.card {
    border-radius: 10px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 15px;
    line-height: 1.5;
}
/* Irrigation - calm blue */
.card-irrigation {
    background-color: #d0eaf8;
    border-left: 5px solid #2196f3;
    color: #0d2d45;
}
/* Heat alert - warm orange */
.card-heat {
    background-color: #fde8cc;
    border-left: 5px solid #e07b00;
    color: #3d1f00;
}
/* Humidity / fungal - muted purple */
.card-humidity {
    background-color: #ede0f5;
    border-left: 5px solid #8e44ad;
    color: #2d0c40;
}
/* Stage note - soft green */
.card-stage {
    background-color: #d6edd8;
    border-left: 5px solid #40916c;
    color: #0d2e18;
}
/* General / fallback - warm grey */
.card-general {
    background-color: #f5f0e6;
    border-left: 5px solid #9e8a6a;
    color: #2a2010;
}
/* Weather strip */
.weather-strip {
    background-color: #e8f5e9;
    border-radius: 10px;
    padding: 10px 16px;
    display: flex;
    gap: 24px;
    font-size: 15px;
    color: #1b3a2a;
    margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
defaults = {
    "token":      None,
    "user_email": None,
    "messages":   [],
    "step":       "crop",
    "run_data":   {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Cookie restore — runs once per page load.
# CookieManager is a browser component: it needs one render cycle to transmit
# cookies back to Python. On a fresh page load st.session_state is empty and
# _cookies.get() returns None until the JS responds. We trigger one controlled
# rerun (tracked by a session flag so it only fires once) to give it time.
# ---------------------------------------------------------------------------
# ── Cookie restore (on page refresh / new tab) ───────────────────────────────
# Both token and email are stored as JSON in a single cookie ("agrisense_auth").
# One cookie → one .set() / .get() / .delete() call per render, which avoids
# the DuplicateWidgetID error that fires when .set() is called more than once
# in the same render cycle (extra-streamlit-components uses a hardcoded key).
#
# CookieManager needs one render cycle to transmit cookies back to Python,
# so we rerun once if they're not ready yet.
if not st.session_state.token and not st.session_state.get("_prevent_cookie_restore"):
    _saved_raw = _cookies.get("agrisense_auth")
    if _saved_raw:
        try:
            # CookieManager may auto-parse JSON and return a dict, or return
            # the raw string depending on the version — handle both.
            _saved = _saved_raw if isinstance(_saved_raw, dict) else json.loads(_saved_raw)
            st.session_state.token      = _saved["token"]
            st.session_state.user_email = _saved["email"]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # malformed cookie — ignore and show login
    # No explicit st.rerun() here — CookieManager already triggers its own
    # rerun when its JS component sends cookies back to Python.
    # Adding a manual st.rerun() here races with that and crashes on first load.

# ── Cookie write (after login) ────────────────────────────────────────────────
# Written passively here (not inside the button handler) to avoid the
# CookieManager rerender that would consume the button event mid-click.
if st.session_state.token and not st.session_state.get("_cookie_written"):
    _expire = datetime.now() + timedelta(hours=1)
    _cookies.set(
        "agrisense_auth",
        json.dumps({"token": st.session_state.token, "email": st.session_state.user_email}),
        expires_at=_expire,
    )
    st.session_state._cookie_written = True

# ---------------------------------------------------------------------------
# Helper: classify an action string into a card type
# ---------------------------------------------------------------------------
def _card_type(action: str) -> str:
    lower = action.lower()
    if "irrigate" in lower or "water" in lower or "rain" in lower:
        return "irrigation"
    if "heat" in lower or "temperature" in lower or "shade" in lower or "mulch" in lower:
        return "heat"
    if "humid" in lower or "fungal" in lower or "pest" in lower or "airflow" in lower:
        return "humidity"
    if "stage" in lower or "seedling" in lower or "flowering" in lower or "harvest" in lower or "vegetative" in lower:
        return "stage"
    return "general"

_CARD_ICONS = {
    "irrigation": "💧",
    "heat":       "🌡️",
    "humidity":   "🍄",
    "stage":      "🌱",
    "general":    "📌",
}

def render_action_card(action: str) -> str:
    ctype = _card_type(action)
    icon  = _CARD_ICONS[ctype]
    # Strip the "[Stage] " prefix if present - the card colour already signals stage
    text = action.replace("[Seedling Stage] ", "").replace("[Vegetative Stage] ", "") \
                 .replace("[Flowering Stage] ", "").replace("[Harvest Stage] ", "")
    return f'<div class="card card-{ctype}">{icon} {text}</div>'


# ---------------------------------------------------------------------------
# Helper: API calls with friendly error handling
# ---------------------------------------------------------------------------
def api_post(endpoint: str, payload: dict, auth: bool = False) -> dict:
    headers = {}
    if auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = httpx.post(f"{BACKEND_URL}{endpoint}", json=payload, headers=headers, timeout=30)
        return r.json()
    except httpx.ConnectError:
        return {"_friendly_error": "We couldn't reach the AgriSense server. Is it running?"}
    except httpx.TimeoutException:
        return {"_friendly_error": "The request took too long. Please try again in a moment."}
    except Exception as e:
        return {"_friendly_error": f"Something unexpected happened: {e}"}


def api_get(endpoint: str, params: dict = {}) -> dict:
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        r = httpx.get(f"{BACKEND_URL}{endpoint}", params=params, headers=headers, timeout=30)
        return r.json()
    except httpx.ConnectError:
        return {"_friendly_error": "Couldn't reach the server to load your history."}
    except httpx.TimeoutException:
        return {"_friendly_error": "Loading your history took too long. Try again."}
    except Exception as e:
        return {"_friendly_error": str(e)}


def show_friendly_error(res: dict):
    """Show a plain-language error. Never expose raw API detail to the user."""
    if "_friendly_error" in res:
        st.error(f"⚠️ {res['_friendly_error']}")
    elif "detail" in res:
        detail = res["detail"]
        # Map common API errors to plain language
        friendly = {
            "Incorrect email or password.":
                "Hmm, that email or password doesn't look right. Want to try again?",
            "An account with this email already exists.":
                "Looks like you already have an account with that email. Try logging in instead.",
            "Token is invalid or has expired. Please log in again.":
                "Your session expired. Please log in again - it only takes a second.",
        }.get(detail, detail)
        st.error(f"⚠️ {friendly}")


# ---------------------------------------------------------------------------
# View 1 - Login / Register
# ---------------------------------------------------------------------------
def show_auth():
    st.markdown(
        "<h1 style='text-align:center; color:#40916c;'>🌾 AgriSense</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#6b5b3e; font-size:17px;'>"
        "Your daily AI-powered farm guide - personalised to your crop, location, and growth stage."
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    tab_login, tab_register = st.tabs(["🔑  Log In", "🌱  Create Account"])

    with tab_login:
        st.markdown("##### Welcome back! Enter your details below.")
        email    = st.text_input("Email address", key="login_email",    placeholder="you@example.com")
        password = st.text_input("Password",       key="login_password", placeholder="Your password", type="password")

        if st.button("Log In  →", use_container_width=True, type="primary"):
            if not email or not password:
                st.warning("Please fill in both your email and password.")
            else:
                with st.spinner("Logging you in…"):
                    res = api_post("/auth/login", {"email": email, "password": password})
                if "access_token" in res:
                    st.session_state.token      = res["access_token"]
                    st.session_state.user_email = email
                    # No _cookies.set() here — cookies are written passively at
                    # the top of the script on the next render to avoid the
                    # CookieManager rerender that would consume this button event.
                    st.rerun()
                else:
                    show_friendly_error(res)

    with tab_register:
        st.markdown("##### Create a free account to get started.")
        email    = st.text_input("Email address",      key="reg_email",    placeholder="you@example.com")
        password = st.text_input("Choose a password",  key="reg_password", placeholder="At least 6 characters", type="password")

        if st.button("Create My Account  →", use_container_width=True, type="primary"):
            if not email or not password:
                st.warning("Please fill in both fields to create your account.")
            elif len(password) < 6:
                st.warning("Your password needs to be at least 6 characters long.")
            else:
                with st.spinner("Setting up your account…"):
                    res = api_post("/auth/register", {"email": email, "password": password})
                if "message" in res:
                    st.success("Account created! Switch to the Log In tab to get started.")
                else:
                    show_friendly_error(res)

    st.divider()
    st.caption("AgriSense - built for smallholder farmers. Inspired by the villages of Kanpur.")


# ---------------------------------------------------------------------------
# View 2 - Main chat interface
# ---------------------------------------------------------------------------
def show_chat():

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        # Brand header
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #40916c 0%, #2d6a4f 100%);
            border-radius: 14px;
            padding: 22px 16px 18px;
            text-align: center;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(45,106,79,0.18);
        ">
            <div style="font-size: 42px; line-height: 1; margin-bottom: 6px;">🌾</div>
            <div style="color: #ffffff; font-size: 21px; font-weight: 700;
                        letter-spacing: 0.5px; margin-bottom: 3px;">AgriSense</div>
            <div style="color: #b7e4c7; font-size: 12px; letter-spacing: 0.3px;">
                AI-Powered Farm Assistant
            </div>
        </div>
        """, unsafe_allow_html=True)

        # User badge
        st.markdown(f"""
        <div style="
            background: #fffdf5;
            border: 1px solid #d9c68a;
            border-radius: 10px;
            padding: 10px 13px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            gap: 10px;
        ">
            <span style="font-size: 22px;">🧑‍🌾</span>
            <div style="overflow: hidden;">
                <div style="font-size: 10px; color: #9e8a6a; text-transform: uppercase;
                            letter-spacing: 0.7px; margin-bottom: 2px;">Signed in as</div>
                <div style="font-size: 12px; color: #2d6a4f; font-weight: 600;
                            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                    {st.session_state.user_email}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Section label
        st.markdown("""
        <div style="font-size: 14px; font-weight: 700; color: #7a6344;
                    text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 10px;">
            🔍 &nbsp;Recent Searches
        </div>
        """, unsafe_allow_html=True)

        if st.button("Load my history", use_container_width=True):
            with st.spinner("Fetching your recent decisions…"):
                history_res = api_get("/agent/history", {"n": 5})

            if "_friendly_error" in history_res:
                st.error(history_res["_friendly_error"])
            elif "history" in history_res:
                entries = history_res["history"]
                if not entries:
                    st.info("No decisions yet - run your first query to get started!")
                else:
                    for entry in reversed(entries):
                        ws = entry.get("weather_snapshot", {})
                        label = f"🌾 {entry['crop']} @ {entry['location']}"
                        with st.expander(label):
                            st.caption(entry.get("timestamp", ""))
                            t = ws.get('temp', '-')
                            p = ws.get('precip', '-')
                            h = ws.get('humidity', '-')
                            st.markdown(f"""
                                    <div style="display:flex;gap:6px;margin:6px 0 10px;">
                                    <div style="flex:1;background:#f9f4e8;border-radius:6px;padding:6px 4px;text-align:center;">
                                        <div style="font-size:9px;color:#9e8a6a;font-weight:700;letter-spacing:.5px;">TEMP</div>
                                        <div style="font-size:14px;font-weight:700;color:#2d6a4f;">{t}°C</div>
                                    </div>
                                    <div style="flex:1;background:#f9f4e8;border-radius:6px;padding:6px 4px;text-align:center;">
                                        <div style="font-size:9px;color:#9e8a6a;font-weight:700;letter-spacing:.5px;">RAIN</div>
                                        <div style="font-size:14px;font-weight:700;color:#2d6a4f;">{p}mm</div>
                                    </div>
                                    <div style="flex:1;background:#f9f4e8;border-radius:6px;padding:6px 4px;text-align:center;">
                                        <div style="font-size:9px;color:#9e8a6a;font-weight:700;letter-spacing:.5px;">HUM</div>
                                        <div style="font-size:14px;font-weight:700;color:#2d6a4f;">{h}%</div>
                                    </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                            if entry.get("llm_summary"):
                                st.info(entry["llm_summary"])
            else:
                st.error("Couldn't load your history right now. Try again in a moment.")

        # Flexible spacer pushes tagline + logout to the very bottom
        # st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)

        st.markdown("""
        <div style="padding-top: 12px; border-top: 1px solid #d9c68a;
                    text-align: center; font-size: 11px; color: #b0996e; margin-bottom: 8px;">
            🌱 Built for smallholder farmers<br>
            <span style="color:#c5a96e;">Inspired by the villages of Kanpur</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🚪  Log Out", use_container_width=True):
            _cookies.delete("agrisense_auth")
            for k, v in defaults.items():
                st.session_state[k] = v
            # Prevent cookie restore from picking up the not-yet-deleted cookie
            # on the very next rerun (browser cookie deletion is async).
            st.session_state._prevent_cookie_restore = True
            st.session_state._cookie_written         = False
            st.rerun()

    # ── Main area ─────────────────────────────────────────────────────────────
    st.markdown(
        "<h2 style='color:#40916c;'>🌾 AgriSense</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Ask me about any crop and I'll fetch today's weather and give you a personalised farm plan.")

    # Replay existing messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🌾" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"], unsafe_allow_html=True)

    # Opening greeting on first load
    if not st.session_state.messages:
        greeting = (
            "Hello! I'm **AgriSense**, your personal farm assistant. 🌱\n\n"
            "Tell me your crop and location and I'll check today's weather "
            "to give you a tailored daily farm plan.\n\n"
            "**Which crop would you like guidance for today?**  \n"
            "*Wheat, Rice, Tomato, Maize, or anything else you're growing — just tell me!*"
        )
        with st.chat_message("assistant", avatar="🌾"):
            st.markdown(greeting)
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.step = "crop"

    # ── Conversational input ─────────────────────────────────────────────────
    user_input = st.chat_input("Type your answer here…")

    if user_input:
        # Show user's message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        step    = st.session_state.step
        cleaned = user_input.strip()
        reply   = ""

        _EXIT_WORDS   = {"done", "no", "exit", "quit", "thanks", "thank you", "bye", "stop"}
        _VALID_STAGES = {"Seedling", "Vegetative", "Flowering", "Harvest"}

        # Fuzzy stage keywords — catches "seedling stage", "it's flowering",
        # "almost ready to harvest", "in the vegetative phase", etc.
        _STAGE_KEYWORDS = {
            "Seedling":   ["seed", "seedling", "sprout", "germina", "young plant"],
            "Vegetative": ["vegetat", "vegeta", "growing", "growth", "leaf", "leaves", "stem"],
            "Flowering":  ["flower", "bloom", "bud", "fruit", "pollinat"],
            "Harvest":    ["harvest", "ripe", "ripen", "mature", "ready", "pick"],
        }

        def _fuzzy_stage(text: str) -> str | None:
            lower = text.lower()
            for stage, keywords in _STAGE_KEYWORDS.items():
                if any(kw in lower for kw in keywords):
                    return stage
            return None

        # Greeting: regex match at the START of the string so "hey there!",
        # "hello, how are you", etc. are all caught — not just exact words.
        _GREETING_RE = re.compile(
            r'^(hi+|hello|hey+|hiya|howdy|sup|good\s+morning|good\s+evening|'
            r'good\s+afternoon|namaste)\b',
            re.IGNORECASE,
        )
        # Confused: short standalone phrases ("idk", "not sure", etc.)
        _CONFUSED_WORDS = {"idk", "i don't know", "i dont know", "not sure",
                           "unsure", "dunno", "no idea", "hmm", "?", "help", "what", "huh"}

        def _is_greeting(text: str) -> bool:
            return bool(_GREETING_RE.match(text.strip()))

        def _is_confused(text: str) -> bool:
            # Strip trailing punctuation so "what?" matches "what", "hmm..." matches "hmm"
            normalised = re.sub(r'[?!.,]+$', '', text.strip().lower())
            return normalised in _CONFUSED_WORDS

        # ── EXIT KEYWORDS - checked first ────────────────────────────────────
        if cleaned.lower() in _EXIT_WORDS:
            reply = (
                "You're all set for today! 🌾\n\n"
                "Come back tomorrow and I'll check the weather again and update your farm plan. "
                "Wishing you a great harvest! 🌻"
            )
            st.session_state.step     = "crop"
            st.session_state.run_data = {}

        # ── GREETINGS / CONFUSED — re-prompt for the current step ────────────
        elif _is_greeting(cleaned) or _is_confused(cleaned):
            if step == "crop":
                reply = (
                    "Hey there! 👋 I'm AgriSense, your farm assistant.\n\n"
                    "**Which crop are you growing?**  \n"
                    "*Wheat, Rice, Tomato, Maize, or anything else — just tell me!*"
                )
            elif step == "location":
                reply = (
                    "No worries! Just type the name of the nearest town or city to your farm.  \n"
                    "*Examples: Ranchi, Pune, Ahmedabad, New Delhi*"
                )
            else:  # stage
                reply = (
                    "Not sure which stage? Here's a quick guide:\n\n"
                    "- **Seedling** — young plant, just sprouted\n"
                    "- **Vegetative** — actively growing leaves and stems\n"
                    "- **Flowering** — producing flowers or setting fruit\n"
                    "- **Harvest** — crop is ready or nearly ready\n\n"
                    "Which one fits your crop right now?"
                )
            # Step does not change — we re-ask the same question

        # ── Step 1: crop ─────────────────────────────────────────────────────
        # Validate immediately via a lightweight Gemini call so "Note", "Pizza",
        # "Hello" etc. are caught here — not after the user fills in location
        # and stage too. Fails open if Gemini is unavailable.
        elif step == "crop":
            crop = cleaned.title()
            if len(crop) < 2:
                reply = "Please tell me which crop you're growing — for example: Wheat, Tomato, Rice."
                # Step stays at "crop"
            else:
                with st.spinner("Checking that crop name…"):
                    validation = api_post("/agent/validate-crop", {"crop": crop})

                if validation.get("is_valid") is False:
                    # Gemini says not a real crop — show its message and re-ask
                    reply = validation.get("message") or (
                        f"I don't recognise **{crop}** as an agricultural crop. "
                        "Could you check the spelling? Try something like Wheat, Rice, or Tomato."
                    )
                    # Step stays at "crop"
                else:
                    # Valid crop (or Gemini unavailable → fail open → proceed)
                    st.session_state.run_data["crop"] = crop
                    reply = (
                        f"Great - **{crop}**! 🌿\n\n"
                        "**Which city or region is your farm in?**  \n"
                        "*For example: Ranchi, Pune, Ahmedabad, Lucknow…*"
                    )
                    st.session_state.step = "location"

        # ── Step 2: location ─────────────────────────────────────────────────
        elif step == "location":
            location = cleaned
            # Allow letters, digits, spaces, hyphens, dots, apostrophes.
            # Rejects pure numbers, symbols, or garbage like "!!!" or "1234".
            _LOCATION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 .,'\-]{1,}$")
            if len(location) < 2 or not _LOCATION_RE.match(location):
                reply = (
                    "Please enter a valid city or region name — letters only, no symbols.  \n"
                    "*Examples: Ranchi, Pune, Ahmedabad, New Delhi*"
                )
                # Step stays at "location"
            else:
                st.session_state.run_data["location"] = location
                reply = (
                    f"Got it - **{location}**. 📍\n\n"
                    "**What growth stage is your crop at right now?**  \n"
                    "*Choose one: Seedling · Vegetative · Flowering · Harvest*"
                )
                st.session_state.step = "stage"

        # ── Step 3: stage → validate → run agent ─────────────────────────────
        elif step == "stage":
            stage = cleaned.title()

            # Fuzzy match first — resolves "seedling stage", "flowering phase", etc.
            if stage not in _VALID_STAGES:
                stage = _fuzzy_stage(cleaned) or stage

            # Reject invalid stages - keep asking until we get a valid one
            if stage not in _VALID_STAGES:
                reply = (
                    f"**{stage}** isn't a growth stage I recognise. 🌱\n\n"
                    "Please choose one of:\n\n"
                    "- **Seedling** - young plant, just germinated\n"
                    "- **Vegetative** - actively growing leaves and stems\n"
                    "- **Flowering** - producing flowers or setting fruit\n"
                    "- **Harvest** - ready or near-ready to harvest"
                )
                # Step stays at "stage" - do not advance

            else:
                crop     = st.session_state.run_data.get("crop", "your crop")
                location = st.session_state.run_data.get("location", "your location")
                st.session_state.run_data["stage"] = stage

                with st.chat_message("assistant", avatar="🌾"):
                    with st.spinner(f"Fetching today's weather for {location} and building your farm plan…"):
                        res = api_post(
                            "/agent/run",
                            {"crop": crop, "location": location, "stage": stage},
                            auth=True,
                        )

                # ── Error: network / server unreachable ───────────────────────
                if "_friendly_error" in res:
                    reply = f"⚠️ {res['_friendly_error']}"
                    # Keep run_data so user can retry without re-entering crop/location

                # ── Error: location not found or weather failure ───────────────
                # main.py now raises HTTP 422 when weather.temp is None, so
                # "detail" will be present and "llm_summary" will NOT be in res.
                elif "detail" in res and "llm_summary" not in res:
                    detail = res["detail"]
                    if "not found" in detail.lower() or "location" in detail.lower():
                        reply = (
                            f"Hmm, I couldn't find **{location}** in the weather database. 🗺️\n\n"
                            "Could you try a nearby larger city? For example, if you typed a small "
                            "village name, try the nearest district town instead."
                        )
                        # Keep step at "location" - user only needs to re-enter the city,
                        # not start over from crop selection.
                        st.session_state.step = "location"
                    else:
                        # Shows the actual message from the backend — could be
                        # an invalid crop rejection (Gemini's message) or a
                        # general weather failure string. Either way it appears
                        # as a chat bubble, not a red error box.
                        reply = detail
                        # Reset fully — user re-enters from crop
                        st.session_state.step     = "crop"
                        st.session_state.run_data = {}

                # ── Success ───────────────────────────────────────────────────
                else:
                    w       = res.get("weather", {})
                    actions = res.get("actions", [])

                    temp_val = w.get("temp")
                    rain_val = w.get("precip")
                    hum_val  = w.get("humidity")

                    temp_icon = "🥵" if (temp_val or 0) > 35 else ("🌤️" if (temp_val or 0) > 25 else "🌡️")
                    rain_icon = "🌧️" if (rain_val or 0) > 1 else "☀️"
                    hum_icon  = "💧" if (hum_val or 0) > 75 else "🌬️"

                    weather_html = (
                        f"<div class='weather-strip'>"
                        f"<span>{temp_icon} <strong>{temp_val}°C</strong> Temperature</span>"
                        f"<span>{rain_icon} <strong>{rain_val} mm</strong> Rain expected</span>"
                        f"<span>{hum_icon} <strong>{hum_val}%</strong> Humidity</span>"
                        f"</div>"
                    )

                    cards_html = "\n".join(render_action_card(a) for a in actions)
                    llm_text   = res.get("llm_summary", "")

                    # Only show "AgriSense says:" when the LLM produced a real summary.
                    # If Gemini was unavailable, llm_summary is "" — we skip the section
                    # entirely rather than repeating the action cards as prose.
                    llm_section = (
                        f"---\n\n**AgriSense says:**\n\n> {llm_text}\n\n"
                        if llm_text.strip() else ""
                    )

                    reply = (
                        f"### Your farm plan for today 🗓️\n\n"
                        f"**{crop}** · {location} · *{stage} stage*\n\n"
                        f"{weather_html}\n\n"
                        f"---\n\n"
                        f"**What to do today:**\n\n"
                        f"{cards_html}\n\n"
                        f"{llm_section}"
                        f"---\n\n"
                        f"Would you like a plan for **another crop or location**?  \n"
                        f"Just tell me the crop name, or type `done` if you're all set. 👋"
                    )

                    st.session_state.step     = "crop"
                    st.session_state.run_data = {}

        else:
            reply = (
                "I didn't quite catch that. Let's start fresh - "
                "**which crop would you like guidance for?**"
            )
            st.session_state.step = "crop"

        with st.chat_message("assistant", avatar="🌾"):
            st.markdown(reply, unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
if st.session_state.token:
    show_chat()
else:
    show_auth()
