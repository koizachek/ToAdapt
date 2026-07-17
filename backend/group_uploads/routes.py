"""Master-Tutor-Upload: ZIP mit Gruppenarbeiten hochladen und bewerten.

Auth-Kette: Router-weit `require_api_key` (fail-closed, 503 ohne Key) — der
Browser erreicht diese Routen nur über den Teacher-Proxy des Frontends, der
den X-API-Key server-seitig ergänzt und `/group-uploads`-Pfade zusätzlich auf
das Master-Flag der Teacher-Session beschränkt. Reguläre Tutor:innen sehen
die Ergebnisse nur aggregiert im Gruppen-Dashboard.

Es werden KEINE hochgeladenen Dateien persistiert — nur der extrahierte Text
wird bewertet und verworfen; gespeichert wird ausschließlich das
Bewertungsergebnis (Scores, Gruppencode, Dateiname).
"""

from __future__ import annotations

import asyncio
import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from backend.anonymize import normalize_group_code
from backend.auth import reject_revoked_teacher_session, require_api_key
from backend.db.group_upload_store import group_upload_store
from backend.group_uploads.evaluator import GROUP_TP_MAX_POINTS, GroupWorkEvaluator
from backend.group_uploads.extraction import (
    ZipValidationError,
    extract_pdf_text,
    list_pdf_entries,
    parse_group_code,
)
from backend.llm import get_openrouter_key
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/group-uploads",
    tags=["group-uploads"],
    dependencies=[Depends(require_api_key), Depends(reject_revoked_teacher_session)],
)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # ZIP-Rohgröße (komprimiert)


class GroupUploadRecord(BaseModel):
    upload_id: str
    batch_id: str
    filename: str
    group_code: str = ""                     # "" = nicht zuordenbar → Review
    target_tp: int
    status: str                              # "evaluated" | "extraction_failed"
    uploaded_at: str
    evaluated_at: str | None = None
    total_points: float = 0.0
    max_points: float = 0.0
    percentage: float = 0.0
    needs_human_review: bool = False
    evaluation_status: str = "ok"
    scores: list[dict] = Field(default_factory=list)
    text_chars: int = 0
    source: str = "group_upload"


class GroupUploadBatchResponse(BaseModel):
    batch_id: str
    target_tp: int
    uploads: list[GroupUploadRecord]
    evaluated_count: int
    unassigned_count: int
    failed_count: int


class GroupCodePatch(BaseModel):
    group_code: str


async def _process_entry(
    *,
    evaluator: GroupWorkEvaluator,
    batch_id: str,
    target_tp: int,
    filename: str,
    pdf_bytes: bytes,
) -> GroupUploadRecord:
    upload_id = str(uuid.uuid4())
    uploaded_at = naive_utcnow().isoformat()

    try:
        text = await asyncio.to_thread(extract_pdf_text, pdf_bytes)
    except ValueError as exc:
        logger.warning("group_upload_extraction_failed", filename=filename, error=str(exc))
        return GroupUploadRecord(
            upload_id=upload_id,
            batch_id=batch_id,
            filename=filename,
            group_code="",
            target_tp=target_tp,
            status="extraction_failed",
            uploaded_at=uploaded_at,
            needs_human_review=True,
            evaluation_status="extraction_failed",
        )

    group_code = parse_group_code(text)
    score = await evaluator.evaluate_document(
        upload_id=upload_id, tp=target_tp, document_text=text
    )
    total = float(score["awarded_points"])
    maximum = float(score["max_points"])

    return GroupUploadRecord(
        upload_id=upload_id,
        batch_id=batch_id,
        filename=filename,
        group_code=group_code,
        target_tp=target_tp,
        status="evaluated",
        uploaded_at=uploaded_at,
        evaluated_at=naive_utcnow().isoformat(),
        total_points=total,
        max_points=maximum,
        percentage=round(total / maximum * 100, 1) if maximum else 0.0,
        needs_human_review=bool(score.get("needs_human_review")),
        evaluation_status=str(score.get("evaluation_status", "ok")),
        scores=[score],
        text_chars=len(text),
    )


@router.post("", response_model=GroupUploadBatchResponse)
async def upload_group_work(
    file: UploadFile = File(...),
    target_tp: int = Form(...),
):
    """Nimmt ein ZIP mit Gruppen-PDFs entgegen, bewertet jedes Dokument
    gegen die TP-Rubric und speichert die Ergebnisse (Store, D3-Muster)."""
    if target_tp not in GROUP_TP_MAX_POINTS:
        raise HTTPException(status_code=422, detail="target_tp muss 1–4 sein")

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ZIP ist zu groß (max. 100 MB).")

    try:
        entries = list_pdf_entries(data)
    except ZipValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    evaluator = GroupWorkEvaluator(api_key=api_key)
    batch_id = str(uuid.uuid4())

    # Parallel bewerten — die globale LLM-Semaphore (backend/llm.py) begrenzt
    # die tatsächliche Parallelität.
    records = await asyncio.gather(*(
        _process_entry(
            evaluator=evaluator,
            batch_id=batch_id,
            target_tp=target_tp,
            filename=filename,
            pdf_bytes=pdf_bytes,
        )
        for filename, pdf_bytes in entries
    ))

    for record in records:
        await asyncio.to_thread(group_upload_store.save_result, record.model_dump())

    evaluated = sum(1 for r in records if r.status == "evaluated")
    unassigned = sum(1 for r in records if r.status == "evaluated" and not r.group_code)
    failed = sum(1 for r in records if r.status == "extraction_failed")
    logger.info(
        "group_upload_batch_processed",
        batch_id=batch_id,
        target_tp=target_tp,
        total=len(records),
        evaluated=evaluated,
        unassigned=unassigned,
        failed=failed,
    )

    return GroupUploadBatchResponse(
        batch_id=batch_id,
        target_tp=target_tp,
        uploads=list(records),
        evaluated_count=evaluated,
        unassigned_count=unassigned,
        failed_count=failed,
    )


@router.get("", response_model=list[GroupUploadRecord])
async def list_group_uploads():
    """Alle bewerteten Gruppenarbeiten, neueste zuerst."""
    records = [GroupUploadRecord(**r) for r in group_upload_store.load_all()]
    records.sort(key=lambda r: r.uploaded_at, reverse=True)
    return records


@router.patch("/{upload_id}", response_model=GroupUploadRecord)
async def patch_group_code(upload_id: str, patch: GroupCodePatch):
    """Gruppenzuordnung nachtragen/korrigieren (Review nicht zuordenbarer
    Dokumente) — die Bewertung selbst bleibt unverändert."""
    record = group_upload_store.get(upload_id)
    if not record:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")

    normalized = normalize_group_code(patch.group_code)
    if not normalized:
        raise HTTPException(status_code=422, detail="Gruppencode darf nicht leer sein")

    record["group_code"] = normalized
    await asyncio.to_thread(group_upload_store.save_result, record)
    logger.info("group_upload_group_assigned", upload_id=upload_id, group_code=normalized)
    return GroupUploadRecord(**record)
