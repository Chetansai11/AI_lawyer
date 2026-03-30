from __future__ import annotations

from app.state import ConversationalState


def effective_missing_fields(state: ConversationalState | dict) -> list[str]:
    """
    Merge fact-based gaps with auditor liability flags.
    LangGraph / LLM may report empty missing_fields while facts are still blank — this is the source of truth for UI + replies.
    """
    facts = (state.get("extracted_facts") if isinstance(state, dict) else {}) or {}
    gaps: list[str] = []
    if not str(facts.get("location", "")).strip():
        gaps.append("location")
    if not str(facts.get("date", "")).strip():
        gaps.append("date")
    if not str(facts.get("injuries", "")).strip():
        gaps.append("injuries")
    if not str(facts.get("incident_type", "")).strip():
        gaps.append("incident_type")

    for x in state.get("missing_fields") or []:
        if x == "liability" and "liability" not in gaps:
            gaps.append("liability")

    seen: set[str] = set()
    out: list[str] = []
    for g in gaps:
        if g and g not in seen:
            seen.add(g)
            out.append(g)
    return out
