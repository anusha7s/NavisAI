from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
import google.generativeai as genai
from dotenv import load_dotenv
import os
import json
import re

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI(title="NavisAI Backend - Autonomous Web Agent")

class PlanRequest(BaseModel):
    task: str
    page_context: str = ""
    mode: str = "general"
    previous_outcome: str = ""

class PlanResponse(BaseModel):
    reasoning: str
    next_action: str
    confidence: int                 # 0-100
    is_safe: bool
    explanation: str
    is_task_complete: bool = False

@app.post("/plan", response_model=PlanResponse)
async def generate_plan(req: PlanRequest):
    raw_text = None
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",  # Change to gemini-2.5-pro if you enable billing
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,  # Low for format consistency
                # top_p=0.95,     # Uncomment if needed
                # max_output_tokens=800,
            ),
            safety_settings={
                genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            }
        )

        system_prompt = f"""
You are NavisAI: a safe, explainable, autonomous web agent.
STRICT RULES:
- NEVER propose actions involving passwords, payments, credit cards, personal data submission, login attempts, or bypassing security.
- If any action seems unsafe or restricted, set is_safe=false and explain why in explanation field.
- Output **ONLY** valid JSON object. No extra text, no markdown, no code blocks like ```json, no comments.
- Use **exactly** these keys and no others:
  - "reasoning": Step-by-step thinking about the page and task (string)
  - "next_action": SINGLE precise action in format e.g. "TYPE|text|selector", "CLICK|selector", "NAVIGATE|url", "SCROLL|down/up"
  - "confidence": integer 0-100
  - "is_safe": boolean true/false
  - "explanation": full human-readable explanation including safety check (string)
  - "is_task_complete": boolean – true ONLY if task is fully achieved based on current context

Example correct output:
{{
  "reasoning": "Page shows search bar filled. Next step is to submit.",
  "next_action": "CLICK|button[type=\\\"submit\\\"], button:has-text(\\\"Search\\\")",
  "confidence": 92,
  "is_safe": true,
  "explanation": "Safe click on public search button. No sensitive data involved.",
  "is_task_complete": false
}}

Mode: {req.mode}
Task: {req.task}
Current page context: {req.page_context[:4000]}  # truncated to avoid token limits
Previous outcome (if any): {req.previous_outcome}

Respond with JSON only matching the above structure.
"""

        response = model.generate_content(system_prompt)

        # Extract raw text safely
        raw_text = (response.text or "").strip()

        print("Raw Gemini output:", raw_text)
        print("Response finish reason:", response.candidates[0].finish_reason if response.candidates else "No candidates")
        print("Safety ratings:", response.candidates[0].safety_ratings if response.candidates else "None")

        # Clean common wrappers Gemini sometimes adds
        raw_text = re.sub(r'^```json\s*|\s*```$', '', raw_text).strip()
        raw_text = re.sub(r'^```|\s*```$', '', raw_text).strip()

        if not raw_text or raw_text == "{}" or len(raw_text) < 20:
            print("WARNING: Empty or too small response from Gemini")
            fallback = {
                "reasoning": "Gemini returned empty/invalid response – possible safety block, token limit, or generation failure.",
                "next_action": "PAUSE|wait for user or retry",
                "confidence": 0,
                "is_safe": False,
                "explanation": "Generation failed. Check API status, safety filters, or reduce context length.",
                "is_task_complete": False
            }
            return PlanResponse(**fallback)

        data = json.loads(raw_text)

        # Defensive key normalization (in case of capitalization differences)
        normalized = {
            "reasoning": data.get("reasoning") or data.get("Reasoning") or "",
            "next_action": data.get("next_action") or data.get("NextAction") or data.get("action") or "",
            "confidence": data.get("confidence") or 50,
            "is_safe": data.get("is_safe") if isinstance(data.get("is_safe"), bool) else True,
            "explanation": data.get("explanation") or data.get("Explanation") or "No explanation provided",
            "is_task_complete": data.get("is_task_complete", False),
        }

        return PlanResponse(**normalized)

    except json.JSONDecodeError as jde:
        print("JSON decode failed:", str(jde))
        raise HTTPException(status_code=500, detail=f"Invalid JSON from Gemini\nRaw: {raw_text[:600]}...")
    except ValidationError as ve:
        print("Pydantic validation failed:", ve.errors())
        raise HTTPException(status_code=422, detail=f"Invalid response structure\nErrors: {ve.errors()}\nRaw: {raw_text[:600]}...")
    except Exception as e:
        print("Unexpected error:", str(e))
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}\nRaw output was: {raw_text[:600]}...")


@app.get("/models")
async def list_models():
    try:
        models = genai.list_models()
        return {"available_models": [m.name for m in models]}
    except Exception as e:
        return {"error": str(e)}