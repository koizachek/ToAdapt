"""Admin-Interface — Case-Generierung und Approval-Workflow."""

import os
import uuid

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.cases.generator import CaseGenerator
from backend.cases.manager import case_manager
from backend.models.case import CaseDifficulty, CaseSummary, Case

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Request-Schemas
# ---------------------------------------------------------------------------

class GenerateCaseRequest(BaseModel):
    industry: str
    country: str
    target_tp: int            # 1–4
    difficulty: str = CaseDifficulty.TP1


class ReviewCaseRequest(BaseModel):
    reviewer: str             # Name oder Kennung des Dozenten
    notes: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/cases/generate", response_model=Case)
async def generate_case(body: GenerateCaseRequest):
    """Generiert einen AI-Draft-Case und legt ihn im Pool ab."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY nicht konfiguriert")

    generator = CaseGenerator(api_key=api_key)

    try:
        case = await generator.generate_draft(
            industry=body.industry,
            country=body.country,
            target_tp=body.target_tp,
            difficulty=body.difficulty,
        )
    except Exception as e:
        logger.error("case_generation_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Generierung fehlgeschlagen: {e}")

    case_manager.save(case)
    return case


@router.get("/cases", response_model=list[CaseSummary])
async def list_cases(status: str | None = None):
    """Listet alle Cases im Pool, optional gefiltert nach Status."""
    return case_manager.list_all(status=status)


@router.get("/cases/{case_id}", response_model=Case)
async def get_case(case_id: str):
    case = case_manager.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    return case


@router.post("/cases/{case_id}/approve", response_model=Case)
async def approve_case(case_id: str, body: ReviewCaseRequest):
    """Gibt einen Case-Draft frei."""
    case = case_manager.approve(case_id, reviewer=body.reviewer, notes=body.notes)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    logger.info("case_approved", case_id=case_id, reviewer=body.reviewer)
    return case


@router.post("/cases/{case_id}/reject", response_model=Case)
async def reject_case(case_id: str, body: ReviewCaseRequest):
    """Lehnt einen Case-Draft ab."""
    case = case_manager.reject(case_id, reviewer=body.reviewer, notes=body.notes)
    if not case:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    logger.info("case_rejected", case_id=case_id, reviewer=body.reviewer)
    return case
