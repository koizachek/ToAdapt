"""Session- und Submission-Endpunkte."""

import asyncio
import uuid

from backend.timeutils import naive_utcnow
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.agents.orchestrator import AgentOrchestrator
from backend.auth import require_student_access, student_access_required
from backend.cases.manager import case_manager
from backend.config.tp_configs import current_tp_phase
from backend.db.dashboard_store import dashboard_store
from backend.db.experiment_logger import experiment_logger
from backend.db.session_store import session_store
from backend.db.submission_store import submission_store
from backend.evaluator.rubric_evaluator import RubricEvaluator
from backend.llm import get_openrouter_key
from backend.models.experiment import ExperimentContext
from backend.models.session import Session, SessionCreate, SessionResponse
from backend.models.submission import (
    AnswerSubmit,
    Submission,
    SubmissionCreate,
    SubmissionResult,
    SubmissionStatus,
)
from backend.ratelimit import rate_limit

logger = structlog.get_logger(__name__)

# Alle Studierenden-Endpunkte verlangen den Kohorten-Zugangscode, sobald
# STUDENT_ACCESS_CODE gesetzt ist (sonst offen — Dev-/Experiment-Modus).
router = APIRouter(tags=["sessions"], dependencies=[Depends(require_student_access)])

# Prozesslokaler Cache; persistente Quelle ist der jeweilige Store (Mongo).
_sessions: dict[str, Session] = {}
_submissions: dict[str, Submission] = {}


async def _load_session(session_id: str) -> Session | None:
    session = _sessions.get(session_id)
    if session is not None:
        return session
    persisted = await asyncio.to_thread(session_store.load, session_id)
    if persisted is not None:
        _sessions[session_id] = persisted
    return persisted


def _normalize_experiment(experiment: ExperimentContext | None) -> ExperimentContext | None:
    return experiment.normalized() if experiment else None


def _participant_id(
    *,
    user_id: str,
    matrikelnummer: str | None,
    experiment: ExperimentContext | None,
) -> str:
    if matrikelnummer and matrikelnummer.strip():
        return matrikelnummer.strip()
    if experiment and experiment.prolific_pid:
        return experiment.prolific_pid
    return user_id


def _log_experiment_event(event_type: str, **payload: Any) -> None:
    experiment = payload.get("experiment")
    if not experiment:
        session = payload.get("session")
        submission = payload.get("submission")
        experiment = (
            (session or {}).get("experiment")
            or (submission or {}).get("experiment")
        )

    event_payload = {key: value for key, value in payload.items() if value is not None}
    event_payload["experiment_context_present"] = bool(experiment)
    if not experiment:
        event_payload["experiment_context_missing"] = True

    # Fire-and-forget: Der blockierende Mongo-Write darf weder den Event-Loop
    # noch die Antwortzeit belasten; log_event fängt Fehler selbst ab.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        experiment_logger.log_event(event_type, event_payload)
        return
    loop.run_in_executor(None, experiment_logger.log_event, event_type, event_payload)


async def _get_submission(submission_id: str) -> Submission | None:
    sub = _submissions.get(submission_id)
    if sub is not None:
        return sub

    persisted = await asyncio.to_thread(submission_store.load, submission_id)
    if persisted is not None:
        _submissions[submission_id] = persisted
        return persisted

    return None


# ---------------------------------------------------------------------------
# Zugangs-Check (Login-Feedback fürs Frontend)
# ---------------------------------------------------------------------------

