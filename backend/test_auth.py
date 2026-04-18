from fastapi.testclient import TestClient
import sqlite3
import os
from main import app, DB_NAME

client = TestClient(app)

def setup_module(module):
    # Setup test DB if needed
    if os.path.exists(DB_NAME):
        pass

def teardown_module(module):
    # Optional cleanup
    pass

def test_register_user():
    # Attempt to register a test user
    response = client.post("/register", json={"username": "testuser", "password": "testpassword123"})
    assert response.status_code in [200, 400] # 400 if already exists

def test_login_user():
    # Login the user
    response = client.post("/token", data={"username": "testuser", "password": "testpassword123", "grant_type": "password"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_invalid_login():
    response = client.post("/token", data={"username": "wronguser", "password": "wrongpassword", "grant_type": "password"})
    assert response.status_code == 401
