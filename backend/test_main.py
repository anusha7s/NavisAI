import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@patch("main.client.chat.completions.create")
def test_start_task(mock_create):
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "action_type": "navigate",
        "target": "https://google.com",
        "value": None,
        "confidence": 0.95,
        "explanation": "Go to Google homepage"
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_create.return_value = mock_response

    response = client.post("/start_task", json={"task": "Search GLA University"})
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "planning"
    assert data["plan"]["action_type"] == "navigate"
    assert data["plan"]["target"] == "https://google.com"

@patch("main.client.chat.completions.create")
def test_next_step(mock_create):
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "action_type": "type",
        "target": "#searchBox",
        "value": "GLA University",
        "confidence": 0.9,
        "explanation": "Type the query in search box"
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_create.return_value = mock_response

    sample_input = {
        "task": "Search GLA University",
        "observation": {
            "url": "https://google.com",
            "title": "Google",
            "page_text": "Search the web...",
            "buttons": [{"text": "Search", "selector": "#btnSearch"}],
            "inputs": [{"type": "text", "placeholder": "Search", "selector": "#searchBox"}]
        },
        "last_action": {
            "action_type": "navigate",
            "target": "https://google.com",
            "value": None,
            "confidence": 0.95,
            "explanation": "Navigated to website"
        },
        "result": {
            "success": True,
            "error": None
        }
    }
    
    response = client.post("/next_step", json=sample_input)
    assert response.status_code == 200
    data = response.json()
    
    assert data["action_type"] == "type"
    assert data["target"] == "#searchBox"
    assert data["value"] == "GLA University"

@patch("main.client.chat.completions.create")
def test_start_task_invalid_type(mock_create):
    # Test fallback extraction or failure scenario
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "action_type": "fly", # Invalid action type
        "target": "sky"
    })
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_create.return_value = mock_response

    response = client.post("/start_task", json={"task": "Fly to sky"})
    # Should fail due to Pydantic/manual validation raising ValueError inside main.py
    # FastAPI returns 500 when raising raw exceptions not caught as HTTPExceptions, except here attempt catches it and returns 500 after max retries
    assert response.status_code == 500
