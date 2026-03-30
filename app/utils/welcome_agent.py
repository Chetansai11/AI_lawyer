"""Static opening message for intake chat."""

from __future__ import annotations

WELCOME_MESSAGE = """Hi there, welcome to Lawyer.com. I’m AI Intake Auditor, and I’m here to help get the ball rolling.

I understand that reaching out for legal guidance can feel a little overwhelming, so I’ll do my best to make this as easy as possible. I’m here to listen to what’s going on and gather some information.

I’ll be asking you questions one at a time, and as we talk, I’ll build a brief summary of your situation. This will help our attorneys understand your needs quickly. You might also see some potential attorney matches appear as we go those are just suggestions based on what you tell me. 😊

Whenever you’re ready, just begin telling me what’s happening"""


async def generate_opening_message() -> str:
    return WELCOME_MESSAGE
