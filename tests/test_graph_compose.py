from __future__ import annotations

import pytest

from app.graph import compose_assistant_reply
from app.state import empty_conversational_state


@pytest.mark.asyncio
async def test_compose_reply_asks_when_gaps_remain() -> None:
    st = empty_conversational_state()
    st["conversation"] = [{"role": "user", "content": "Something happened"}]
    st["extracted_facts"] = {
        "location": "",
        "date": "",
        "incident_type": "",
        "injuries": "",
    }
    st["missing_fields"] = []
    st["next_question"] = ""
    st["logs"] = []

    out = await compose_assistant_reply(st)
    assert out["missing_fields"]
    assert out["next_question"]
    assert "👉" not in out["assistant_reply"]
    assert len(out["assistant_reply"].strip()) > 10


@pytest.mark.asyncio
async def test_compose_reply_completes_when_facts_full() -> None:
    st = empty_conversational_state()
    st["conversation"] = [{"role": "user", "content": "full story"}]
    st["extracted_facts"] = {
        "location": "Austin",
        "date": "2026-01-01",
        "incident_type": "car accident",
        "injuries": "none",
    }
    st["missing_fields"] = []
    st["logs"] = []

    out = await compose_assistant_reply(st)
    assert "enough information" in out["assistant_reply"].lower() or "brief" in out["assistant_reply"].lower()
    assert out["assistant_reply"].count("?") == 0 or "refine" in out["assistant_reply"].lower()
