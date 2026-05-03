import os
import json
import re
import time
import asyncio
import sqlite3
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from pydantic import BaseModel

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta

from groq import AsyncGroq
from models import TaskRequest, Observation, ActionPlan, NextStepRequest

load_dotenv()

# --- Security & Auth Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-for-jwt")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- Database setup (SQL Injection Prevention) ---
DB_NAME = "navisai.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user_db(username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, hashed_password FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return {"username": user[0], "hashed_password": user[1]}
    return None

def create_user_db(username: str, hashed_password: str):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

# Dependency to get current logged in user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_db(username=username)
    if user is None:
        raise credentials_exception
    return user

# --- AI Setup ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in environment")

client = AsyncGroq(api_key=GROQ_API_KEY)
# Model switched to 8B to avoid strict Groq rate limits (6000 TPM limit on 70B)
MODEL_NAME = "llama-3.1-8b-instant" 

def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    match = re.search(r"\{[\s\S]*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

# --- FastAPI with Rate Limiting (SlowAPI) ---
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="NavisAI Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

SYSTEM_PROMPT = """
You are NavisAI - an autonomous browser agent with dynamic vision.
Given a user task and the current screen observation, decide the SINGLE next browser action to take.

You MUST respond with ONLY a valid JSON object, no other text, in EXACTLY this format:
{
  "action_type": "navigate",
  "target": "https://www.google.com",
  "value": null,
  "confidence": 0.95,
  "explanation": "Navigate to Google to search for the query"
}

Rules:
- action_type must be EXACTLY one of: navigate, click, type, submit, scroll, wait, select_option, press_key, ask_user, done
- target: for navigate = full URL; for element interactions (click, type, submit, scroll) use the exact 'selector' from the CURRENT observation's 'buttons' or 'inputs' array. NEVER reuse selectors from your Action History — old selectors are dead!
- value: the text to type (for type action ONLY), wait ms (for wait), option text (for select_option), key name (for press_key)
- confidence: a number between 0.0 and 1.0
- explanation: THIS IS YOUR MEMORY SCRATCHPAD. Write down any data you find here. Example: "Amazon price for Ear Muffs is ₹1295. Now going to Flipkart."

CRITICAL RULES:
1. "type" action means typing into a search/input field. The "value" field is ONLY for the user's search query (e.g. "Ear Muffs for Noise Reduction"). NEVER type instructions or sentences into a search bar! Only type the actual product name!
2. There is NO "read" action! Reading is automatic — you can already see all page data in the 'page_text' field. When you see prices in page_text, just write them in your 'explanation' and immediately output your NEXT real action (navigate to next site, or ask_user with your final answer).
3. PRICE COMPARISON WORKFLOW:
   Step A: Navigate to site 1 (e.g. amazon.in)
   Step B: Type the product name into the search bar (the form auto-submits)
   Step C: Search results are now visible in page_text. Note the prices in your explanation. Output action_type="navigate" to site 2.
   Step D: Type the product name into site 2's search bar
   Step E: Search results visible in page_text. Output action_type="ask_user" with your full price comparison in the explanation field.
4. If your previous action failed, just look at the NEW observation and continue from the current page state.
5. If you encounter a CAPTCHA or login wall, output ask_user to let the user handle it.
- Do NOT include any text outside the JSON object
- Do NOT use markdown, code blocks, explanations before/after JSON
"""

# Auth Endpoints
class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, user: UserCreate):
    hashed_password = get_password_hash(user.password)
    success = create_user_db(user.username, hashed_password)
    if not success:
        raise HTTPException(status_code=400, detail="Username already registered")
    return {"message": "User registered successfully"}

@app.post("/token")
@limiter.limit("5/minute")
async def login_for_access_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user_db(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request):
    return {"status": "ok", "provider": "groq", "model": MODEL_NAME}

from fastapi.responses import StreamingResponse
from sse_manager import sse_manager
from agent import execute_task

@app.get("/step_result")
async def step_result(task: str, step_id: str, success: str, error: str = ""):
    from agent import active_tasks
    if task in active_tasks and "event" in active_tasks[task]:
        active_tasks[task]["result"] = {
            "success": success.lower() == "true",
            "error": error
        }
        active_tasks[task]["event"].set()
    return {"status": "received"}

