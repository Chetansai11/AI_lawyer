from __future__ import annotations

from typing import TypedDict


class Message(TypedDict):
    role: str
    content: str


class Assumption(TypedDict):
    text: str
    confidence: float


class LawyerMatch(TypedDict):
    name: str
    specialty: str
    location: str
    score: float
    rating: float
    profile_url: str
    contact_email: str


class ConversationalState(TypedDict, total=False):
    """Persistent state for AI Intake Auditor (multi-turn)."""

    conversation: list[Message]
    extracted_facts: dict[str, str]
    missing_fields: list[str]
    assumptions: list[Assumption]
    risk_analysis: str
    case_score: float
    lawyer_matches: list[LawyerMatch]
    next_question: str
    confidence_score: float
    logs: list[str]
    plausibility: str
    researcher_reasoning: str
    case_research_summary: str
    off_topic: bool
    assistant_reply: str


def default_extracted_facts() -> dict[str, str]:
    return {
        "name": "",
        "location": "",
        "date": "",
        "incident_type": "",
        "injuries": "",
    }


def empty_conversational_state() -> ConversationalState:
    return {
        "conversation": [],
        "extracted_facts": default_extracted_facts(),
        "missing_fields": [],
        "assumptions": [],
        "risk_analysis": "",
        "case_score": 0.0,
        "lawyer_matches": [],
        "next_question": "",
        "confidence_score": 0.0,
        "logs": [],
        "plausibility": "medium",
        "researcher_reasoning": "",
        "case_research_summary": "",
        "off_topic": False,
        "assistant_reply": "",
    }
