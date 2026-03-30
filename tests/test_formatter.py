from __future__ import annotations

from app.state import empty_conversational_state
from app.utils.formatter import format_brief_markdown


def test_format_brief_contains_sections() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {
        "location": "Dallas",
        "date": "2026-03-01",
        "incident_type": "slip and fall",
        "injuries": "sprained ankle",
    }
    st["missing_fields"] = []
    st["assumptions"] = [{"text": "Test assumption", "confidence": 0.7}]
    st["risk_analysis"] = "Early triage only."
    st["case_score"] = 6.5
    st["confidence_score"] = 0.8
    st["plausibility"] = "high"
    st["lawyer_matches"] = [
        {"name": "Jane Doe", "specialty": "personal injury", "location": "Dallas", "score": 0.9}
    ]
    st["next_question"] = ""

    md = format_brief_markdown(st)
    assert "## Attorney Brief" in md
    assert "### Summary" in md
    assert "Dallas" in md
    assert "Disclaimer" in md
    assert "legal advice" in md.lower()
    assert "### Key Facts" in md
    assert "### Detailed Summary for Counsel" in md
    assert "### Case Analysis" in md
    assert "slip and fall" in md
    assert "### Case Score" not in md
    assert "### Confidence" not in md
    assert "internal triage score" not in md.lower()
    assert "6.5" not in md
    assert "Jane Doe" in md


def test_format_brief_shows_gaps_in_summary() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {
        "location": "",
        "date": "",
        "incident_type": "",
        "injuries": "",
    }
    st["missing_fields"] = []
    st["plausibility"] = "low"
    md = format_brief_markdown(st)
    assert "gaps" in md.lower() or "location" in md.lower()
    assert "Disclaimer" in md
    assert "### Case Analysis" in md