@app.post("/observation_result")
async def observation_result(request: Request):
    data = await request.json()
    task = data.get("task")
    from agent import active_tasks
    if task in active_tasks and "event" in active_tasks[task]:
        active_tasks[task]["result"] = {
            "success": True,
            "observation": data.get("observation")
        }
        active_tasks[task]["event"].set()
    return {"status": "received"}

@app.post("/resume_task")
async def resume_task(request: Request):
    data = await request.json()
    task = data.get("task")
    user_reply = data.get("reply")
    
    from agent import execute_task, active_tasks
    if task in active_tasks and "paused_at" in active_tasks[task]:
        # Restart loop with a strong directive to execute the choice and not pause again
        new_prompt = task + f"\n\nCRITICAL SYSTEM OVERRIDE: You previously paused and asked the user for input. The user replied with: '{user_reply}'. Your new plan MUST NOT include an 'ask_user' step. Immediately execute the exact choice the user specified."
        asyncio.create_task(execute_task(new_prompt))
        return {"status": "resuming"}
    return {"status": "error", "message": "Task not found or not paused"}

@app.get("/stream_task")
async def stream_task(request: Request, task: str):
    queue = sse_manager.connect(task)
    
    # Start the agent execution in the background
    asyncio.create_task(execute_task(task))
    
    return StreamingResponse(sse_manager.event_generator(task), media_type="text/event-stream")

async def generate_next_step(req: NextStepRequest):
    obs = req.observation
    page_summary = (
        f"URL: {obs.url}\n"
        f"Title: {obs.title}\n"
        f"Page text (READ THIS TO FIND PRICES):\n{obs.page_text[:6000]}\n\n"
        f"Clickable Buttons/Links: {json.dumps(obs.buttons[:60])}\n"
        f"Input Fields: {json.dumps(obs.inputs)}"
    )

    action_context = ""
    if req.history and len(req.history) > 0:
        action_context += f"\nAction History ({len(req.history)} past steps):\n"
        for i, item in enumerate(req.history):
            action_context += f"Step {i+1}: {item.action.action_type} on '{item.action.target}'. Result: {'Success' if item.result.success else 'Failed'}. Memory: {item.action.explanation}\n"
    elif req.last_action:
        action_context += f"\nLast Action Attempted:\n{req.last_action.model_dump_json(indent=2)}\n"
        if req.result:
            action_context += f"Action Result:\n{req.result.model_dump_json(indent=2)}\n"

    full_prompt = f"""
User Task: {req.task}
{action_context}
Current page state:
{page_summary}

Decide the SINGLE next action. Remember:
- To READ data, just look at the page text above. Do NOT type anything to read data.
- "type" action is ONLY for typing a product name into a search bar. Never type instructions.
- When you see prices in the page text, write them in your explanation and navigate to the next site.
- When you have all prices, use ask_user to tell the user the comparison result.

Do not add markdown, explanations, code blocks or any text outside the JSON.
"""

    for attempt in range(1, 4):
        try:
            print(f"[NEXT_STEP attempt {attempt}] Page URL: {req.observation.url}")

            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"}
            )

            raw_text = response.choices[0].message.content.strip()
            print("[NEXT_STEP DEBUG RAW RESPONSE START]")
            print(raw_text)
            print("[NEXT_STEP DEBUG RAW RESPONSE END]")
            print("─" * 90)

            try:
                action_dict = json.loads(raw_text)
            except json.JSONDecodeError:
                action_dict = json.loads(extract_json(raw_text))

            action_obj = ActionPlan(**action_dict)

            valid_types = {"navigate", "click", "type", "submit", "scroll", "wait", "select_option", "press_key", "ask_user", "done"}
            # If LLM outputs "read", treat it as a no-op — the data is already in the explanation
            if action_obj.action_type == "read":
                action_obj.action_type = "wait"
                action_obj.value = "500"
            elif action_obj.action_type not in valid_types:
                raise ValueError(f"Invalid action_type: {action_obj.action_type}")

            return action_obj

        except Exception as e:
            print(f"[NEXT_STEP GENERAL ERROR attempt {attempt}]: {str(e)}")
            if attempt == 3:
                raise Exception(f"Groq call failed in next_step: {str(e)}")
            await asyncio.sleep(2)

    raise Exception("next_step logic failed after all retries")

@app.post("/next_step")
@limiter.limit("20/minute")
async def next_step_endpoint(request: Request, req: NextStepRequest):
    try:
        return await generate_next_step(req)
    except Exception as e:
        raise HTTPException(500, str(e))



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)