@router.post("/auth/student/verify", dependencies=[Depends(rate_limit(10, 60, scope="verify"))])
async def verify_student_access() -> dict:
    # require_student_access (Router-Dependency) hat den Code bereits geprüft;
    # hier landet nur, wer durchgelassen wurde.
    return {"ok": True, "required": student_access_required()}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    dependencies=[Depends(rate_limit(20, 60, scope="create_session"))],
)
async def create_session(body: SessionCreate):
    case = case_manager.get(body.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    session_id = str(uuid.uuid4())
    tp = case.target_tp or current_tp_phase()
    experiment = _normalize_experiment(body.experiment)

    session = Session(
        session_id=session_id,
        user_id=body.user_id,
        case_id=body.case_id,
        tp_phase=tp,
        experiment=experiment,
    )
    _sessions[session_id] = session
    await asyncio.to_thread(session_store.save, session)

    _log_experiment_event(
        "session_created",
        session=session.model_dump(mode="json", exclude_none=True),
        experiment=experiment.model_dump(mode="json", exclude_none=True) if experiment else None,
    )

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

@router.post(
    "/sessions/{session_id}/chat",
    response_model=ChatResponse,
    dependencies=[Depends(rate_limit(15, 60, scope="chat", by_path_param="session_id"))],
)
async def chat(session_id: str, body: ChatRequest):
    session = await _load_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")

    case = case_manager.get(session.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")
    orchestrator = AgentOrchestrator(api_key=api_key)

    case_context = f"{case.title}\n{case.tagline}\n" + "\n".join(
        s.content[:400] for s in case.sections[:2]
    )

    session.message_count += 1
    session.last_activity = naive_utcnow()

    try:
        agent_type, response_text = await orchestrator.respond(
            session=session,
            user_message=body.content,
            history=body.history,
            case_context=case_context,
        )
    except Exception as e:
        logger.error("chat_error", error=str(e), type=type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail="Der Assistent ist gerade nicht erreichbar. Bitte versucht es gleich noch einmal.",
        )

    await asyncio.to_thread(session_store.save, session)

    _log_experiment_event(
        "chat_turn_completed",
        session_id=session.session_id,
        case_id=session.case_id,
        user_id=session.user_id,
        experiment=(
            session.experiment.model_dump(mode="json", exclude_none=True)
            if session.experiment else None
        ),
        message_count=session.message_count,
        history_length=len(body.history),
        user_message=body.content,
        agent_type=agent_type,
        assistant_message=response_text,
    )

    return ChatResponse(agent_type=agent_type, content=response_text)


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

@router.post(
    "/submissions",
    response_model=dict,
    status_code=201,
    dependencies=[Depends(rate_limit(20, 60, scope="create_submission"))],
)
async def create_submission(body: SubmissionCreate):
    sub_id = str(uuid.uuid4())
    experiment = _normalize_experiment(body.experiment)
    participant_id = _participant_id(
        user_id=body.user_id,
        matrikelnummer=body.matrikelnummer,
        experiment=experiment,
    )
    submission = Submission(
        submission_id=sub_id,
        user_id=body.user_id,
        matrikelnummer=participant_id,
        case_id=body.case_id,
        target_tp=body.target_tp,
        experiment=experiment,
    )
    _submissions[sub_id] = submission
    await asyncio.to_thread(submission_store.save, submission)

    _log_experiment_event(
        "submission_created",
        submission=submission.model_dump(mode="json", exclude_none=True),
        experiment=experiment.model_dump(mode="json", exclude_none=True) if experiment else None,
    )

    return {"submission_id": sub_id}


@router.post(
    "/submissions/{submission_id}/answer",
    dependencies=[Depends(rate_limit(60, 60, scope="answer", by_path_param="submission_id"))],
)
async def submit_answer(submission_id: str, body: AnswerSubmit):
    sub = await _get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission nicht gefunden")
    if sub.status == SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Submission bereits abgeschlossen")
    sub.answers[body.question_id] = body.answer_text
    await asyncio.to_thread(submission_store.save, sub)

    _log_experiment_event(
        "submission_answer_saved",
        submission_id=sub.submission_id,
        case_id=sub.case_id,
        user_id=sub.user_id,
        participant_id=sub.matrikelnummer,
        experiment=(
            sub.experiment.model_dump(mode="json", exclude_none=True)
            if sub.experiment else None
        ),
        question_id=body.question_id,
        answer_text=body.answer_text,
        answer_word_count=len(body.answer_text.split()),
    )

    return {"ok": True}


@router.post(
    "/submissions/{submission_id}/submit",
    response_model=SubmissionResult,
    dependencies=[Depends(rate_limit(5, 60, scope="submit", by_path_param="submission_id"))],
)
async def submit_and_evaluate(submission_id: str):
    sub = await _get_submission(submission_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission nicht gefunden")

    case = case_manager.get(sub.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")
    evaluator = RubricEvaluator(api_key=api_key)

    sub.status = SubmissionStatus.SUBMITTED
    sub.submitted_at = naive_utcnow()
    await asyncio.to_thread(submission_store.save, sub)

    _log_experiment_event(
        "submission_submitted",
        submission=sub.model_dump(mode="json", exclude_none=True),
        experiment=(
            sub.experiment.model_dump(mode="json", exclude_none=True)
            if sub.experiment else None
        ),
    )

    try:
        result = await evaluator.evaluate_submission(sub, case)
    except Exception as e:
        logger.error("evaluation_error", submission_id=submission_id, error=str(e), type=type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail="Die Auswertung ist gerade nicht möglich. Eure Antworten sind gespeichert — bitte versucht es gleich noch einmal.",
        )

    sub.status = SubmissionStatus.EVALUATED
    sub.evaluated_at = naive_utcnow()
    sub.scores = result.scores
    sub.total_points = result.total_points
    sub.max_points = result.max_points
    sub.percentage = result.percentage
    sub.canvas_alignment_pct = result.canvas_alignment_pct
    sub.rubric_fit_pct = result.rubric_fit_pct
    sub.canvas_exemplar_candidate = result.canvas_exemplar_candidate
    await asyncio.to_thread(submission_store.save, sub)

    # Persistieren für Dashboard
    out = {
        "submission_id": sub.submission_id,
        "matrikelnummer": sub.matrikelnummer,
        "case_id": sub.case_id,
        "target_tp": sub.target_tp,
        "percentage": sub.percentage,
        "canvas_alignment_pct": sub.canvas_alignment_pct,
        "rubric_fit_pct": sub.rubric_fit_pct,
        "canvas_exemplar_candidate": sub.canvas_exemplar_candidate,
        "submitted_at": sub.submitted_at,
        "evaluated_at": sub.evaluated_at,
        "scores": [s.model_dump() for s in sub.scores],
        "experiment": (
            sub.experiment.model_dump(mode="json", exclude_none=True)
            if sub.experiment else None
        ),
    }
    await asyncio.to_thread(dashboard_store.save_result, out)

    _log_experiment_event(
        "submission_evaluated",
        submission=sub.model_dump(mode="json", exclude_none=True),
        result=result.model_dump(mode="json", exclude_none=True),
        experiment=(
            sub.experiment.model_dump(mode="json", exclude_none=True)
            if sub.experiment else None
        ),
    )

    if result.canvas_exemplar_candidate:
        _log_experiment_event(
            "canvas_exemplar_candidate",
            submission_id=sub.submission_id,
            case_id=sub.case_id,
            participant_id=sub.matrikelnummer,
            percentage=result.percentage,
            canvas_alignment_pct=result.canvas_alignment_pct,
            rubric_fit_pct=result.rubric_fit_pct,
            experiment=(
                sub.experiment.model_dump(mode="json", exclude_none=True)
                if sub.experiment else None
            ),
            scores=[score.model_dump(mode="json", exclude_none=True) for score in result.scores],
        )

    return result
