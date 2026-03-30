from __future__ import annotations

from app.state import empty_conversational_state
from app.utils.gaps import effective_missing_fields


def test_effective_missing_all_empty_facts() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {
        "location": "",
        "date": "",
        "incident_type": "",
        "injuries": "",
    }
    gaps = effective_missing_fields(st)
    assert set(gaps) == {"location", "date", "incident_type", "injuries"}


def test_effective_missing_partial_facts() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {
        "location": "Austin",
        "date": "",
        "incident_type": "car accident",
        "injuries": "whiplash",
    }
    assert effective_missing_fields(st) == ["date"]


def test_effective_missing_adds_liability_from_auditor() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {
        "location": "Austin",
        "date": "2026-01-01",
        "incident_type": "car accident",
        "injuries": "none",
    }
    st["missing_fields"] = ["liability"]
    assert "liability" in effective_missing_fields(st)


def test_effective_missing_dedupes_order() -> None:
    st = empty_conversational_state()
    st["extracted_facts"] = {"location": "", "date": "", "incident_type": "", "injuries": ""}
    st["missing_fields"] = ["liability"]
    out = effective_missing_fields(st)
    assert out.count("liability") == 1
    assert out.index("liability") == len(out) - 1
