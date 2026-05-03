import asyncio
from sse_manager import sse_manager
from models import Observation, NextStepRequest, ActionPlan, ActionResult

# In a real app, this state would be persisted in a DB
active_tasks = {}

async def execute_task(task_text: str):
    from main import generate_next_step
    try:
        await sse_manager.send_message(task_text, {"type": "step_update", "step_id": "planning", "text": "Initializing dynamic agent...", "status": "active"})
        
        history = []
        last_action = None
        
        while True:
            step_idx = len(history)
            step_id = f"step_{step_idx}"
            
            # 1. Ask frontend for DOM observation
            await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": "Scanning page...", "status": "active"})
            await sse_manager.send_message(task_text, {"type": "get_observation", "step_id": step_id})
            
            event = asyncio.Event()
            active_tasks[task_text] = {"event": event, "result": None}
            await asyncio.wait_for(event.wait(), timeout=15.0)
            
            obs_data = active_tasks[task_text].get("result")
            if not obs_data or not obs_data.get("success"):
                raise Exception("Failed to get DOM observation")
            
            from models import PageObservation
            obs_obj = PageObservation(**obs_data.get("observation", {}))
            
            # 2. Generate Next Step
            await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": "Analyzing screen and thinking...", "status": "active"})
            req = NextStepRequest(task=task_text, observation=obs_obj, history=history, last_action=last_action)
            action = await generate_next_step(req)
            
            desc = f"{action.action_type} {action.target or ''}"
            await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": desc, "status": "active", "confidence": action.confidence})
            
            if action.action_type == "done":
                await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": f"Completed: {desc}", "status": "done"})
                break
                
            if action.action_type == "ask_user":
                await sse_manager.send_message(task_text, {"type": "ask_user", "text": action.explanation or "I need your input. Please type your response."})
                # Pause execution
                active_tasks[task_text] = {"paused_at": step_idx, "history": history, "last_action": action}
                return
                
            # 3. Execute Action
            # Use dict to send to sidebar
            await sse_manager.send_message(task_text, {"type": "execute_action", "step_id": step_id, "action": action.model_dump()})
            
            event = asyncio.Event()
            active_tasks[task_text] = {"event": event, "result": None}
            await asyncio.wait_for(event.wait(), timeout=20.0)
            
            result_data = active_tasks[task_text].get("result", {})
            action_result = ActionResult(success=result_data.get("success", False), error=result_data.get("error"))
            
            if action_result.success:
                await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": f"Completed: {desc}", "status": "done"})
            else:
                await sse_manager.send_message(task_text, {"type": "step_update", "step_id": step_id, "text": f"Failed: {action_result.error}", "status": "fail"})
                # Let the ReAct loop handle the failure! Do not crash.
                
            from models import ActionHistoryItem
            history.append(ActionHistoryItem(action=action, result=action_result))
            last_action = action

        await sse_manager.send_message(task_text, {"type": "done", "step_id": "final"})
        
    except Exception as e:
        await sse_manager.send_message(task_text, {"type": "error", "error": str(e)})
