# AgriSense - Setup Guide

## Prerequisites
- Python 3.11+ (tested on 3.11–3.14; see note below for 3.14)
- A free [MongoDB Atlas](https://cloud.mongodb.com) account (M0 free tier)
- A free [Gemini API key](https://aistudio.google.com) from Google AI Studio  
  *(Keys starting with `AQ.` require Gemini 3.x models — already configured)*

> **Python 3.14 users:** Set this env var **before** starting any Python process:
> ```bash
> export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
> ```
> Add it to `~/.zshrc` or `~/.bashrc` to make it permanent.

---

## 1. Clone and install

```bash
git clone https://github.com/capblack222/AgriSense-Agent.git
cd AgriSense-Agent
pip install -r requirements.txt
```

---

## 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
MONGODB_URL=mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/agrisense
SECRET_KEY=<any long random string>
GEMINI_API_KEY=<your Gemini API key>
```

Generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Run locally

**Backend** (from `agrisense/backend/`):
```bash
uvicorn main:app --reload --port 8000
```

**Frontend** (from `agrisense/frontend/`):
```bash
streamlit run app.py
```

Visit `http://localhost:8501` for the chat UI.  
Visit `http://localhost:8000/docs` for the interactive API docs.

---

## 4. Run with Docker

```bash
docker build -t agrisense .
docker run -p 8000:8000 --env-file .env agrisense
```

---

## 5. Cloud deployment (free tier)

| Service | Platform | Notes |
|---|---|---|
| Backend | [Railway](https://railway.app) or [Render](https://render.com) | Set env vars in dashboard; Dockerfile is ready |
| Frontend | [Streamlit Community Cloud](https://streamlit.io/cloud) | Connect GitHub repo, set `BACKEND_URL` to your deployed API URL |
| Database | MongoDB Atlas M0 | Already configured via `MONGODB_URL` |

**Before deploying the frontend**, set the `BACKEND_URL` environment variable (or Streamlit secret) to your deployed FastAPI URL — no code change needed.

---

## Supported Crops

Wheat · Tomato · Rice · Maize · Soybean · Cotton · Sugarcane

## Supported Growth Stages

Seedling · Vegetative · Flowering · Harvest
