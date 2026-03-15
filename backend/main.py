import os
import json
import re
import time
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

from groq import Groq

from models import TaskRequest, Observation, ActionPlan

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in .env file! Please add your Groq API key.")

client = Groq(api_key=GROQ_API_KEY)

# Powerful, fast, and high free-tier allowance
MODEL_NAME = "llama-3.3-70b-versatile" 

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

app = FastAPI(title="NavisAI Backend")

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
- action_type must be EXACTLY one of: navigate, click, type, done
- target: for navigate = full URL; for click = button/link text; for type = input field description/placeholder
- value: text to type (only for action_type=type), otherwise null
- confidence: a number between 0.0 and 1.0
- explanation: short reason for this action
- When the task is fully complete, use action_type = "done"
- Do NOT include any text outside the JSON object
- Do NOT use markdown, code blocks, explanations before/after JSON
"""

@app.get("/health")
async def health():
    return {"status": "ok", "provider": "groq", "model": MODEL_NAME}

@app.post("/start_task")
async def start_task(req: TaskRequest):
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
            
            response = client.chat.completions.create(
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

            plan_dict = json.loads(raw_text)

            if "action_type" not in plan_dict or plan_dict["action_type"] not in ["navigate", "click", "type", "done"]:
                raise ValueError("Invalid or missing action_type")

            return {"status": "planning", "plan": plan_dict}

        except Exception as e:
            print(f"[GENERAL ERROR attempt {attempt}]: {str(e)}")
            if attempt == 3:
                raise HTTPException(500, detail=f"Groq API call failed: {str(e)}")
            time.sleep(2)

    raise HTTPException(500, "All attempts failed")

@app.post("/next_step")
async def next_step(obs: Observation):
    page_summary = (
        f"URL: {obs.url}\n"
        f"Title: {obs.title}\n"
        f"Page text snippet: {obs.page_text[:1200]}\n"
        f"Visible buttons/links: {obs.visible_buttons[:15]}\n"
        f"Forms: {obs.forms}"
    )

    full_prompt = f"""
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

Do not add markdown, explanations, code blocks or any text outside the JSON.
"""

    for attempt in range(1, 4):
        try:
            print(f"[NEXT_STEP attempt {attempt}] Page URL: {obs.url}")

            response = client.chat.completions.create(
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

            action_dict = json.loads(raw_text)

            if "action_type" not in action_dict:
                raise ValueError("Missing 'action_type' in response")

            valid_types = {"navigate", "click", "type", "done"}
            if action_dict["action_type"] not in valid_types:
                raise ValueError(f"Invalid action_type: {action_dict['action_type']}")

            return ActionPlan(**action_dict)

        except Exception as e:
            print(f"[NEXT_STEP GENERAL ERROR attempt {attempt}]: {str(e)}")
            if attempt == 3:
                raise HTTPException(
                    status_code=500,
                    detail=f"Groq call failed in next_step: {str(e)}"
                )
            time.sleep(2)

    raise HTTPException(500, "next_step endpoint failed after all retries")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)