from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.llm import chat_json, get_client
from app.state import Assumption, ConversationalState, empty_conversational_state
from app.utils.logger import agent_log
from app.utils.prompts import AUDITOR_CONVERSATION_SYSTEM

OFF_TOPIC_REDIRECT = (
    "Please share only details about your legal situation: when and where things happened, "
    "what type of incident it was, and any injuries or medical care—so we can build your attorney brief."
)


def _latest_user_message(state: ConversationalState) -> str:
    conv = list(state.get("conversation") or [])
    for m in reversed(conv):
        if m.get("role") == "user":
            return str(m.get("content") or "").strip()
    return ""


_CASE_HINTS = (
    "accident",
    "injur",
    "hurt",
    "lawyer",
    "legal",
    "suit",
    "case",
    "slip",
    "fall",
    "malpractice",
    "contract",
    "tenant",
    "landlord",
    "employer",
    "assault",
    "divorce",
    "custody",
    "visa",
    "immigration",
    "dui",
    "arrest",
    "bankrupt",
)


def _heuristic_off_topic(latest: str, facts: dict[str, Any]) -> bool:
    """Conservative: flag only clear chitchat / unrelated lines when intake is still thin."""
    if not latest:
        return False
    low = latest.lower().strip()
    # Strong case signals in this turn → on-topic
    if any(h in low for h in _CASE_HINTS):
        return False
    filled = sum(
        1
        for k in ("location", "date", "incident_type", "injuries")
        if str(facts.get(k, "")).strip()
    )
    if filled >= 2 and len(latest) < 120:
        # Short ack after they've given facts → not off-topic
        return False

    unrelated = (
        "weather",
        "joke",
        "recipe",
        "stock price",
        "who won the",
        "ignore previous",
        "pretend you",
    )
    if any(u in low for u in unrelated):
        return True

    # Very short greeting-only style with no case content
    if len(latest) < 100:
        if re.match(
            r"^(hi|hello|hey|good\s+(morning|afternoon|evening)|thanks?|thank\s+you)[\s!,?.]*$",
            low,
        ):
            return True
        if "thanks for reaching" in low and filled == 0:
            return True

    return False


def _apply_off_topic(off_topic: bool, nq: str, missing: list[str]) -> tuple[bool, str]:
    if not off_topic:
        return False, nq
    text = ((nq or "").strip() or OFF_TOPIC_REDIRECT)
    return True, text


def _facts_incomplete(facts: dict) -> list[str]:
    missing: list[str] = []
    loc = str(facts.get("location", "")).strip()
    dt = str(facts.get("date", "")).strip()
    inj = str(facts.get("injuries", "")).strip()
    inc = str(facts.get("incident_type", "")).strip()
    if not loc:
        missing.append("location")
    if not dt:
        missing.append("date")
    if not inj:
        missing.append("injuries")
    if not inc:
        missing.append("incident_type")
    return missing


def _liability_gap(facts: dict, transcript: str) -> bool:
    inc = str(facts.get("incident_type", "")).lower()
    if not any(x in inc for x in ("car", "slip", "fall", "accident", "assault", "workplace")):
        return False
    t = transcript.lower()
    return not any(
        w in t
        for w in (
            "fault",
            "negligence",
            "liable",
            "who hit",
            "rear",
            "wet floor",
            "employer",
            "assailant",
            "at fault",
        )
    )


def _heuristic_missing(facts: dict, transcript: str) -> list[str]:
    missing = _facts_incomplete(facts)
    if _liability_gap(facts, transcript):
        if "liability" not in missing:
            missing.append("liability")
    return missing


