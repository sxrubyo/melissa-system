"""Tests for melissa_admin_api.py"""
import sys
import os
sys.path.insert(0, ".")

os.environ.setdefault("MASTER_API_KEY", "test_key_123")
os.environ.setdefault("ADMIN_API_KEY", "test_key_123")

from fastapi.testclient import TestClient
from melissa_admin_api import router as admin_router
from fastapi import FastAPI

app = FastAPI()
app.include_router(admin_router)
client = TestClient(app)

HEADERS = {"X-Admin-Key": "test_key_123"}


def test_persona_override_applies():
    resp = client.post(
        "/admin/test_instance/persona",
        headers=HEADERS,
        json={
            "tone": "formal",
            "verbosity": "concise",
            "greeting_style": "Buenos dias",
            "sign_off": "Saludos cordiales",
            "forbidden_topics": ["precios"],
            "escalation_phrases": ["no se"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["applied"]["tone"] == "formal"


def test_model_override():
    resp = client.post(
        "/admin/test_instance/model",
        headers=HEADERS,
        json={
            "provider": "gemini",
            "model_id": "gemini-2.5-flash",
            "temperature": 0.7,
            "max_tokens": 2048,
            "thinking_budget": 0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True


def test_status_endpoint():
    resp = client.get("/admin/test_instance/status", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "persona" in data
    assert "model" in data


def test_teach_endpoint():
    resp = client.post(
        "/admin/test_instance/teach",
        headers=HEADERS,
        json={
            "question": "cuanto cuesta el botox",
            "answer": "desde 800.000 COP la unidad",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_unauthorized_returns_401():
    resp = client.get("/admin/test_instance/status", headers={"X-Admin-Key": "wrong"})
    assert resp.status_code == 401


def test_gaps_endpoint():
    resp = client.get("/admin/test_instance/gaps", headers=HEADERS)
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
    assert "gaps" in resp.json()
