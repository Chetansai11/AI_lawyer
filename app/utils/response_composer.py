from __future__ import annotations

import inspect
import random
import re
from typing import Any

from app.llm import chat_text
from app.state import ConversationalState

ACK_PHRASES = [
    "Got it — thanks for sharing that.",
    "I see, that helps clarify things.",
    "Thanks, that gives me a better picture.",
    "Makes sense — I appreciate you spelling that out.",
    "Okay, I'm with you so far.",
    "Thanks for walking me through that.",
]

PROMPT = """You are a professional, empathetic legal intake assistant.

Your job is to communicate naturally with a potential client while gathering missing information.

Guidelines:
- Sound human, calm, and helpful (not robotic)
- Write like a real chat: short back-and-forth, not an interrogation
- Acknowledge what the user just said in a natural line or two (vary your openers across turns)
- Avoid repeating their whole story or quoting long chunks
- Ask ONLY ONE question at a time
- Keep responses concise (2–4 sentences max)
- Use conversational phrasing (not formal/legal tone)
- Do NOT sound like a form or checklist

Tone:
- Friendly but professional
- Slightly conversational
- Clear and confident

Structure:
1. Brief acknowledgment
2. Smooth transition
3. Ask the next question naturally

Examples:

User: "I had an accident recently in Texas and hurt my arm"

Good Response:
"Got it — thanks for sharing that. I can help figure out what your options might look like.

Do you happen to remember the exact date the accident occurred?"

---

User: "I slipped at a store and hurt my back"

Good Response:
"That sounds like a tough situation, especially with a back injury.

Do you recall if there were any warning signs around the area where you slipped?"

---

Now generate a response using:
- next_question: {next_question}
- recent conversation: {conversation}
- suggested acknowledgment tone (you may use or paraphrase naturally): {ack_phrase}

Return ONLY the response text.
"""

COMPLETE_MESSAGE = (
    "I have enough information to evaluate your case. "
    "You can review the updated brief on the right."
)


def _recent_conversation_snippet(conv: list[dict[str, Any]], *, max_messages: int = 3) -> str:
    if not conv:
        return "(no messages yet)"
    tail = conv[-max_messages:]
    lines: list[str] = []
    for m in tail:
        role = str(m.get("role", "user"))
        content = str(m.get("content") or "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines) if lines else "(no messages yet)"


def _strip_code_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _fallback_follow_up(next_question: str, ack_phrase: str) -> str:
    return f"{ack_phrase}\n\n{next_question.strip()}"


async def generate_human_response(state: ConversationalState | dict[str, Any], llm: Any = None) -> str:
    """
    Communication layer: turn auditor `next_question` + recent turns into a natural reply.

    Decision logic stays in the auditor; this only phrases the message.

    `llm`: optional async or sync callable taking one str (the composed user prompt) and returning str.
    """
    next_question = str(state.get("next_question") or "").strip()
    if not next_question:
        return COMPLETE_MESSAGE

    conv = list(state.get("conversation") or [])
    ack_phrase = random.choice(ACK_PHRASES)
    conversation = _recent_conversation_snippet(conv)
    user_payload = PROMPT.format(
        next_question=next_question,
        conversation=conversation,
        ack_phrase=ack_phrase,
    )

    if llm is not None:
        result = llm(user_payload)
        if inspect.isawaitable(result):
            result = await result
        text = _strip_code_fences(str(result))
        return text if text else _fallback_follow_up(next_question, ack_phrase)

    try:
        raw = await chat_text(
            system=(
                "You write the visible chat message for a legal intake assistant. "
                "Output plain text only: no quotes, no markdown fences, no labels."
            ),
            user=user_payload,
        )
        text = _strip_code_fences(raw)
        if not text:
            return _fallback_follow_up(next_question, ack_phrase)
        return text[:2000]
    except Exception:
        return _fallback_follow_up(next_question, ack_phrase)