def suggest_next_question(missing: list[str], facts: dict) -> str:
    # Keep per-field prompts short; caller can combine top gaps.
    order = ["date", "location", "incident_type", "injuries", "liability"]
    for field in order:
        if field not in missing:
            continue
        if field == "date":
            return "What is the exact date (and approximate time) of the incident?"
        if field == "location":
            return "In which city and state did this happen (or the exact venue or address if you know it)?"
        if field == "incident_type":
            return (
                "In one sentence, what type of incident was this "
                "(for example: car accident, slip and fall, workplace injury)?"
            )
        if field == "injuries":
            return "What injuries or physical symptoms did you have, and did you seek medical care?"
        if field == "liability":
            return "What happened in terms of fault or responsibility — who do you believe was negligent or at fault, and why?"
    return ""


def _follow_up_questions(missing: list[str], facts: dict) -> str:
    """Return up to two prioritized follow-ups in one concise message."""
    order = ["date", "location", "incident_type", "injuries", "liability"]
    prompts: list[str] = []
    for field in order:
        if field in missing:
            q = suggest_next_question([field], facts)
            if q and q not in prompts:
                prompts.append(q)
        if len(prompts) >= 2:
            break
    if not prompts:
        return ""
    if len(prompts) == 1:
        return prompts[0]
    return prompts[0] + "\n" + prompts[1]


def _heuristic_assumptions(missing: list[str], facts: dict) -> list[Assumption]:
    out: list[Assumption] = []
    if "date" in missing:
        out.append({"text": "Incident timing may be within typical filing windows; date not confirmed.", "confidence": 0.4})
    if "location" in missing:
        out.append({"text": "Jurisdiction and venue are not confirmed.", "confidence": 0.45})
    if "injuries" in missing:
        out.append({"text": "Injury severity and causation are not documented in intake.", "confidence": 0.45})
    if "incident_type" in missing:
        out.append({"text": "Incident category is not confirmed from intake.", "confidence": 0.45})
    if "liability" in missing:
        out.append({"text": "Liability and duty/breach are not yet clear from intake.", "confidence": 0.5})
    inc = str(facts.get("incident_type", "")).lower()
    if inc and not out:
        out.append({"text": "Incident category is inferred from intake; may be incomplete.", "confidence": 0.6})
    return out or [{"text": "Intake is preliminary; facts may change with documentation.", "confidence": 0.55}]


def _risk_text(missing: list[str], incident: str, plausibility: str) -> str:
    base = (
        f"This intake suggests a **{incident or 'general civil'}** matter. "
        f"Plausibility signal: **{plausibility}**. "
    )
    if missing:
        return base + (
            "Gaps remain in " + ", ".join(missing) + ". "
            "Until those are clarified, risk assessment is tentative and should not be treated as legal advice."
        )
    return base + "Core triage fields are present; remaining uncertainty should be validated with evidence."


def _score_case(missing_count: int, plausibility: str) -> float:
    score = 7.0
    if plausibility == "low":
        score -= 2.0
    elif plausibility == "medium":
        score -= 0.8
    if missing_count:
        score -= min(3.0, missing_count * 0.75)
    return round(max(1.0, min(10.0, score)), 1)


def _clamp01(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.55
    return max(0.0, min(1.0, v))


def _clamp_score(x: Any) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 5.0
    return round(max(1.0, min(10.0, v)), 1)


def _normalize_assumptions(raw: Any) -> list[Assumption]:
    if not isinstance(raw, list):
        return []
    out: list[Assumption] = []
    for item in raw:
        if isinstance(item, dict) and "text" in item:
            out.append({"text": str(item["text"]), "confidence": _clamp01(item.get("confidence", 0.5))})
    return out


def _transcript(state: ConversationalState) -> str:
    return "\n".join(m.get("content", "") for m in state.get("conversation", []))


async def run_auditor(state: ConversationalState) -> ConversationalState:
    await asyncio.sleep(0)
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("AUDITOR", "Evaluating case strength..."))
    facts = state.get("extracted_facts", {})
    plausibility = state.get("plausibility", "medium")
    transcript = _transcript(state)

    user_block = json.dumps(
        {
            "conversation": state.get("conversation", []),
            "extracted_facts": facts,
            "plausibility_hint": plausibility,
        },
        ensure_ascii=False,
    )

    latest = _latest_user_message(state)

    if get_client():
        try:
            payload = await chat_json(AUDITOR_CONVERSATION_SYSTEM, user_block)
            if not isinstance(payload, dict):
                raise ValueError("auditor JSON must be an object")

            off_topic = bool(payload.get("off_topic"))
            if not off_topic and _heuristic_off_topic(latest, facts):
                off_topic = True

            raw_missing = payload.get("missing_fields", [])
            norm_map = {"injury": "injuries", "fault": "liability", "negligence": "liability"}
            missing: list[str] = []
            for x in raw_missing:
                key = norm_map.get(str(x).lower().strip(), str(x).lower().strip())
                if key in ("date", "location", "incident_type", "injuries", "liability") and key not in missing:
                    missing.append(key)
            assumptions = _normalize_assumptions(payload.get("assumptions")) or _heuristic_assumptions(missing, facts)
            risk = str(payload.get("risk_analysis", "")).strip() or _risk_text(missing, str(facts.get("incident_type", "")), plausibility)
            case_score = _clamp_score(payload.get("case_score"))
            conf = _clamp01(payload.get("confidence_score"))
            nq = str(payload.get("next_question", "")).strip()

            if not missing and (_facts_incomplete(facts) or _liability_gap(facts, transcript)):
                missing = _heuristic_missing(facts, transcript)

            if not missing:
                nq = ""
            elif not nq:
                nq = _follow_up_questions(missing, facts)

            off_topic, nq = _apply_off_topic(off_topic, nq, missing)
            if not missing and off_topic:
                missing = _heuristic_missing(facts, transcript) or ["incident_type"]

            state["off_topic"] = off_topic
            state["missing_fields"] = missing
            state["assumptions"] = assumptions
            state["risk_analysis"] = risk
            state["case_score"] = case_score
            state["confidence_score"] = round(conf, 2)
            state["next_question"] = nq
            state["logs"].append(agent_log("AUDITOR", "Used Gemini for case evaluation"))
        except Exception as exc:
            missing = _heuristic_missing(facts, transcript)
            off_topic = _heuristic_off_topic(latest, facts)
            nq = _follow_up_questions(missing, facts) if missing else ""
            off_topic, nq = _apply_off_topic(off_topic, nq, missing)
            if not missing and off_topic:
                missing = _heuristic_missing(facts, transcript) or ["incident_type"]
            state["off_topic"] = off_topic
            state["missing_fields"] = missing
            state["assumptions"] = _heuristic_assumptions(missing, facts)
            state["risk_analysis"] = _risk_text(missing, str(facts.get("incident_type", "")), plausibility)
            state["case_score"] = _score_case(len(missing), plausibility)
            state["confidence_score"] = round(max(0.15, min(1.0, 1 - 0.12 * len(missing))), 2)
            state["next_question"] = nq
            state["logs"].append(agent_log("AUDITOR", f"Gemini failed ({exc!r}); heuristic mode"))
    else:
        missing = _heuristic_missing(facts, transcript)
        off_topic = _heuristic_off_topic(latest, facts)
        nq = _follow_up_questions(missing, facts) if missing else ""
        off_topic, nq = _apply_off_topic(off_topic, nq, missing)
        if not missing and off_topic:
            missing = _heuristic_missing(facts, transcript) or ["incident_type"]
        state["off_topic"] = off_topic
        state["missing_fields"] = missing
        state["assumptions"] = _heuristic_assumptions(missing, facts)
        state["risk_analysis"] = _risk_text(missing, str(facts.get("incident_type", "")), plausibility)
        state["case_score"] = _score_case(len(missing), plausibility)
        state["confidence_score"] = round(max(0.15, min(1.0, 1 - 0.12 * len(missing))), 2)
        state["next_question"] = nq
        state["logs"].append(agent_log("AUDITOR", "Heuristic evaluation (no API key)"))

    state["logs"].append(
        agent_log(
            "AUDITOR",
            f"Score {state.get('case_score')}/10, confidence {state.get('confidence_score')}",
        )
    )
    return state
