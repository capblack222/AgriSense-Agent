# 🌾 AgriSense Agent  
### Turning Weather Data Into Actionable Farm Decisions  
*A personalized, explainable AI agent helping smallholder farmers make smarter daily choices.*

## 📌 Overview  
AgriSense is an AI-powered farm advisory platform that transforms real-time weather data into crop-specific, stage-aware farming recommendations. The project combines weather intelligence, agronomy-inspired decision rules, persistent farm memory, and AI reasoning to help farmers make more informed decisions about irrigation, fertilization, and crop management.

The idea was originally developed as a capstone project during the **Google × Kaggle AI Agents Intensive (2025)**, where I explored agentic workflows, tool integration, and memory-driven AI systems. Since then, AgriSense has evolved into a production-ready, full-stack application built for scalability, data isolation, and low-latency performance.


### 🛠️ Core Architectural Focus

* **RAG-Grounded Recommendations:** Retrieves crop-specific agronomic knowledge (irrigation thresholds, pest names, heat limits) from a local vector index at query time, injecting it into every Gemini prompt to ground advice in verified agronomy data rather than model weights alone.
* **Agentic Weather Intelligence:** Fetches live Open-Meteo forecast data and runs weather fetch + RAG retrieval concurrently via `asyncio.gather`, keeping latency low while gathering full context before LLM reasoning.
* **State & Memory Management:** Utilises a decoupled MongoDB architecture to maintain multi-turn, multi-seasonal farm history across stateless API sessions.
* **Production-Grade Guardrails:** JWT-based user isolation, FastAPI Pydantic input validation, and async pipeline design — no blocking calls in the request path.
* **Technology Stack:** FastAPI, MongoDB Atlas, Gemini 3.1 Flash Lite (REST API), AWS Bedrock Titan Embeddings V2, Chroma, Open-Meteo API.


### ❤️ The "Why" Behind AgriSense

This project holds deep personal significance for me. Growing up, I watched farmers in my ancestral village in Kanpur navigate unpredictable weather patterns and limited access to timely, expert agricultural guidance. A single mistimed fertilization or irrigation cycle could decimate an entire season's yield. 

Those experiences inspired my long-term goal of engineering accessible technology that bridges the gap between complex data and rural communities. AgriSense is a pragmatic step toward that vision-turning enterprise-level AI capabilities into actionable, real-world utility for the people who need it most.

## 🌟 Key Features

### 🤖 Interactive Farm Assistant
- Conversational chat UI (Streamlit) with colour-coded recommendation cards
- Validated input flow: crop → location → growth stage → personalised plan
- Fetches real-time weather on every query

