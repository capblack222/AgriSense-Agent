# 🌱 AgriSense Agent

An AI-powered farm advisory platform that transforms real-time weather data into crop-specific recommendations for farmers.

AgriSense combines weather intelligence, agronomy-based decision rules, persistent farm memory, and secure user management to deliver personalized farming guidance through a conversational interface.

---

## 📖 Overview

Farmers often rely on fragmented information when making critical decisions regarding irrigation, fertilization, and crop management. AgriSense bridges this gap by converting real-time weather forecasts into actionable recommendations tailored to specific crops and growth stages.

The platform uses:

* Real-time weather data from Open-Meteo
* Crop-specific decision logic
* Growth-stage-aware recommendations
* Persistent farm memory
* Secure JWT-based authentication
* Interactive conversational interface

Inspired by agricultural challenges observed in rural communities, AgriSense focuses on helping farmers make informed decisions using accessible technology.

---

## ✨ Features

### 🌦️ Weather Intelligence

* Real-time weather forecasts
* Temperature monitoring
* Rainfall prediction
* Humidity tracking
* Location-based weather retrieval

### 🌾 Crop-Aware Decision Engine

* Crop-specific recommendation rules
* Growth-stage modifiers
* Irrigation guidance
* Fertilization recommendations
* Weather risk alerts

### 🧠 Persistent Farm Memory

* MongoDB-backed storage
* Historical recommendation tracking
* User-specific farm records
* Long-term advisory history

### 🔐 Secure Authentication

* User registration and login
* Password hashing with bcrypt
* JWT-based authentication
* Protected API endpoints

### 💬 Conversational Interface

* Streamlit chat experience
* Simple advisory workflow
* Historical recommendation sidebar
* Interactive user experience

---

## 🏗️ Architecture

```text
┌─────────────────────────┐
│   Streamlit Frontend    │
└─────────────┬───────────┘
              │
         HTTP + JWT
              │
              ▼

┌─────────────────────────┐
│     FastAPI Backend     │
└─────────────┬───────────┘
              │
              ▼

┌─────────────────────────┐
│       Farm Agent        │
└─────────────┬───────────┘
              │
     ┌────────┼────────┐
     │        │        │
     ▼        ▼        ▼

Weather   Decision   Memory
Service    Engine    Service

     │                 │
     ▼                 ▼

Open-Meteo         MongoDB
```

---

## 📂 Project Structure

```text
agrisense-agent/
│
├── backend/
│   ├── agent.py
│   ├── auth.py
│   ├── database.py
│   ├── memory.py
│   ├── models.py
│   ├── rules.py
│   ├── weather.py
│   └── main.py
│
├── frontend/
│   └── app.py
│
├── requirements.txt
└── README.md
```

---

## ⚙️ How It Works

### Step 1

User logs into the platform.

### Step 2

The frontend sends a request containing:

* Crop
* Location
* Growth Stage

### Step 3

The backend:

* Retrieves weather data from Open-Meteo
* Applies crop-specific decision rules
* Generates recommendations

### Step 4

Results are stored in MongoDB for future reference.

### Step 5

Recommendations are returned and displayed in the chat interface.

---

## 🛠️ Technology Stack

### Backend

* FastAPI
* Python
* Pydantic
* JWT Authentication

### Database

* MongoDB
* Motor (Async MongoDB Driver)

### Frontend

* Streamlit

### External APIs

* Open-Meteo Weather API

### Security

* bcrypt
* python-jose

---

## 🔌 API Endpoints

### Authentication

| Method | Endpoint         | Description                 |
| ------ | ---------------- | --------------------------- |
| POST   | `/auth/register` | Register a new user         |
| POST   | `/auth/login`    | Login and receive JWT token |

### Agent

| Method | Endpoint         | Authentication |
| ------ | ---------------- | -------------- |
| POST   | `/agent/run`     | Required       |
| GET    | `/agent/history` | Required       |

---

## 📝 Example Workflow

Input:

```json
{
  "crop": "wheat",
  "location": "Pune",
  "stage": "flowering"
}
```

Output:

```json
{
  "recommendations": [
    "Reduce irrigation due to expected rainfall.",
    "Monitor humidity-related fungal risks.",
    "Avoid fertilizer application before rain."
  ]
}
```

---

## ✅ Current Progress

### Completed

* Modular project architecture
* FastAPI backend
* Streamlit frontend
* MongoDB integration
* Persistent farm memory
* JWT authentication
* Password hashing
* Open-Meteo weather integration
* Crop recommendation engine
* Historical recommendation tracking

### Currently Building

* LLM-powered recommendation layer
* Context-aware memory retrieval
* Dockerized deployment
* AWS cloud deployment

---

## 🚀 Future Enhancements

### AI Features

* LLM-based agricultural reasoning
* Multi-tool agent architecture
* Context-aware memory
* Agricultural knowledge retrieval

### Cloud Features

* Docker containers
* AWS ECS Fargate deployment
* Amazon ECR
* AWS Secrets Manager
* CI/CD with GitHub Actions
* CloudWatch monitoring

### Product Features

* Multi-farm management
* Crop analytics dashboard
* SMS notifications
* Mobile-friendly experience
