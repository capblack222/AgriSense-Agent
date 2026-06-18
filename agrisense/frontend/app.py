"""
frontend/app.py — AgriSense Streamlit chat interface.

Farmer-friendly UI with:
  - Warm earthy colour scheme (set in .streamlit/config.toml)
  - Colour-coded recommendation cards (irrigation / heat / humidity / stage)
  - Plain-language error messages — no stack traces shown to the user
  - Persistent session history in the sidebar

Run locally:
    streamlit run app.py

Change BACKEND_URL to your deployed FastAPI URL when going live.
"""

import streamlit as st
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title = "AgriSense — Your Farm Assistant",
    page_icon  = "🌾",
    layout     = "centered",
)

# ---------------------------------------------------------------------------
# Shared CSS — colour-coded recommendation cards
# Each card type maps to a keyword in the action text.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Shared card base */
.card {
    border-radius: 10px;
    padding: 12px 16px;
    margin: 6px 0;
    font-size: 15px;
    line-height: 1.5;
}
/* Irrigation — calm blue */
.card-irrigation {
    background-color: #d0eaf8;
    border-left: 5px solid #2196f3;
    color: #0d2d45;
}
/* Heat alert — warm orange */
.card-heat {
    background-color: #fde8cc;
    border-left: 5px solid #e07b00;
    color: #3d1f00;
}
/* Humidity / fungal — muted purple */
.card-humidity {
    background-color: #ede0f5;
    border-left: 5px solid #8e44ad;
    color: #2d0c40;
}
/* Stage note — soft green */
.card-stage {
    background-color: #d6edd8;
    border-left: 5px solid #40916c;
    color: #0d2e18;
}
/* General / fallback — warm grey */
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
# Helper: classify an action string into a card type
# ---------------------------------------------------------------------------
def _card_type(action: str) -> str:
    lower = action.lower()
    if "irrigat" in lower or "water" in lower or "rain" in lower:
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
    # Strip the "[Stage] " prefix if present — the card colour already signals stage
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
                "Your session expired. Please log in again — it only takes a second.",
        }.get(detail, detail)
        st.error(f"⚠️ {friendly}")


