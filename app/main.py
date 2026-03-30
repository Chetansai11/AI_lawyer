from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.requests import Request

from app.controller import handle_message
from app.graph import run_audit
from app.state import ConversationalState
from app.utils.welcome_agent import generate_opening_message

_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, max-age=0, must-revalidate",
    "Pragma": "no-cache",
}

_ROOT = Path(__file__).resolve().parent.parent
_UI_DIR = _ROOT / "ui"
_STATIC_DIR = _UI_DIR / "static"
_UI_DIST = _UI_DIR / "dist"
_UI_DIST_INDEX = _UI_DIST / "index.html"
_UI_DIST_ASSETS = _UI_DIST / "assets"

app = FastAPI(title="AI Intake Auditor", version="2.0.0")


@app.middleware("http")
async def disable_browser_cache_for_ui(request: Request, call_next):
    """Avoid stale index.html / App.jsx when the dev server restarts (browser disk cache)."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/") or path.startswith("/assets/"):
        for k, v in _NO_CACHE.items():
            response.headers[k] = v
    return response


if _UI_DIST_INDEX.is_file() and _UI_DIST_ASSETS.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_UI_DIST_ASSETS)), name="assets")
elif _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

SESSIONS: dict[str, ConversationalState] = {}


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=5, description="Messy legal input text")


class AnalyzeResponse(BaseModel):
    brief: str
    logs: list[str]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class LawyerMatchOut(BaseModel):
    name: str = ""
    specialty: str = ""
    location: str = ""
    score: float = 0.0
    rating: float = 0.0
    profile_url: str = ""
    contact_email: str = ""


class ChatResponse(BaseModel):
    reply: str
    brief: str
    logs: list[str]
    session_id: str
    case_score: float = 0.0
    confidence_score: float = 0.0
    plausibility: str = ""
    risk_analysis: str = ""
    next_question: str = ""
    researcher_reasoning: str = ""
    lawyer_matches: list[LawyerMatchOut] = Field(default_factory=list)


class ShareBriefRequest(BaseModel):
    session_id: str | None = None
    lawyer_name: str
    lawyer_email: str | None = None
    brief_markdown: str = Field(..., min_length=1)
    note: str = ""


class ShareBriefResponse(BaseModel):
    status: str
    reference_id: str


class BookAppointmentRequest(BaseModel):
    session_id: str | None = None
    lawyer_name: str
    lawyer_email: str | None = None
    client_email: str = ""
    client_phone: str = ""
    preferred_times: str = ""
    note: str = ""


class BookAppointmentResponse(BaseModel):
    status: str
    reference_id: str


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def spa() -> FileResponse:
    if _UI_DIST_INDEX.is_file():
        return FileResponse(_UI_DIST_INDEX, headers=_NO_CACHE)
    index = _UI_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index, headers=_NO_CACHE)


@app.get("/welcome")
async def welcome_message() -> dict[str, str]:
    """Agent-generated opening copy for empty chat (LLM with safe fallback)."""
    message = await generate_opening_message()
    return {"message": message}


@app.post("/share-brief", response_model=ShareBriefResponse)
async def share_brief(payload: ShareBriefRequest) -> ShareBriefResponse:
    """
    Mock: send the generated attorney brief to a selected lawyer.
    Replace with email/CRM integration in production.
    """
    ref = str(uuid.uuid4())
    return ShareBriefResponse(status="queued", reference_id=ref)


@app.post("/book-appointment", response_model=BookAppointmentResponse)
async def book_appointment(payload: BookAppointmentRequest) -> BookAppointmentResponse:
    """
    Mock: request an appointment with the selected lawyer.
    Replace with calendaring integration in production.
    """
    ref = str(uuid.uuid4())
    return BookAppointmentResponse(status="requested", reference_id=ref)


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    try:
        result = await run_audit(payload.text)
        return AnalyzeResponse(brief=result["brief"], logs=result["logs"])
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        sid = payload.session_id or str(uuid.uuid4())
        prev = SESSIONS.get(sid)
        reply, brief, logs, final = await handle_message(payload.message, prev)
        SESSIONS[sid] = final
        raw_lawyers = final.get("lawyer_matches") or []
        lawyers_out: list[LawyerMatchOut] = []
        for row in raw_lawyers:
            if not isinstance(row, dict):
                continue
            lawyers_out.append(
                LawyerMatchOut(
                    name=str(row.get("name", "") or ""),
                    specialty=str(row.get("specialty", "") or ""),
                    location=str(row.get("location", "") or ""),
                    score=float(row.get("score", 0) or 0),
                    rating=float(row.get("rating", 0) or 0),
                    profile_url=str(row.get("profile_url", "") or ""),
                    contact_email=str(row.get("contact_email", "") or ""),
                )
            )
        return ChatResponse(
            reply=reply,
            brief=brief,
            logs=logs,
            session_id=sid,
            case_score=float(final.get("case_score", 0) or 0),
            confidence_score=float(final.get("confidence_score", 0) or 0),
            plausibility=str(final.get("plausibility", "") or ""),
            risk_analysis=str(final.get("risk_analysis", "") or ""),
            next_question=str(final.get("next_question", "") or ""),
            researcher_reasoning=str(final.get("researcher_reasoning", "") or ""),
            lawyer_matches=lawyers_out,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc
