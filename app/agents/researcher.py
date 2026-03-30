from __future__ import annotations

import asyncio
import random

from app.state import ConversationalState, empty_conversational_state
from app.utils.logger import agent_log


async def run_researcher(state: ConversationalState) -> ConversationalState:
    await asyncio.sleep(0)
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("RESEARCHER", "Checking plausibility..."))
    facts = state.get("extracted_facts", {})
    incident = str(facts.get("incident_type", ""))
    loc = str(facts.get("location", "")).strip()
    dt = str(facts.get("date", "")).strip()
    inj = str(facts.get("injuries", "")).strip()

    missing_core = sum(1 for x in (loc, dt) if not x)
    filled = sum(1 for x in (loc, dt, str(facts.get("incident_type", "")).strip(), inj) if x)

    if incident in {"car accident", "workplace injury", "slip and fall"} and missing_core == 0 and inj:
        plausibility = "high"
        reasoning = (
            f"Incident type is concrete ({incident}); core logistics present (location/date); "
            f"injury signal present. Coherence score ~{filled}/4 fields."
        )
    elif missing_core >= 2 or not incident:
        plausibility = "low"
        reasoning = (
            "Several core facts missing or incident type unclear; narrative coherence is weak for triage."
        )
    else:
        plausibility = random.choice(["medium", "medium", "high"])
        reasoning = (
            f"Mixed completeness: {filled}/4 key fields filled; plausibility set to {plausibility} pending details."
        )

    state["plausibility"] = plausibility
    state["researcher_reasoning"] = reasoning
    state["logs"].append(agent_log("RESEARCHER", reasoning))
    state["logs"].append(agent_log("RESEARCHER", f"Incident plausibility: {plausibility}"))
    return state
