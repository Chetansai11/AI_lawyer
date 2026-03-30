from __future__ import annotations

import asyncio
from copy import deepcopy

from app.agents.auditor import run_auditor, suggest_next_question
from app.agents.matcher import run_matcher
from app.agents.researcher import run_researcher
from app.agents.scribe import run_scribe
from app.state import ConversationalState, empty_conversational_state
from app.utils.formatter import format_brief_markdown
from app.utils.gaps import effective_missing_fields
from app.utils.logger import agent_log
from app.utils.response_composer import COMPLETE_MESSAGE, generate_human_response


async def _parallel_agents(state: ConversationalState) -> ConversationalState:
    state = {**empty_conversational_state(), **dict(state)}
    state["logs"].append(agent_log("GRAPH", "Running Auditor, Matcher, Researcher in parallel"))

    auditor_state, matcher_state, researcher_state = await asyncio.gather(
        run_auditor(deepcopy(state)),
        run_matcher(deepcopy(state)),
        run_researcher(deepcopy(state)),
    )

    merged = deepcopy(state)
    merged["missing_fields"] = auditor_state.get("missing_fields", [])
    merged["assumptions"] = auditor_state.get("assumptions", [])
    merged["risk_analysis"] = auditor_state.get("risk_analysis", "")
    merged["case_score"] = auditor_state.get("case_score", 0.0)
    merged["confidence_score"] = auditor_state.get("confidence_score", 0.0)
    merged["next_question"] = auditor_state.get("next_question", "")
    merged["lawyer_matches"] = matcher_state.get("lawyer_matches", [])
    merged["plausibility"] = researcher_state.get("plausibility", "medium")
    merged["researcher_reasoning"] = researcher_state.get("researcher_reasoning", "")

    merged["logs"] = list(state["logs"])
    for branch in (auditor_state, matcher_state, researcher_state):
        for line in branch.get("logs", []):
            if line not in merged["logs"]:
                merged["logs"].append(line)

    return merged


async def compose_assistant_reply(state: ConversationalState) -> ConversationalState:
    state = {**empty_conversational_state(), **dict(state)}
    effective = effective_missing_fields(state)
    state["missing_fields"] = effective
    facts = state.get("extracted_facts") or {}
    nq = (state.get("next_question") or "").strip()

    if effective:
        if not nq:
            nq = suggest_next_question(effective, facts)
        state["next_question"] = nq
        reply = await generate_human_response(state)
    else:
        nq = ""
        reply = COMPLETE_MESSAGE

    state["next_question"] = nq
    state["assistant_reply"] = reply
    conv = list(state.get("conversation", []))
    conv.append({"role": "assistant", "content": reply})
    state["conversation"] = conv
    state["logs"].append(agent_log("GRAPH", "Composing assistant reply"))
    return state


async def run_pipeline(state: ConversationalState) -> ConversationalState:
    """
    Scribe → parallel agents (auditor, matcher, researcher).
    Uses direct async calls so `logs` accumulate (LangGraph ainvoke was merging away prior log lines).
    """
    state = {**empty_conversational_state(), **dict(state)}
    state = await run_scribe(state)
    state = await _parallel_agents(state)
    return state


async def run_audit(input_text: str) -> dict[str, object]:
    """One-shot analyze: single user message, full pipeline."""
    initial: ConversationalState = empty_conversational_state()
    initial["conversation"] = [{"role": "user", "content": input_text}]
    initial["logs"] = []
    merged = await run_pipeline(initial)
    final_state = await compose_assistant_reply(merged)
    return {
        "brief": format_brief_markdown(final_state),
        "logs": final_state.get("logs", []),
    }
