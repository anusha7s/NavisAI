# 🧠 NavisAI – Autonomous Browser Agent

## 🌟 Overview
NavisAI is an AI-powered browser agent that can observe web pages, plan actions using an LLM, and execute tasks automatically with minimal human intervention.

It bridges:
🧠 **AI reasoning** (LLM Groq)<br>🌐 **Browser interaction** (Chrome Extension)<br>⚙️ **Backend decision engine** (FastAPI)

## 🛡️ Security Features
To ensure the safety and robustness of the system, NavisAI includes industry-standard security features:
- **Authentication & Authorization**: API endpoints secured via OAuth2 with JWT tokens. Local SQLite database handles user state mapping.
- **Password Hashing**: User credentials are encrypted using bcrypt hashing (via `passlib`) before storage.
- **SQL Injection Prevention**: SQLite integrated with parameterized queries to prevent SQL injections.
- **Rate Limiting**: `SlowAPI` integration restricts excessive API hits (e.g. 10/minute for task planning) to prevent DDOS scenarios.
- **Robust Error Handling**: External REST API errors are safely caught, retried automatically with backoff timeouts, and bubbled up to the frontend UI gracefully instead of silently failing.

## ⚙️ How It Works
User Task → Backend (`/start_task`)<br>
          → Action → Browser (`content.js` + `background.js` loop)<br>
          → Result + Observation<br>
          → Backend (`/next_step`)<br>
          → Repeat until DONE
          
## 🏗 Architecture
[Popup UI] (Glassmorphism & Real-time status)
     ↓
[background.js]  ← Robust agent loop with automatic retries
     ↓
[content.js]     ← Executes actions (click, type, etc)
     ↓
[FastAPI Backend] ← Secured via JWT and Rate Limited
     ↓
[LLM (Groq API)]

## ✨ Key Features
🔹 AI-based task planning
🔹 Real-time page observation (DOM extraction)
🔹 Automated browser actions (click, type)
🔹 Iterative agent loop (plan → act → observe) with resilience
🔹 Structured JSON action system
🔹 Premium UI using Modern Web typography

## 🛠 Tech Stack
1. **Frontend**: HTML, Post-Vanilla CSS, JavaScript
2. **Extension**: Chrome Extension (Manifest V3)
3. **Backend**: FastAPI (Python), SQLite
4. **Security**: Passlib (Bcrypt), Python-JOSE (JWT), SlowAPI
5. **AI Model**: Groq API (Llama-3)
6. **Validation**: Pydantic

## 🚀 Getting Started

### 1. Clone Repo
```bash
git clone https://github.com/anusha7s/NavisAI.git
cd NavisAI
```

### 2. Backend
```bash
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload
```

### 3. Extension
1. Open Google Chrome and go to `chrome://extensions`
2. Enable **Developer Mode**
3. Click **Load unpacked** and select the `extension/` folder

## 📡 API Endpoints

### Auth
- `POST /register`: Register a local account. Rate Limited.
- `POST /token`: Get an OAuth2 JWT token. Rate Limited.

### Core Agent Operations
- `GET /health`: Health check.
- `POST /start_task`: Translates natural language into the first structured JSON browser action.
- `POST /next_step`: Given a page observation and past results, plans the next sequential action in the loop.

## ⚠️ Current Limitations
1. Still iterating on autonomous loop completion edge cases.
2. Limited actions (click, type, scroll, wait, navigate).
3. Needs broader integration testing across more SPAs.

## 🎯 Architectural Diagrams

<img width="1024" height="916" alt="image" src="https://github.com/user-attachments/assets/c49cf9ce-2361-4b76-a0f9-f1f3b99e0a98" />

<img width="414" height="1024" alt="image" src="https://github.com/user-attachments/assets/575ebf5d-87f6-42fd-94d9-5c9aa1aa7087" />

<img width="377" height="1527" alt="image" src="https://github.com/user-attachments/assets/ddb80be4-7c16-46d8-9bb9-971478162f1e" />
