"""
frontend/app.py — AgriSense Streamlit chat interface.

Two views:
    1. Login / Register  — collects credentials, stores JWT in session state
    2. Chat interface    — collects crop/location/stage, calls FastAPI, shows advice

Run locally with:
    streamlit run app.py

The BACKEND_URL below should match where your FastAPI server is running.
Change it to your deployed URL when going live.
"""

import streamlit as st
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_URL = "http://localhost:8000"   # change to deployed URL in production

st.set_page_config(
    page_title = "AgriSense 🌾",
    page_icon  = "🌾",
    layout     = "centered",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# Streamlit re-runs the entire script on every interaction.
# session_state persists values across those reruns.
# ---------------------------------------------------------------------------
if "token"      not in st.session_state: st.session_state.token      = None
if "user_email" not in st.session_state: st.session_state.user_email = None
if "messages"   not in st.session_state: st.session_state.messages   = []
if "step"       not in st.session_state: st.session_state.step       = "crop"
if "run_data"   not in st.session_state: st.session_state.run_data   = {}


# ---------------------------------------------------------------------------
# Helper: authenticated API call
# ---------------------------------------------------------------------------
def api_post(endpoint: str, payload: dict, auth: bool = False) -> dict:
    headers = {}
    if auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        r = httpx.post(f"{BACKEND_URL}{endpoint}", json=payload, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def api_get(endpoint: str, params: dict = {}) -> dict:
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        r = httpx.get(f"{BACKEND_URL}{endpoint}", params=params, headers=headers, timeout=30)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# View 1: Login / Register
# ---------------------------------------------------------------------------
def show_auth():
    st.title("🌾 AgriSense")
    st.caption("AI-powered daily farm guidance for smallholder farmers")
    st.divider()

    tab_login, tab_register = st.tabs(["Log In", "Create Account"])

    with tab_login:
        email    = st.text_input("Email",    key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log In", use_container_width=True):
            if email and password:
                res = api_post("/auth/login", {"email": email, "password": password})
                if "access_token" in res:
                    st.session_state.token      = res["access_token"]
                    st.session_state.user_email = email
                    st.success("Logged in!")
                    st.rerun()
                else:
                    st.error(res.get("detail", "Login failed. Check your credentials."))
            else:
                st.warning("Please enter your email and password.")

    with tab_register:
        email    = st.text_input("Email",           key="reg_email")
        password = st.text_input("Password (min 6)", type="password", key="reg_password")
        if st.button("Create Account", use_container_width=True):
            if email and password:
                res = api_post("/auth/register", {"email": email, "password": password})
                if "message" in res:
                    st.success("Account created! You can now log in.")
                else:
                    st.error(res.get("detail", "Registration failed."))
            else:
                st.warning("Please fill in both fields.")


# ---------------------------------------------------------------------------
# View 2: Chat interface
# ---------------------------------------------------------------------------
def show_chat():
    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"**Logged in as:** {st.session_state.user_email}")
        st.divider()

        # History panel
        if st.button("📋 Show my recent decisions"):
            history_res = api_get("/agent/history", {"n": 5})
            if "history" in history_res:
                entries = history_res["history"]
                if entries:
                    for entry in reversed(entries):
                        with st.expander(f"🌾 {entry['crop']} @ {entry['location']} — {entry['timestamp']}"):
                            ws = entry.get("weather_snapshot", {})
                            st.markdown(
                                f"**Stage:** {entry.get('stage', '—')}  \n"
                                f"**Temp:** {ws.get('temp')}°C  |  "
                                f"**Rain:** {ws.get('precip')} mm  |  "
                                f"**Humidity:** {ws.get('humidity')}%"
                            )
                            if entry.get("llm_summary"):
                                st.info(entry["llm_summary"])
                else:
                    st.info("No history yet — run a query first.")
            else:
                st.error("Could not load history.")

        st.divider()
        if st.button("🚪 Log Out"):
            for key in ["token", "user_email", "messages", "step", "run_data"]:
                st.session_state[key] = None if key == "token" else (
                    [] if key == "messages" else ({} if key == "run_data" else "crop")
                )
            st.rerun()

    # ── Main chat area ───────────────────────────────────────────────────────
    st.title("🌾 AgriSense")
    st.caption("Your daily AI-powered farm assistant")

    # Replay existing messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Start the conversation if it's fresh
    if not st.session_state.messages:
        greeting = (
            "Hello! I'm AgriSense, your farm assistant. 🌱\n\n"
            "I'll check today's weather and give you personalised guidance "
            "based on your crop and growth stage.\n\n"
            "**Which crop would you like guidance for?**  \n"
            "*(e.g. Wheat, Tomato, Rice, Maize, Soybean, Cotton, Sugarcane)*"
        )
        with st.chat_message("assistant"):
            st.markdown(greeting)
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        st.session_state.step = "crop"

    # ── Conversational input loop ─────────────────────────────────────────────
    user_input = st.chat_input("Type your answer here...")

    if user_input:
        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})

        step = st.session_state.step

        # Step 1: collect crop
        if step == "crop":
            st.session_state.run_data["crop"] = user_input.strip().title()
            reply = (
                f"Great — **{st.session_state.run_data['crop']}**! 🌾\n\n"
                "**Which city or region is your farm located in?**"
            )
            st.session_state.step = "location"

        # Step 2: collect location
        elif step == "location":
            st.session_state.run_data["location"] = user_input.strip()
            reply = (
                f"Got it — **{st.session_state.run_data['location']}**.\n\n"
                "**What is the current growth stage?**  \n"
                "*(Seedling / Vegetative / Flowering / Harvest)*"
            )
            st.session_state.step = "stage"

        # Step 3: collect stage → run agent
        elif step == "stage":
            st.session_state.run_data["stage"] = user_input.strip().title()

            with st.chat_message("assistant"):
                with st.spinner("Checking the weather and preparing your farm plan..."):
                    res = api_post(
                        "/agent/run",
                        {
                            "crop":     st.session_state.run_data["crop"],
                            "location": st.session_state.run_data["location"],
                            "stage":    st.session_state.run_data["stage"],
                        },
                        auth=True,
                    )

            if "error" in res and "llm_summary" not in res:
                reply = f"⚠️ Something went wrong: {res.get('error', 'Unknown error')}"
            else:
                w = res.get("weather", {})
                actions_md = "\n".join(f"{i+1}. {a}" for i, a in enumerate(res.get("actions", [])))
                reply = (
                    f"### 🌾 Farm Plan — {res['crop']} @ {res['location']} ({res['stage']} stage)\n\n"
                    f"**Current weather:**  \n"
                    f"🌡️ {w.get('temp')}°C  |  🌧️ {w.get('precip')} mm rain  |  💧 {w.get('humidity')}% humidity\n\n"
                    f"---\n\n"
                    f"**Today's recommendations:**\n\n{actions_md}\n\n"
                    f"---\n\n"
                    f"**AgriSense summary:**\n\n{res.get('llm_summary', '')}\n\n"
                    f"---\n\n"
                    f"Would you like guidance for **another crop**? Just tell me the crop name, "
                    f"or type `done` to finish."
                )
            st.session_state.step = "crop"   # reset for next query
            st.session_state.run_data = {}

        # Handle "done"
        elif user_input.strip().lower() in ["done", "no", "exit", "quit"]:
            reply = "Thanks for using AgriSense! Come back tomorrow for your next farm plan. 🌾"

        else:
            reply = "Sorry, I didn't catch that. Which crop would you like guidance for?"
            st.session_state.step = "crop"

        with st.chat_message("assistant"):
            st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
# Router: show auth or chat based on login state
# ---------------------------------------------------------------------------
if st.session_state.token:
    show_chat()
else:
    show_auth()
