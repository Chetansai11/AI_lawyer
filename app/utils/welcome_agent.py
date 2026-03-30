"""LLM-generated opening message for intake chat (no extra LangGraph agent)."""

from __future__ import annotations

from app.llm import chat_text, get_client

WELCOME_FALLBACK = """Hi — I'm here to help with your legal intake.

Tell me, in your own words, what happened. I'll listen and ask one clear follow-up at a time so it doesn't feel like a form. I'll keep a living brief on the right for your lawyer, and matching attorneys can appear below once we have enough context.

To start: type your story in the box below and press Send or Enter. Use Shift+Enter if you need a new line."""

_SYSTEM = """You are AI Auditor, a warm legal intake assistant for Lawyer.com.
Write ONLY the opening chat message the user will see first (no subject line, no JSON).
Requirements:
- 3–5 short paragraphs or a few lines with blank lines between ideas
- Friendly, human, calm — not corporate or robotic
- Explain briefly: you'll listen to their story, ask one question at a time, build a brief on the right for counsel, attorney matches may appear below
- Tell them how to start: type below, Send or Enter, Shift+Enter for newline
- Do NOT ask a legal fact question yet (no "what date" etc.) — this is only the welcome
- No emojis unless one subtle one fits
- Plain text only"""


async def generate_opening_message() -> str:
    if not get_client():
        return WELCOME_FALLBACK
    try:
        text = await chat_text(
            _SYSTEM,
            "Generate the opening message now.",
            max_tokens=450,
        )
        cleaned = (text or "").strip()
        return cleaned if len(cleaned) > 40 else WELCOME_FALLBACK
    except Exception:
        return WELCOME_FALLBACK
