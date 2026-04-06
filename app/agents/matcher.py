from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from app.state import ConversationalState, LawyerMatch, empty_conversational_state
from app.utils.logger import agent_log

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "lawyers.json"


def _slugify(name: str) -> str:
    out: list[str] = []
    for ch in name.lower().strip():
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_"):
            out.append("-")
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-") or "attorney"


def _score_lawyer(lawyer: dict[str, Any], facts: dict[str, Any]) -> float:
    score = 0.0
    incident = str(facts.get("incident_type", "")).lower()
    location = str(facts.get("location", "")).lower()
    specialties = [s.lower() for s in lawyer.get("specialties", [])]

    if incident and any(incident in spec or spec in incident for spec in specialties):
        score += 0.65
    elif specialties:
        score += 0.25

    if location and location in str(lawyer.get("location", "")).lower():
        score += 0.25

    score += min(0.1, float(lawyer.get("rating", 0)) / 50.0)
    return round(score, 3)


async def run_matcher(state: ConversationalState) -> ConversationalState:
    await asyncio.sleep(0)
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("MATCHER", "Finding lawyers..."))

    facts = state.get("extracted_facts", {})
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    ranked: list[LawyerMatch] = []
    for lawyer in raw:
        score = _score_lawyer(lawyer, facts)
        slug = _slugify(str(lawyer.get("name", "")))
        rating = float(lawyer.get("rating", 0.0) or 0.0)
        ranked.append(
            {
                "name": lawyer["name"],
                "specialty": ", ".join(lawyer["specialties"]),
                "location": lawyer["location"],
                "score": score,
                "rating": round(rating, 1),
                "profile_url": f"https://lawyer.com/attorneys/{slug}",
                "contact_email": f"intake+{slug}@lawyer.com",
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    state["lawyer_matches"] = ranked[:6]
    state["logs"].append(agent_log("MATCHER", f"Selected top {len(state['lawyer_matches'])} lawyers"))
    return state
