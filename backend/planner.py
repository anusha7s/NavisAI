import os
import json
import re
from groq import AsyncGroq
from models import PlanResponse

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.1-8b-instant"

def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
    match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text

async def generate_plan(task: str) -> dict:
    prompt = f"""
You are an autonomous browser agent. Break this task into precise sequential steps.
Task: "{task}"

CRITICAL RULES:
1. If the task requires opening or using a specific website, your VERY FIRST step MUST be `navigate` with the full correct URL (e.g., "https://in.bookmyshow.com", "https://www.google.com"). Do not assume the browser is already on the correct page.
2. Only output the JSON array. No other text.

For each step specify:
- action_type (navigate / click / type / select_option / scroll / wait)
- target (Be extremely literal. Use EXACT visible text you expect to see on the page, e.g., 'From', 'To', 'Search'. DO NOT hallucinate generic names like 'Flight search form' or 'Submit area'. Keep it short and precise.)
- value (what to type or select if needed)
- confidence (0 to 1)
- needs_user_input (true/false - set true if agent needs user to provide info like payment, OTP, login)
- explanation (short reasoning)

Output MUST be a valid JSON object containing a "plan" array:
{{
  "plan": [
    {{
      "action_type": "navigate",
      "target": "https://www.makemytrip.com",
      "value": null,
      "confidence": 0.95,
      "needs_user_input": false,
      "explanation": "Go to MakeMyTrip homepage"
    }}
  ]
}}
"""
    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": "You are a precise JSON planner agent."},
                  {"role": "user", "content": prompt}],
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    
    raw = response.choices[0].message.content.strip()
    try:
        data = json.loads(extract_json(raw))
        # Validate against Pydantic
        PlanResponse(**data)
        return data
    except Exception as e:
        print("Plan generation error:", str(e), "RAW:", raw)
        raise ValueError("Failed to generate valid plan.")
