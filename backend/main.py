import os
import json
import re
import time
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

from groq import AsyncGroq

from models import TaskRequest, Observation, ActionPlan, NextStepRequest

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in environment")

client = AsyncGroq(api_key=GROQ_API_KEY)

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
- action_type must be EXACTLY one of: navigate, click, type, submit, scroll, wait, select_option, press_key, done
- target: for navigate = full URL; for all element interactions (click, type, submit, scroll, select_option) ALWAYS explicitly use the EXACT 'selector' from the observation if available, otherwise fallback to text/description; for scroll also "up"/"down"; for press_key = key name
- value: text to type (for type), wait duration in ms (for wait), option text (for select_option), key name (for press_key)
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
async def next_step(req: NextStepRequest):
    obs = req.observation
    page_summary = (
        f"URL: {obs.url}\n"
        f"Title: {obs.title}\n"
        f"Page text snippet: {obs.page_text[:1200]}\n"
        f"Buttons/Links: {json.dumps(obs.buttons[:15])}\n"
        f"Inputs: {json.dumps(obs.inputs)}"
    )

    action_context = ""
    if req.last_action:
        action_context += f"\nLast Action Attempted:\n{req.last_action.model_dump_json(indent=2)}\n"
    if req.result:
        action_context += f"\nAction Result:\n{req.result.model_dump_json(indent=2)}\n"

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