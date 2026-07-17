"""Admin-Interface — Case-Generierung und Approval-Workflow."""

import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import reject_revoked_teacher_session, require_api_key
from backend.cases.generator import CaseGenerator
from backend.cases.manager import case_manager
from backend.cases.validator import CaseValidationReport, validate_case
from backend.llm import get_openrouter_key
from backend.models.case import (
    AgentGuidance,
    Case,
    CaseDifficulty,
    CaseEditEvent,
    CaseExhibit,
    CaseQuestion,
    CaseSection,
    CaseStatus,
    CaseSummary,
    GlossaryTermSpec,
)

logger = structlog.get_logger(__name__)
# Widerrufene Teacher-Sessions abweisen (Header kommt nur vom Teacher-Proxy;
# Requests ohne Header — Studierenden-Frontend, Skripte — sind unberührt).
router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(reject_revoked_teacher_session)],
)


# ---------------------------------------------------------------------------
# Request-Schemas
# ---------------------------------------------------------------------------

class GenerateCaseRequest(BaseModel):
    industry: str
    country: str
    target_tp: int            # 1–4
    difficulty: str = CaseDifficulty.TP1
    language: str = "de"      # "de" | "en"


class ReviewCaseRequest(BaseModel):
    reviewer: str             # Name oder Kennung des Dozenten
    notes: str = ""
    force: bool = False       # Freigabe trotz Validierungs-Fehlern erzwingen


class UpdateCaseRequest(BaseModel):
    """Partielle Bearbeitung durch die Lehrperson — nur gesetzte Felder ändern."""
    editor: str = ""
    title: str | None = None
    tagline: str | None = None
    sections: list[CaseSection] | None = None
    exhibits: list[CaseExhibit] | None = None
    questions: list[CaseQuestion] | None = None
    glossary: list[GlossaryTermSpec] | None = None
    agent_guidance: AgentGuidance | None = None


class RegeneratePartRequest(BaseModel):
    editor: str = ""
    target: str               # "section" | "exhibit" | "question" | "tagline"
    target_id: str | None = None
    instructions: str = Field(default="", max_length=2000)


def _require_case(case_id: str) -> Case:
    case = case_manager.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    return case


def _bump_revision(case: Case, editor: str, action: str, detail: str) -> None:
    case.revision += 1
    case.edit_history.append(CaseEditEvent(editor=editor, action=action, detail=detail))
    # Inhaltliche Änderungen an einem freigegebenen Case erfordern erneute Freigabe.
    if case.status == CaseStatus.APPROVED:
        case.status = CaseStatus.DRAFT
        case.approved_at = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/cases/generate", response_model=Case, dependencies=[Depends(require_api_key)])
async def generate_case(body: GenerateCaseRequest):
    """Generiert einen AI-Draft-Case und legt ihn im Pool ab."""
    if body.language not in {"de", "en"}:
        raise HTTPException(status_code=400, detail="Ungültige Sprache")

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")

    generator = CaseGenerator(api_key=api_key)

    try:
        case = await generator.generate_draft(
            industry=body.industry,
            country=body.country,
            target_tp=body.target_tp,
            difficulty=body.difficulty,
            language=body.language,
        )
    except Exception as e:
        logger.error("case_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Generierung fehlgeschlagen: {e}")

    await asyncio.to_thread(case_manager.save, case)
    return case


@router.get("/cases", response_model=list[CaseSummary])
async def list_cases(status: str | None = None, language: str | None = None):
    """Listet alle Cases im Pool, optional gefiltert nach Status."""
    if language is not None and language not in {"de", "en"}:
        raise HTTPException(status_code=400, detail="Ungültige Sprache")
    return case_manager.list_all(status=status, language=language)


@router.get("/cases/{case_id}", response_model=Case)
async def get_case(case_id: str):
    case = case_manager.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    return case