### 🌦️ Weather Intelligence
Powered by the [Open-Meteo API](https://open-meteo.com/) - free, no key required.

### 🧠 Persistent Memory
Farm history stored in **MongoDB Atlas** per user account. Sessions survive restarts - your decisions are always there when you come back.

### 🪪 Transparent Rule Engine
Crop-specific and **growth-stage-aware** agronomy logic for irrigation, heat stress, and fungal/pest risk. Thresholds shift based on whether your crop is at Seedling, Vegetative, Flowering, or Harvest stage.

### 🧩 LLM Reasoning Layer ✅
**Gemini 3.1 Flash Lite** (via direct REST API — no SDK) reasons over live weather data to produce a farmer-friendly daily plan. Falls back gracefully to the rule engine if the API is unavailable. A lightweight crop-name validation call also runs at the crop input step to reject non-crops instantly.

### 🔐 Authentication
JWT-based stateless auth (register + login). Passwords hashed with bcrypt + SHA-256 pre-hashing.

### 🧭 End-to-End Orchestration
FastAPI backend runs weather fetch and RAG knowledge retrieval **concurrently**, then passes both to Gemini for grounded reasoning, and persists the result to MongoDB — all in a single async pipeline per request.

---

## 🏛️ Architecture
```
Streamlit (frontend/app.py)
  ↓ HTTP via httpx
FastAPI (backend/main.py)
  ├── /agent/validate-crop   lightweight crop name check (no auth)
  ├── /agent/run             full pipeline (auth required)
  ├── /agent/history         user decision history (auth required)
  ├── auth.py        JWT register / login
  └── agent.py       Orchestrator
        ├── weather.py   Open-Meteo API → live forecast           ┐ concurrent
        ├── rag/         Knowledge retrieval → agronomic context   ├ asyncio.gather
        │     └── Bedrock Titan V2 → Chroma → top-5 chunks        ┘
        ├── gemini.py    Gemini 3.1 Flash Lite → reasoning + summary (primary)
        │     └── Prompt = weather + RAG context → grounded advice
        ├── rules.py     Crop + stage rule engine (fallback when Gemini unavailable)
        └── memory.py    MongoDB read/write (per-user history)

MongoDB Atlas          ← persistent farm memory (users + decision history)
Chroma (local disk)    ← RAG vector index (built once via ingest.py)
AWS Bedrock            ← Titan Embeddings V2 (query-time embedding)
```

---

## 🗣️ Example Interaction
Conversation-style flow with crop → location → stage → personalized plan.  
Includes weather fetch, irrigation decisions, fungal/pest alerts, and history summaries.

---

## 🔧 Tools & Technologies

| Layer | Technology |
|---|---|
| LLM | Gemini 3.1 Flash Lite (REST API via httpx — no SDK, Python 3.14 compatible) |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit + extra-streamlit-components (cookie auth persistence) |
| Database | MongoDB Atlas + Motor (async driver) |
| Auth | python-jose (JWT) + bcrypt + SHA-256 pre-hash |
| Weather | Open-Meteo API (free, no key) |
| RAG | AWS Bedrock Titan Embeddings V2 + Chroma (local) |
| HTTP client | httpx (Gemini calls + weather) |
| Container | Docker |
| Language | Python 3.11–3.14 (3.14 requires `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`) |

---

## 🚀 Probable Future Extensions
- IoT soil sensors  
- Voice + local language interface  
- Seasonal planning  
- WhatsApp/Android integration  
- Pest prediction models  

---

## 🏅 Google AI Agents Intensive  
✔ Built a full agent workflow  
✔ Tools + memory + orchestration  
✔ Multi-agent concepts  
✔ Evaluation + observability  
✔ Capstone submitted + Kaggle badge  

---

## 📁 Repository Structure
```
agrisense/
  backend/
    main.py              FastAPI routes + CORS + health check
    agent.py             Orchestrator (weather + RAG + Gemini + memory, concurrent)
    rules.py             Crop + stage-aware decision engine (Gemini fallback)
    weather.py           Open-Meteo API wrapper (async httpx)
    gemini.py            Gemini LLM synthesis layer (REST API, no SDK)
    memory.py            MongoDB-backed FarmMemory
    auth.py              JWT auth + bcrypt password hashing
    database.py          Motor async MongoDB client (singleton)
    models.py            Pydantic request/response models
    rag/
      __init__.py        Public API: Retriever
      chunker.py         Load .txt docs → overlapping chunks (~600 chars)
      embedder.py        AWS Bedrock Titan Embeddings V2 → 1024-dim vectors
      vector_store.py    Chroma persistent index (build + query)
      retriever.py       Clean retrieve(query) → list[dict] interface
      ingest.py          One-time script: load KB → embed → store Chroma
      chroma_index/      Auto-created by ingest.py (git-ignored)
  frontend/     
    app.py               Streamlit chat UI
  knowledge_base/
    wheat_guide.txt
    rice_guide.txt
    tomato_maize_guide.txt
    cotton_soybean_sugarcane_guide.txt
  tests/ 
    test_gemini.py       Gemini + validate_crop tests
    test_rules.py        Rule engine tests
    test_weather.py      Async weather API tests
    test_retriever.py    Chunker unit tests + RAG eval harness
    eval_qa_pairs.json   30 QA pairs for retrieval quality evaluation
agrisense-agent-code-jupyter-nb.ipynb   original capstone notebook
Dockerfile
requirements.txt
.env.example
```

## ⚙️ Setup

See **[docs/setup.md](docs/setup.md)** for full local and cloud deployment instructions.

---

## 🔗 Links  
**Kaggle Notebook:**  
https://www.kaggle.com/code/capblack222/agrisense-agent  

---

## 💛 Personal Note  
AgriSense is a small but meaningful step toward using technology for rural impact - inspired by the farmers in my village whose resilience shaped my journey.

#### To read in-depth about it, please go to [Kaggle Writeup](https://www.kaggle.com/competitions/agents-intensive-capstone-project/writeups/new-writeup-1764611812766)
