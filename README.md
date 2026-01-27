# 🌾 AgriSense Agent  
### Turning Weather Data Into Actionable Farm Decisions  
*A personalized, explainable AI agent helping smallholder farmers make smarter daily choices.*

## 📌 Overview  
AgriSense is my capstone project from the **Google x Kaggle AI Agents Intensive (2025)** - a 5-day deep dive into agentic system design, memory, tools, and multi-agent workflows.

This project holds deep meaning for me. Growing up, I watched farmers in my ancestral village in Kanpur struggle with unpredictable weather and limited access to timely advice. Those experiences shaped my long-term goal of building tech that empowers rural communities.

**AgriSense is designed for exactly that purpose.**  
It converts raw weather forecasts into **clear, crop-specific, stage-aware farm recommendations** using AI agents.

## 🌟 Key Features

### 🤖 Interactive Farm Assistant
- Asks intuitive questions  
- Fetches real-time weather  
- Generates daily personalized guidance  
- Remembers previous sessions  

### 🌦️ Weather Intelligence
Powered by the Open-Meteo API.

### 🧠 Context + Memory
Stores crop, stage, past alerts, and weather snapshots.

### 🪪 Transparent Rule Engine
Agronomy-inspired decision logic for irrigation, heat stress, and pest risk.

### 🧩 LLM Reasoning Layer
Combines weather + rules + memory → simple, actionable advice.

### 🧭 End-to-End Orchestration
Handles workflow, user input, memory updates, and logging.

---

## 🏛️ Architecture
```
User
  ↓
Orchestrator Agent
  ↓
Weather Tool → Rule Engine → Memory Store
  ↓
LLM Reasoner
  ↓
Output Layer (JSON + Natural Summary)
```

---

## 🗣️ Example Interaction
Conversation-style flow with crop → location → stage → personalized plan.  
Includes weather fetch, irrigation decisions, fungal/pest alerts, and history summaries.

---

## 🔧 Tools & Technologies
- Google AI Studio (Gemini)  
- ADK (Agent Development Kit)  
- Python  
- Open-Meteo API  
- JSON output logs  
- Notebook-based memory system  

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
notebooks/
capstone/
screenshots/
README.md
```

---

## 🔗 Links  
**Kaggle Notebook:**  
https://www.kaggle.com/code/capblack222/agrisense-agent  

---

## 💛 Personal Note  
AgriSense is a small but meaningful step toward using technology for rural impact — inspired by the farmers in my village whose resilience shaped my journey.

#### To read in-depth about it, please go to [Kaggle Writeup] (https://www.kaggle.com/competitions/agents-intensive-capstone-project/writeups/new-writeup-1764611812766)