@router.patch("/cases/{case_id}", response_model=Case, dependencies=[Depends(require_api_key)])
async def update_case(case_id: str, body: UpdateCaseRequest):
    """Bearbeitet Felder eines Cases (Editor-Flow der Lehrperson)."""
    case = _require_case(case_id)

    changed: list[str] = []
    for field in ("title", "tagline", "sections", "exhibits", "questions", "glossary", "agent_guidance"):
        value = getattr(body, field)
        if value is not None:
            setattr(case, field, value)
            changed.append(field)

    if not changed:
        return case

    _bump_revision(case, editor=body.editor or "unbekannt", action="edited", detail=", ".join(changed))
    await asyncio.to_thread(case_manager.save, case)
    logger.info("case_edited", case_id=case_id, fields=changed, revision=case.revision)
    return case


@router.post("/cases/{case_id}/regenerate", response_model=Case, dependencies=[Depends(require_api_key)])
async def regenerate_case_part(case_id: str, body: RegeneratePartRequest):
    """Regeneriert gezielt einen Teil des Cases nach Anweisung der Lehrperson."""
    case = _require_case(case_id)

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")
    generator = CaseGenerator(api_key=api_key)

    try:
        case = await generator.regenerate_part(
            case,
            target=body.target,
            target_id=body.target_id,
            instructions=body.instructions,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("case_regenerate_failed", case_id=case_id, error=str(e), type=type(e).__name__)
        raise HTTPException(
            status_code=503,
            detail="Regenerierung gerade nicht möglich — bitte erneut versuchen.",
        )

    _bump_revision(
        case,
        editor=body.editor or "unbekannt",
        action="regenerated",
        detail=f"{body.target}:{body.target_id or '-'} — {body.instructions[:200]}",
    )
    await asyncio.to_thread(case_manager.save, case)
    return case


@router.get("/cases/{case_id}/validate", response_model=CaseValidationReport, dependencies=[Depends(require_api_key)])
async def validate_case_endpoint(case_id: str):
    """Führt die Qualitäts-Checks aus, ohne den Status zu ändern."""
    return validate_case(_require_case(case_id))


@router.post("/cases/{case_id}/approve", response_model=Case, dependencies=[Depends(require_api_key)])
async def approve_case(case_id: str, body: ReviewCaseRequest):
    """Gibt einen Case-Draft frei — nur wenn die Qualitäts-Checks bestehen.

    Fehler blockieren die Freigabe (422 mit Report); mit force=True kann die
    Lehrperson bewusst übersteuern (wird in der Historie vermerkt).
    """
    case = _require_case(case_id)
    report = validate_case(case)
    if not report.ok and not body.force:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validierung fehlgeschlagen — Freigabe blockiert.",
                "issues": [issue.model_dump() for issue in report.issues],
            },
        )

    notes = body.notes
    if not report.ok and body.force:
        notes = f"{notes} [Freigabe trotz Validierungsfehlern erzwungen]".strip()

    case = await asyncio.to_thread(case_manager.approve, case_id, reviewer=body.reviewer, notes=notes)
    logger.info("case_approved", case_id=case_id, reviewer=body.reviewer, forced=not report.ok)
    return case


@router.post("/cases/{case_id}/retire", response_model=Case, dependencies=[Depends(require_api_key)])
async def retire_case(case_id: str, body: ReviewCaseRequest):
    """Nimmt einen freigegebenen Case aus dem Studierenden-Pool."""
    case = await asyncio.to_thread(case_manager.retire, case_id, reviewer=body.reviewer, notes=body.notes)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    logger.info("case_retired", case_id=case_id, reviewer=body.reviewer)
    return case


@router.post("/cases/{case_id}/restore", response_model=Case, dependencies=[Depends(require_api_key)])
async def restore_case(case_id: str, body: ReviewCaseRequest):
    """Macht ein Archivieren rückgängig und bringt den Case zurück in den Pool."""
    case = await asyncio.to_thread(case_manager.restore, case_id, reviewer=body.reviewer, notes=body.notes)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    logger.info("case_restored", case_id=case_id, reviewer=body.reviewer)
    return case


@router.post("/cases/{case_id}/reject", response_model=Case, dependencies=[Depends(require_api_key)])
async def reject_case(case_id: str, body: ReviewCaseRequest):
    """Lehnt einen Case-Draft ab."""
    case = await asyncio.to_thread(case_manager.reject, case_id, reviewer=body.reviewer, notes=body.notes)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    logger.info("case_rejected", case_id=case_id, reviewer=body.reviewer)
    return case
