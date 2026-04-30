"""Session- und Submission-Endpunkte."""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.agents.orchestrator import AgentOrchestrator
from backend.cases.manager import case_manager
from backend.config.tp_configs import current_tp_phase
from backend.evaluator.rubric_evaluator import RubricEvaluator
from backend.models.session import Session, SessionCreate, SessionResponse
from backend.models.submission import (
    AnswerSubmit,
    Submission,
    SubmissionCreate,
    SubmissionResult,
    SubmissionStatus,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["sessions"])

SUBMISSIONS_DIR = Path(__file__).parent.parent / "db" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory session store (Phase 2: Redis/PostgreSQL)
_sessions: dict[str, Session] = {}
_submissions: dict[str, Submission] = {}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate):
    case = case_manager.get(body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    session_id = str(uuid.uuid4())
    tp = case.target_tp or current_tp_phase()

    session = Session(
        session_id=session_id,
        user_id=body.user_id,
        case_id=body.case_id,
        tp_phase=tp,
    )
    _sessions[session_id] = session

    return SessionResponse(
        session_id=session_id,
        user_id=body.user_id,
        case_id=body.case_id,
        tp_phase=tp,
        websocket_url=f"/ws/{session_id}",
    )


# ---------------------------------------------------------------------------
# Chat — HTTP POST (zuverlässiger als WebSocket durch Railway-Proxy)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    content: str
    history: list[dict] = []

class ChatResponse(BaseModel):
    agent_type: str
    content: str

@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(session_id: str, body: ChatRequest):
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    case = case_manager.get(session.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    orchestrator = AgentOrchestrator(api_key=api_key)

    case_context = f"{case.title}\n{case.tagline}\n" + "\n".join(
        s.content[:400] for s in case.sections[:2]
    )

    session.message_count += 1
    session.last_activity = datetime.utcnow()

    try:
        agent_type, response_text = await orchestrator.respond(
            session=session,
            user_message=body.content,
            history=body.history,
            case_context=case_context,
        )
    except Exception as e:
        logger.error("chat_error", error=str(e), type=type(e).__name__)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    return ChatResponse(agent_type=agent_type, content=response_text)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

@router.post("/submissions", response_model=dict, status_code=201)
async def create_submission(body: SubmissionCreate):
    sub_id = str(uuid.uuid4())
    submission = Submission(
        submission_id=sub_id,
        user_id=body.user_id,
        matrikelnummer=body.matrikelnummer,
        case_id=body.case_id,
        target_tp=body.target_tp,
    )
    _submissions[sub_id] = submission
    return {"submission_id": sub_id}


@router.post("/submissions/{submission_id}/answer")
async def submit_answer(submission_id: str, body: AnswerSubmit):
    sub = _submissions.get(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission nicht gefunden")
    if sub.status == SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Submission bereits abgeschlossen")
    sub.answers[body.question_id] = body.answer_text
    return {"ok": True}


@router.post("/submissions/{submission_id}/submit", response_model=SubmissionResult)
async def submit_and_evaluate(submission_id: str):
    sub = _submissions.get(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission nicht gefunden")

    case = case_manager.get(sub.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    evaluator = RubricEvaluator(api_key=api_key)

    sub.status = SubmissionStatus.SUBMITTED
    sub.submitted_at = datetime.utcnow()

    result = await evaluator.evaluate_submission(sub, case)

    sub.status = SubmissionStatus.EVALUATED
    sub.evaluated_at = datetime.utcnow()
    sub.scores = result.scores
    sub.total_points = result.total_points
    sub.max_points = result.max_points
    sub.percentage = result.percentage

    # Persistieren für Dashboard
    out = {
        "submission_id": sub.submission_id,
        "matrikelnummer": sub.matrikelnummer,
        "case_id": sub.case_id,
        "target_tp": sub.target_tp,
        "percentage": sub.percentage,
        "scores": [s.model_dump() for s in sub.scores],
    }
    (SUBMISSIONS_DIR / f"{submission_id}.json").write_text(
        json.dumps(out, default=str), encoding="utf-8"
    )

    return result
