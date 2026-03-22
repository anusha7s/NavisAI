from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class TaskRequest(BaseModel):
    task: str

class PageObservation(BaseModel):
    url: str
    title: str
    page_text: str
    buttons: List[Dict[str, Any]]
    inputs: List[Dict[str, Any]]

class Observation(BaseModel):
    task: str
    url: str
    title: str
    page_text: str
    buttons: List[Dict[str, Any]]
    inputs: List[Dict[str, Any]]

class ActionPlan(BaseModel):
    action_type: str           # click, type, navigate, submit, scroll, wait, select_option, press_key, done
    target: Optional[str] = ""
    value: Optional[str] = None
    confidence: float = 0.5
    explanation: str = ""

class ActionResult(BaseModel):
    success: bool
    error: Optional[str] = None

class NextStepRequest(BaseModel):
    task: str
    observation: PageObservation
    last_action: Optional[ActionPlan] = None
    result: Optional[ActionResult] = None