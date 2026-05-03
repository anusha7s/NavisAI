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
    action_type: str           # click, type, navigate, submit, scroll, wait, select_option, press_key, ask_user, done
    target: Optional[str] = ""
    value: Optional[Any] = None
    confidence: float = 0.5
    needs_user_input: bool = False
    explanation: str = ""

class PlanResponse(BaseModel):
    plan: List[ActionPlan]

class ActionResult(BaseModel):
    success: bool
    error: Optional[str] = None

class ActionHistoryItem(BaseModel):
    action: ActionPlan
    result: ActionResult

class NextStepRequest(BaseModel):
    task: str
    observation: PageObservation
    last_action: Optional[ActionPlan] = None
    result: Optional[ActionResult] = None
    history: Optional[List[ActionHistoryItem]] = []