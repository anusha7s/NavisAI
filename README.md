🧠 NavisAI – Autonomous Browser Agent

🌟 Overview

NavisAI is an AI-powered browser agent that can observe web pages, plan actions using an LLM, and execute tasks automatically with minimal human intervention.

It bridges:

🧠 AI reasoning (LLM)<br>🌐 Browser interaction (Chrome Extension)<br>⚙️ Backend decision engine (FastAPI)

⚙️ How It Works
User Task → Backend (/start_task)<br>
          → Action → Browser (content.js)<br>
          → Result + Observation<br>
          → Backend (/next_step)<br>
          → Repeat until DONE<br>
          
🏗 Architecture
[Popup UI]
     ↓
[background.js]  ← agent loop
     ↓
[content.js]     ← executes actions (click, type)
     ↓
[FastAPI Backend]
     ↓
[LLM (Groq)]

✨ Key Features<br>
🔹 AI-based task planning<br>
🔹 Real-time page observation (DOM extraction)<br>
🔹 Automated browser actions (click, type)<br>
🔹 Iterative agent loop (plan → act → observe)<br>
🔹 Structured JSON action system

🧠 Agent Workflow
1. User enters task
2. Backend generates action
3. Browser executes action
4. Result is captured
5. Next action is generated
6. Loop continues until "done"

🛠 Tech Stack
1. Frontend: HTML, CSS, JavaScript
2. Extension: Chrome Extension (Manifest V3)
3. Backend: FastAPI (Python)
4. AI Model: Groq API
5. Validation: Pydantic

🚀 Getting Started
1. Clone Repo
git clone https://github.com/anusha7s/NavisAI.git
cd NavisAI
2. Backend
pip install -r requirements.txt
uvicorn main:app --reload
3. Extension
Open chrome://extensions
Enable Developer Mode
Load extension/ folder

📡 API
/start_task

Generates first action

/next_step

Generates next action based on:

observation
last action
result

⚠️ Current Limitations
1. Limited actions (click, type only)
2. Partial multi-step loop
3. No retry/error handling
4. No tests yet

🚀 Future Improvements
1. Full autonomous loop completion
2. More actions (submit, scroll, wait)
3. Better UI state handling
4. Retry + timeout system
5. Test coverage


🎯 1. Architecture Diagram

<img width="1024" height="916" alt="image" src="https://github.com/user-attachments/assets/c49cf9ce-2361-4b76-a0f9-f1f3b99e0a98" />


🎯 2. Agent Workflow Diagram

<img width="414" height="1024" alt="image" src="https://github.com/user-attachments/assets/575ebf5d-87f6-42fd-94d9-5c9aa1aa7087" />


🎯 3. Data Flow Diagram

<img width="377" height="1527" alt="image" src="https://github.com/user-attachments/assets/ddb80be4-7c16-46d8-9bb9-971478162f1e" />

