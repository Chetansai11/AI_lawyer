from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.llm import chat_json, get_client
from app.state import ConversationalState, default_extracted_facts, empty_conversational_state
from app.utils.logger import agent_log
from app.utils.prompts import SCRIBE_CONVERSATION_SYSTEM


def _conversation_transcript(state: ConversationalState) -> str:
    msgs = state.get("conversation", [])
    lines = []
    for m in msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines)


def _extract_date(text: str) -> str:
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},\s+\d{4}\b",
    ]
    lowered = text.lower()
    for pattern in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if match:
            return match.group(0)
    return ""


def _extract_location(text: str) -> str:
    loc_patterns = [
        r"\b(?:in|at|near)\s+(?:a\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
        r"(?:in|at|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
        r"\b(?:city|location)[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})",
    ]
    for pattern in loc_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def _extract_incident_type(text: str) -> str:
    keywords = {
        "car accident": ["car accident", "vehicle crash", "rear-ended", "collision", "hit my car"],
        "workplace injury": ["work injury", "workplace injury", "on the job", "factory accident"],
        "slip and fall": ["slip and fall", "slipped", "wet floor", "fell in store"],
        "medical malpractice": ["malpractice", "surgical error", "misdiagnosed", "wrong medication"],
        "assault": ["assault", "attacked", "battery"],
        "contract dispute": ["contract dispute", "breach of contract", "did not pay", "agreement broken"],
        "property dispute": ["property dispute", "landlord", "tenant", "eviction"],
    }
    lowered = text.lower()
    for incident, variants in keywords.items():
        if any(word in lowered for word in variants):
            return incident
    return ""


def _extract_injuries(text: str) -> str:
    lowered = text.lower()
    if any(w in lowered for w in ("no injury", "uninjured", "not hurt", "fine")):
        return "none reported"
    if any(w in lowered for w in ("hospital", "er", "surgery", "fracture", "broken", "whiplash", "concussion")):
        snippet = text[:400]
        return f"injuries mentioned: {snippet[:200]}…" if len(snippet) > 200 else snippet
    if "hurt" in lowered or "pain" in lowered or "injur" in lowered:
        return "injuries mentioned (details unclear)"
    return ""


def _heuristic_from_text(full_text: str) -> dict[str, str]:
    return {
        "location": _extract_location(full_text),
        "date": _extract_date(full_text),
        "incident_type": _extract_incident_type(full_text),
        "injuries": _extract_injuries(full_text),
    }


def _merge_facts(prev: dict[str, str], new: dict[str, str]) -> dict[str, str]:
    out = {**default_extracted_facts(), **prev}
    for key in ("location", "date", "incident_type", "injuries"):
        nv = str(new.get(key, "")).strip()
        if nv and nv.lower() not in ("unknown", "n/a", "none", ""):
            out[key] = nv
    return out


def _normalize_llm_facts(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("scribe response must be a JSON object")
    inner = payload.get("extracted_facts", payload)
    if not isinstance(inner, dict):
        raise ValueError("extracted_facts missing")
    out = default_extracted_facts()
    for key in ("location", "date", "incident_type", "injuries"):
        v = inner.get(key, "")
        out[key] = str(v).strip() if v is not None else ""
    return out


async def run_scribe(state: ConversationalState) -> ConversationalState:
    await asyncio.sleep(0)
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("SCRIBE", "Updating extracted facts..."))
    prev = _merge_facts(default_extracted_facts(), state.get("extracted_facts", {}))
    transcript = _conversation_transcript(state)
    full_text = transcript or ""

    if get_client():
        try:
            user_payload = json.dumps(
                {"conversation": state.get("conversation", []), "previous_extracted_facts": prev},
                ensure_ascii=False,
            )
            payload = await chat_json(SCRIBE_CONVERSATION_SYSTEM, user_payload)
            new_facts = _normalize_llm_facts(payload)
            merged = _merge_facts(prev, new_facts)
            state["extracted_facts"] = merged
            state["logs"].append(agent_log("SCRIBE", "Used Gemini for incremental extraction"))
        except Exception as exc:
            merged = _merge_facts(prev, _heuristic_from_text(full_text))
            state["extracted_facts"] = merged
            state["logs"].append(agent_log("SCRIBE", f"Gemini failed ({exc!r}); heuristic merge"))
    else:
        merged = _merge_facts(prev, _heuristic_from_text(full_text))
        state["extracted_facts"] = merged
        state["logs"].append(agent_log("SCRIBE", "Heuristic extraction (no API key)"))

    state["logs"].append(agent_log("SCRIBE", f"Facts: {state['extracted_facts']}"))
    return state
