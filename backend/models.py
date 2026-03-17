from pydantic import BaseModel
from typing import List, Optional

class TaskRequest(BaseModel):
    task: str

class Observation(BaseModel):
    task: str
    url: str
    title: str
    page_text: str
    visible_buttons: List[str]
    forms: List[str]

class ActionPlan(BaseModel):
    action_type: str           # click, type, navigate, done
    target: Optional[str] = ""
    value: Optional[str] = None
    confidence: float = 0.5
    explanation: str = ""