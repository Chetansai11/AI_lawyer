from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.state import empty_conversational_state


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_welcome_returns_message() -> None:
    client = TestClient(app)
    response = client.get("/welcome")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert len(data["message"]) > 20


def test_chat_returns_reply_brief_session() -> None:
    merged = empty_conversational_state()
    merged["conversation"] = [{"role": "user", "content": "test"}]
    merged["extracted_facts"] = {
        "location": "Austin",
        "date": "2026-01-01",
        "incident_type": "car accident",
        "injuries": "none",
    }
    merged["missing_fields"] = []
    merged["assumptions"] = []
    merged["risk_analysis"] = "ok"
    merged["case_score"] = 7.0
    merged["confidence_score"] = 0.9
    merged["lawyer_matches"] = []
    merged["next_question"] = ""
    merged["plausibility"] = "high"
    merged["logs"] = ["[TEST] log line"]

    async def _fake_pipeline(state):
        return merged

    with (
        patch("app.controller.run_pipeline", new_callable=AsyncMock, side_effect=_fake_pipeline),
    ):
        client = TestClient(app)
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "brief" in data
    assert "logs" in data
    assert "session_id" in data
    assert "## Attorney Brief" in data["brief"]
    assert data["logs"]
    assert data.get("case_score") == 7.0
    assert "lawyer_matches" in data