# ---------------------------------------------------------------------------
# View 1 — Login / Register
# ---------------------------------------------------------------------------
def show_auth():
    st.markdown(
        "<h1 style='text-align:center; color:#40916c;'>🌾 AgriSense</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; color:#6b5b3e; font-size:17px;'>"
        "Your daily AI-powered farm guide — personalised to your crop, location, and growth stage."
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
                    st.success("Welcome back! Loading your dashboard…")
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
    st.caption("AgriSense — built for smallholder farmers. Inspired by the villages of Kanpur.")


# ---------------------------------------------------------------------------
# View 2 — Main chat interface
# ---------------------------------------------------------------------------
def show_chat():

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"**Logged in as**  \n{st.session_state.user_email}")
        st.divider()
        st.markdown("#### 📋 Recent Decisions")

        if st.button("Load my history", use_container_width=True):
            with st.spinner("Fetching your recent decisions…"):
                history_res = api_get("/agent/history", {"n": 5})

            if "_friendly_error" in history_res:
                st.error(history_res["_friendly_error"])
            elif "history" in history_res:
                entries = history_res["history"]
                if not entries:
                    st.info("No decisions yet — run your first query to get started!")
                else:
                    for entry in reversed(entries):
                        ws = entry.get("weather_snapshot", {})
                        label = f"🌾 {entry['crop']} @ {entry['location']}"
                        with st.expander(label):
                            st.caption(entry.get("timestamp", ""))
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Temp",     f"{ws.get('temp', '—')}°C")
                            col2.metric("Rain",     f"{ws.get('precip', '—')} mm")
                            col3.metric("Humidity", f"{ws.get('humidity', '—')}%")
                            if entry.get("llm_summary"):
                                st.info(entry["llm_summary"])
            else:
                st.error("Couldn't load your history right now. Try again in a moment.")

        st.divider()
        if st.button("🚪  Log Out", use_container_width=True):
            for k, v in defaults.items():
                st.session_state[k] = v
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
            "*Examples: Wheat, Tomato, Rice, Maize, Soybean, Cotton, Sugarcane*"
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

        _EXIT_WORDS      = {"done", "no", "exit", "quit", "thanks", "thank you", "bye", "stop"}
        _VALID_STAGES    = {"Seedling", "Vegetative", "Flowering", "Harvest"}
        # Keep in sync with CROP_CONFIG in backend/rules.py
        _SUPPORTED_CROPS = {"Wheat", "Tomato", "Rice", "Maize", "Soybean", "Cotton", "Sugarcane"}

        # ── EXIT KEYWORDS — must be checked FIRST, before any step logic ─────
        # Previously this was an elif after step checks, making it unreachable:
        # step is always "crop", "location", or "stage", so the elif never fired.
        if cleaned.lower() in _EXIT_WORDS:
            reply = (
                "You're all set for today! 🌾\n\n"
                "Come back tomorrow and I'll check the weather again and update your farm plan. "
                "Wishing you a great harvest! 🌻"
            )
            st.session_state.step     = "crop"
            st.session_state.run_data = {}

        # ── Step 1: crop ─────────────────────────────────────────────────────
        elif step == "crop":
            crop = cleaned.title()
            crops_display = " · ".join(sorted(_SUPPORTED_CROPS))
            if crop not in _SUPPORTED_CROPS:
                reply = (
                    f"I don't have data for **{crop}** yet. 🌱\n\n"
                    f"I currently support these crops:\n\n"
                    f"**{crops_display}**\n\n"
                    "Please type one of the above."
                )
                # Step stays at "crop"
            else:
                st.session_state.run_data["crop"] = crop
                reply = (
                    f"Great — **{crop}**! 🌿\n\n"
                    "**Which city or region is your farm in?**  \n"
                    "*For example: Ranchi, Pune, Ahmedabad, Lucknow…*"
                )
                st.session_state.step = "location"

        # ── Step 2: location ─────────────────────────────────────────────────
        elif step == "location":
            location = cleaned
            if len(location) < 2:
                reply = "Please enter a valid city or region name — for example: Ranchi, Pune, Ahmedabad."
            else:
                st.session_state.run_data["location"] = location
                reply = (
                    f"Got it — **{location}**. 📍\n\n"
                    "**What growth stage is your crop at right now?**  \n"
                    "*Choose one: Seedling · Vegetative · Flowering · Harvest*"
                )
                st.session_state.step = "stage"

        # ── Step 3: stage → validate → run agent ─────────────────────────────
        elif step == "stage":
            stage = cleaned.title()

            # Reject invalid stages — keep asking until we get a valid one
            if stage not in _VALID_STAGES:
                reply = (
                    f"**{stage}** isn't a growth stage I recognise. 🌱\n\n"
                    "Please choose one of:\n\n"
                    "- **Seedling** — young plant, just germinated\n"
                    "- **Vegetative** — actively growing leaves and stems\n"
                    "- **Flowering** — producing flowers or setting fruit\n"
                    "- **Harvest** — ready or near-ready to harvest"
                )
                # Step stays at "stage" — do not advance

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
                elif "detail" in res and "llm_summary" not in res:
                    detail = res["detail"]
                    if "not found" in detail.lower() or "location" in detail.lower():
                        reply = (
                            f"Hmm, I couldn't find **{location}** in the weather database. 🗺️\n\n"
                            "Could you try a nearby larger city? For example, if you typed a small "
                            "village name, try the nearest district town instead."
                        )
                    else:
                        reply = (
                            "Something went wrong fetching the weather data. "
                            "Please try again in a moment — these things sometimes fix themselves!"
                        )
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

                    reply = (
                        f"### Your farm plan for today 🗓️\n\n"
                        f"**{crop}** · {location} · *{stage} stage*\n\n"
                        f"{weather_html}\n\n"
                        f"---\n\n"
                        f"**What to do today:**\n\n"
                        f"{cards_html}\n\n"
                        f"---\n\n"
                        f"**AgriSense says:**\n\n"
                        f"> {llm_text}\n\n"
                        f"---\n\n"
                        f"Would you like a plan for **another crop or location**?  \n"
                        f"Just tell me the crop name, or type `done` if you're all set. 👋"
                    )

                    st.session_state.step     = "crop"
                    st.session_state.run_data = {}

        else:
            reply = (
                "I didn't quite catch that. Let's start fresh — "
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
