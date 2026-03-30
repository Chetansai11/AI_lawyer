from __future__ import annotations

from app.agents.auditor import suggest_next_question


def test_suggest_next_question_priority_date() -> None:
    q = suggest_next_question(["date", "location", "injuries"], {})
    assert "date" in q.lower() or "Date" in q


def test_suggest_next_question_incident_type() -> None:
    q = suggest_next_question(["incident_type"], {})
    assert "incident" in q.lower()


def test_suggest_next_question_empty_missing() -> None:
    assert suggest_next_question([], {}) == ""
