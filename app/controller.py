from __future__ import annotations

from copy import deepcopy

from app.graph import compose_assistant_reply, run_pipeline
from app.state import ConversationalState, empty_conversational_state
from app.utils.formatter import format_brief_markdown


def _merge_session_state(state: ConversationalState | dict) -> ConversationalState:
    """Ensure every key exists for LangGraph nodes (avoid KeyError on partial session dicts)."""
    base = empty_conversational_state()
    merged: dict = {**base, **dict(state)}
    return merged  # type: ignore[return-value]


async def handle_message(user_input: str, state: ConversationalState | None) -> tuple[str, str, list[str], ConversationalState]:
    """
    Append user message, run LangGraph, return assistant reply, markdown brief, logs, updated state.

    Assistant wording is composed in ``compose_assistant_reply`` via
    ``app.utils.response_composer.generate_human_response`` (auditor still owns ``next_question``).
    """
    if state:
        st = _merge_session_state(deepcopy(state))
    else:
        st = empty_conversational_state()
    st["conversation"] = list(st.get("conversation", [])) + [{"role": "user", "content": user_input.strip()}]
    st["logs"] = []

    merged: ConversationalState = await run_pipeline(st)
    final: ConversationalState = await compose_assistant_reply(merged)
    reply = final.get("assistant_reply", "")
    brief = format_brief_markdown(final)
    logs = list(final.get("logs", []))
    return reply, brief, logs, final
