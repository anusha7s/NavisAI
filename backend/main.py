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
You are NavisAI - an autonomous browser agent.
Given a user task, decide the SINGLE next browser action to take.

You MUST respond with ONLY a valid JSON object, no other text, in EXACTLY this format:
{
  "action_type": "navigate",
  "target": "https://www.google.com",
  "value": null,
  "confidence": 0.95,
  "explanation": "Navigate to Google to search for the query"
}

Rules:
- action_type must be EXACTLY one of: navigate, click, type, submit, scroll, wait, select_option, press_key, done
- target: for navigate = full URL; for all element interactions (click, type, submit, scroll, select_option) prioritize explicitly using the exact 'text' from the observation (e.g. "Book tickets"). Only use 'selector' if text is unavailable; for scroll also "up"/"down"; for press_key = key name
- value: text to type (for type), wait duration in ms (for wait), option text (for select_option), key name (for press_key)
- confidence: a number between 0.0 and 1.0
- explanation: short reason for this action
- If the task is purely informational or just navigating to a site with NO further instructions, output action_type = "done" when reached. Otherwise, CONTINUE step-by-step until the complete user goal is achieved. Break down complex tasks into multiple sequential steps.
- When the final goal of the user's task is fully achieved, output action_type = "done".
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

@app.post("/start_task")
@limiter.limit("10/minute")
async def start_task(request: Request, req: TaskRequest): # (Optionally add `current_user: dict = Depends(get_current_user)` here)
    full_prompt = f"""
User Task: {req.task}

Output **only** the JSON object for the FIRST action. No other text, no markdown.
Example:
{{
  "action_type": "navigate",
  "target": "https://www.google.com",
  "value": null,
  "confidence": 0.95,
  "explanation": "Go to Google homepage"
}}
"""

    for attempt in range(1, 4):
        try:
            print(f"[DEBUG attempt {attempt}] Task: {req.task}")
            
            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.1,
                max_tokens=300,
                response_format={"type": "json_object"} # Groq supports Guaranteed JSON Mode!
            )

            raw_text = response.choices[0].message.content.strip()
            print("[DEBUG RAW GROQ RESPONSE START]")
            print(raw_text)
            print("[DEBUG RAW GROQ RESPONSE END]")
            print("─" * 80)

            try:
                plan_dict = json.loads(raw_text)
            except json.JSONDecodeError:
                plan_dict = json.loads(extract_json(raw_text))

            plan_obj = ActionPlan(**plan_dict)

            if plan_obj.action_type not in ["navigate", "click", "type", "submit", "scroll", "wait", "select_option", "press_key", "done"]:
                raise ValueError(f"Invalid action_type: {plan_obj.action_type}")

            return {"status": "planning", "plan": plan_obj.model_dump()}

        except Exception as e:
            print(f"[GENERAL ERROR attempt {attempt}]: {str(e)}")
            if attempt == 3:
                raise HTTPException(500, detail=f"Groq API call failed: {str(e)}")
            await asyncio.sleep(2)

    raise HTTPException(500, "All attempts failed")

@app.post("/next_step")
@limiter.limit("20/minute")
async def next_step(request: Request, req: NextStepRequest):
    obs = req.observation
    page_summary = (
        f"URL: {obs.url}\n"
        f"Title: {obs.title}\n"
        f"Page text snippet: {obs.page_text[:1200]}\n"
        f"Buttons/Links: {json.dumps(obs.buttons[:50])}\n"
        f"Inputs: {json.dumps(obs.inputs)}"
    )

    action_context = ""
    if req.history and len(req.history) > 0:
        action_context += f"\nAction History ({len(req.history)} past steps):\n"
        for i, item in enumerate(req.history):
            action_context += f"Step {i+1}: Attempted {item.action.action_type} on '{item.action.target}'. Result: {'Success' if item.result.success else 'Failed (' + str(item.result.error) + ')'}\n"
    elif req.last_action:
        action_context += f"\nLast Action Attempted:\n{req.last_action.model_dump_json(indent=2)}\n"
        if req.result:
            action_context += f"Action Result:\n{req.result.model_dump_json(indent=2)}\n"

    full_prompt = f"""
User Task: {req.task}
{action_context}
Current page state:
{page_summary}

Decide the SINGLE next action (or "done" if task is complete).

Examples:
{{
  "action_type": "type",
  "target": "search box",
  "value": "GLA University Mathura",
  "confidence": 0.88,
  "explanation": "Enter search query"
}}

{{
  "action_type": "click",
  "target": "Google Search",
  "value": null,
  "confidence": 0.9,
  "explanation": "Click the search button"
}}

{{
  "action_type": "done",
  "target": null,
  "value": null,
  "confidence": 1.0,
  "explanation": "The user merely asked to open the site, and the site is loaded."
}}

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

            valid_types = {"navigate", "click", "type", "submit", "scroll", "wait", "select_option", "press_key", "done"}
            if action_obj.action_type not in valid_types:
                raise ValueError(f"Invalid action_type: {action_obj.action_type}")

            return action_obj

        except Exception as e:
            print(f"[NEXT_STEP GENERAL ERROR attempt {attempt}]: {str(e)}")
            if attempt == 3:
                raise HTTPException(
                    status_code=500,
                    detail=f"Groq call failed in next_step: {str(e)}"
                )
            await asyncio.sleep(2)

    raise HTTPException(500, "next_step endpoint failed after all retries")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)