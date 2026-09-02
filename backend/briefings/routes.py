"""Routen der KI-Briefings: Master-Upload, Abruf, DOCX-Download.

Auth-Kette: Router-weit ``require_api_key`` (fail-closed, 503 ohne Key) +
``reject_revoked_teacher_session``. Der Browser erreicht diese Routen nur
über den Teacher-Proxy des Frontends, der den X-API-Key server-seitig
ergänzt und die verifizierte Tutor-Identität als Header mitschickt:

- ``X-Teacher-Id``     — Tutor-Kennung aus der signierten Session
                         (Konvention: Kennung = Übungsgruppe, z.B. ``UEG07``)
- ``X-Teacher-Master`` — ``1`` nur für den Master-Tutor

Sichtbarkeit: Der Master sieht alles (inkl. interner Einstufung). Eine
reguläre ÜGL sieht nur die Briefings ihrer eigenen Übungsgruppe — und nie
die interne Kriterien-Einstufung. Requests OHNE Identitäts-Header (Skripte
direkt mit API-Key) gelten als Operator (= Master), analog zur
jti-Sperrliste, deren Header ebenfalls nur der Proxy setzt.

Es werden KEINE hochgeladenen Dateien persistiert — nur der extrahierte
Text wird verdichtet und verworfen; gespeichert wird das Briefing, die
formale Vorprüfung und die interne Einstufung. Mitgliedernamen vom
Deckblatt werden nie übernommen.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import structlog
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.auth import reject_revoked_teacher_session, require_api_key
from backend.briefings.docx_render import render_briefing_docx
from backend.briefings.extraction import (
    ZipValidationError,
    build_code,
    extract_submission,
    iter_submission_entries,
    normalize_ueg,
)
from backend.briefings.formal import formal_checks
from backend.briefings.generator import BriefingGenerator
from backend.briefings.rubrics import SUPPORTED_TPS, BriefingRubric, load_rubric
from backend.db.briefing_store import briefing_store
from backend.llm import get_openrouter_key
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/briefings",
    tags=["briefings"],
    dependencies=[Depends(require_api_key), Depends(reject_revoked_teacher_session)],
)

MAX_UPLOAD_BYTES = 400 * 1024 * 1024   # ZIP-Rohgrösse (komprimiert)
UPLOAD_CONCURRENCY = 8                  # gleichzeitig entpackte + verdichtete Dateien
STAMMGRUPPEN = range(1, 9)

TEACHER_ID_HEADER = "X-Teacher-Id"
TEACHER_MASTER_HEADER = "X-Teacher-Master"

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# Tutor-Kontext
# ---------------------------------------------------------------------------

@dataclass
class TeacherContext:
    tutor_id: str | None
    is_master: bool
    ueg: str            # eigene Übungsgruppe (normalisiert) oder ""


async def teacher_context(
    x_teacher_id: str | None = Header(default=None, alias=TEACHER_ID_HEADER),
    x_teacher_master: str | None = Header(default=None, alias=TEACHER_MASTER_HEADER),
) -> TeacherContext:
    if x_teacher_id is None and x_teacher_master is None:
        return TeacherContext(tutor_id=None, is_master=True, ueg="")
    tutor_id = (x_teacher_id or "").strip()
    is_master = (x_teacher_master or "").strip().lower() in {"1", "true", "yes"}
    return TeacherContext(tutor_id=tutor_id or None, is_master=is_master, ueg=normalize_ueg(tutor_id))


def require_master(ctx: TeacherContext = Depends(teacher_context)) -> TeacherContext:
    if not ctx.is_master:
        raise HTTPException(status_code=403, detail="Nur für den Master-Tutor")
    return ctx


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class BriefingRecord(BaseModel):
    briefing_id: str
    batch_id: str
    filename: str
    format: str = ""
    target_tp: int
    ueg: str = ""                     # "" = nicht zuordenbar → Review
    sg: int | None = None
    code: str | None = None
    code_source: str | None = None
    status: str                       # "briefed" | "extraction_failed" | "no_content"
    uploaded_at: str
    generated_at: str | None = None
    uploaded_by: str | None = None
    evaluation_status: str = "ok"     # "ok" | "technical_fallback" | "no_content" | "extraction_failed"
    needs_human_review: bool = False
    review_reason: str | None = None
    guardrail_hits: list[str] = Field(default_factory=list)
    formal: dict = Field(default_factory=dict)
    briefing: dict = Field(default_factory=dict)
    assessment: dict = Field(default_factory=dict)   # intern — nur Master
    text_chars: int = 0
    source: str = "briefing_upload"


PUBLIC_FIELDS = set(BriefingRecord.model_fields) - {"assessment"}


class BriefingPublic(BaseModel):
    """Tutor-sichtbare Sicht: ohne interne Einstufung."""
    briefing_id: str
    batch_id: str
    filename: str
    format: str = ""
    target_tp: int
    ueg: str = ""
    sg: int | None = None
    code: str | None = None
    code_source: str | None = None
    status: str
    uploaded_at: str
    generated_at: str | None = None
    uploaded_by: str | None = None
    evaluation_status: str = "ok"
    needs_human_review: bool = False
    review_reason: str | None = None
    guardrail_hits: list[str] = Field(default_factory=list)
    formal: dict = Field(default_factory=dict)
    briefing: dict = Field(default_factory=dict)
    text_chars: int = 0
    source: str = "briefing_upload"


class BriefingBatchResponse(BaseModel):
    batch_id: str
    target_tp: int
    briefings: list[BriefingPublic]
    briefed_count: int
    unassigned_count: int
    failed_count: int
    review_count: int


class AssignmentPatch(BaseModel):
    ueg: str
    sg: int = Field(ge=1, le=8)


class BriefingOverviewRow(BaseModel):
    target_tp: int
    ueg: str
    briefed_count: int
    review_count: int
    missing_groups: list[int]
    latest_uploaded_at: str | None = None


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _public(record: dict) -> BriefingPublic:
    return BriefingPublic(**{k: v for k, v in record.items() if k in BriefingPublic.model_fields})


def _latest_per_group(records: list[dict]) -> list[dict]:
    """Bei Mehrfach-Uploads derselben Stammgruppe gewinnt der neueste
    Datensatz; nicht zuordenbare Datensätze bleiben alle erhalten."""
    latest: dict[tuple, dict] = {}
    unassigned: list[dict] = []
    for r in records:
        if r.get("ueg") and r.get("sg"):
            key = (int(r.get("target_tp", 0)), r["ueg"], int(r["sg"]))
            if key not in latest or str(r.get("uploaded_at", "")) > str(latest[key].get("uploaded_at", "")):
                latest[key] = r
        else:
            unassigned.append(r)
    return list(latest.values()) + unassigned


def _visible_records(ctx: TeacherContext, *, tp: int | None, ueg: str | None) -> list[dict]:
    records = briefing_store.load_all()
    if tp is not None:
        records = [r for r in records if int(r.get("target_tp", 0)) == tp]
    if ctx.is_master:
        if ueg:
            wanted = normalize_ueg(ueg)
            records = [r for r in records if r.get("ueg") == wanted]
    else:
        if not ctx.ueg:
            return []
        records = [r for r in records if r.get("ueg") == ctx.ueg]
    records = _latest_per_group(records)
    records.sort(key=lambda r: (int(r.get("target_tp", 0)), r.get("ueg") or "~", int(r.get("sg") or 99)))
    return records


def _rubric_or_422(tp: int) -> BriefingRubric:
    try:
        return load_rubric(tp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _missing_groups(records: list[dict]) -> list[int]:
    present = {int(r["sg"]) for r in records if r.get("sg")}
    return [n for n in STAMMGRUPPEN if n not in present]


# ---------------------------------------------------------------------------
# Verarbeitung eines Eintrags
# ---------------------------------------------------------------------------

async def _process_entry(
    *,
    generator: BriefingGenerator,
    rubric: BriefingRubric,
    batch_id: str,
    target_tp: int,
    filename: str,
    data: bytes,
    uploaded_by: str | None,
) -> BriefingRecord:
    briefing_id = str(uuid.uuid4())
    uploaded_at = naive_utcnow().isoformat()

    try:
        sub = await asyncio.to_thread(extract_submission, filename, data, target_tp)
    except ValueError as exc:
        logger.warning("briefing_extraction_failed", filename=filename, error=str(exc))
        return BriefingRecord(
            briefing_id=briefing_id,
            batch_id=batch_id,
            filename=filename,
            format=filename.rsplit(".", 1)[-1].lower(),
            target_tp=target_tp,
            status="extraction_failed",
            uploaded_at=uploaded_at,
            uploaded_by=uploaded_by,
            evaluation_status="extraction_failed",
            needs_human_review=True,
            review_reason=str(exc),
            formal={"filename": filename},
        )

    kd = sub.kenndaten
    result = await generator.generate(briefing_id=briefing_id, rubric=rubric, sub=sub)
    status = "no_content" if result["evaluation_status"] == "no_content" else "briefed"

    return BriefingRecord(
        briefing_id=briefing_id,
        batch_id=batch_id,
        filename=filename,
        format=sub.format,
        target_tp=target_tp,
        ueg=kd.ueg,
        sg=kd.sg,
        code=(build_code(target_tp, kd.ueg, kd.sg) if kd.ueg and kd.sg else None),
        code_source=kd.source or None,
        status=status,
        uploaded_at=uploaded_at,
        generated_at=naive_utcnow().isoformat(),
        uploaded_by=uploaded_by,
        evaluation_status=result["evaluation_status"],
        needs_human_review=bool(result["needs_human_review"]) or not (kd.ueg and kd.sg),
        review_reason=result.get("review_reason")
        or (None if (kd.ueg and kd.sg) else "Übungsgruppe/Stammgruppe nicht erkennbar — bitte zuordnen."),
        guardrail_hits=list(result.get("guardrail_hits", [])),
        formal=formal_checks(sub, rubric, target_tp),
        briefing=result["briefing"],
        assessment=result["assessment"],
        text_chars=sub.baustein1_chars + sub.baustein2_chars,
    )


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=BriefingBatchResponse)
async def upload_submissions(
    file: UploadFile = File(...),
    target_tp: int = Form(...),
    ctx: TeacherContext = Depends(require_master),
):
    """Master-Upload: ZIP mit Stammgruppen-Abgaben (PPTX/DOCX/PDF) → je
    Datei ein Briefing. Speichert nur Briefing + Einstufung, nie Dateien."""
    if target_tp not in SUPPORTED_TPS:
        raise HTTPException(status_code=422, detail="target_tp muss 1–5 sein")
    rubric = _rubric_or_422(target_tp)

    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")

    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="ZIP ist zu gross (max. 400 MB).")

    try:
        entries = list(iter_submission_entries(data))
    except ZipValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    del data

    generator = BriefingGenerator(api_key=api_key)
    batch_id = str(uuid.uuid4())
    gate = asyncio.Semaphore(UPLOAD_CONCURRENCY)

    async def _guarded(filename: str, payload: bytes) -> BriefingRecord:
        async with gate:
            return await _process_entry(
                generator=generator,
                rubric=rubric,
                batch_id=batch_id,
                target_tp=target_tp,
                filename=filename,
                data=payload,
                uploaded_by=ctx.tutor_id,
            )

    records = await asyncio.gather(*(_guarded(name, payload) for name, payload in entries))

    for record in records:
        await asyncio.to_thread(briefing_store.save, record.model_dump())

    briefed = sum(1 for r in records if r.status == "briefed")
    unassigned = sum(1 for r in records if r.status != "extraction_failed" and not (r.ueg and r.sg))
    failed = sum(1 for r in records if r.status == "extraction_failed")
    review = sum(1 for r in records if r.needs_human_review)
    logger.info(
        "briefing_batch_processed",
        batch_id=batch_id,
        target_tp=target_tp,
        total=len(records),
        briefed=briefed,
        unassigned=unassigned,
        failed=failed,
        review=review,
        uploaded_by=ctx.tutor_id,
    )
    return BriefingBatchResponse(
        batch_id=batch_id,
        target_tp=target_tp,
        briefings=[_public(r.model_dump()) for r in records],
        briefed_count=briefed,
        unassigned_count=unassigned,
        failed_count=failed,
        review_count=review,
    )


@router.get("/overview", response_model=list[BriefingOverviewRow])
async def briefing_overview(
    tp: int | None = Query(default=None, ge=1, le=5),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Je Touchpoint und Übungsgruppe: wie viele Briefings liegen vor,
    welche Stammgruppen fehlen. ÜGL sehen nur die eigene Übungsgruppe."""
    records = _visible_records(ctx, tp=tp, ueg=None)
    groups: dict[tuple[int, str], list[dict]] = {}
    for r in records:
        groups.setdefault((int(r.get("target_tp", 0)), r.get("ueg") or ""), []).append(r)
    rows = [
        BriefingOverviewRow(
            target_tp=key[0],
            ueg=key[1],
            briefed_count=sum(1 for r in items if r.get("status") == "briefed"),
            review_count=sum(1 for r in items if r.get("needs_human_review")),
            missing_groups=_missing_groups(items) if key[1] else [],
            latest_uploaded_at=max((str(r.get("uploaded_at", "")) for r in items), default=None),
        )
        for key, items in groups.items()
    ]
    rows.sort(key=lambda row: (row.target_tp, row.ueg or "~"))
    return rows


@router.get("/docx")
async def download_briefing_bundle(
    tp: int = Query(..., ge=1, le=5),
    ueg: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """DOCX mit allen Briefings einer Übungsgruppe für einen Touchpoint.
    ÜGL: eigene Übungsgruppe; Master: ``ueg`` erforderlich."""
    rubric = _rubric_or_422(tp)
    if ctx.is_master:
        wanted = normalize_ueg(ueg or "")
        if not wanted:
            raise HTTPException(status_code=422, detail="ueg fehlt oder ist ungültig (z.B. UEG07)")
    else:
        wanted = ctx.ueg
        if not wanted:
            raise HTTPException(
                status_code=403,
                detail="Ihre Tutor-Kennung ist keiner Übungsgruppe zugeordnet (erwartet z.B. UEG07).",
            )
    records = _visible_records(ctx, tp=tp, ueg=wanted)
    if not records:
        raise HTTPException(status_code=404, detail="Keine Briefings für diese Übungsgruppe")
    payload = await asyncio.to_thread(
        render_briefing_docx, records, rubric=rubric, ueg=wanted, missing_groups=_missing_groups(records)
    )
    filename = f"KI-Briefing_TP{tp}_{wanted}.docx"
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[BriefingPublic])
async def list_briefings(
    tp: int | None = Query(default=None, ge=1, le=5),
    ueg: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Briefings (tutor-sichtbare Sicht). ÜGL: nur die eigene Übungsgruppe."""
    return [_public(r) for r in _visible_records(ctx, tp=tp, ueg=ueg)]


@router.get("/{briefing_id}", response_model=BriefingPublic)
async def get_briefing(briefing_id: str, ctx: TeacherContext = Depends(teacher_context)):
    record = briefing_store.get(briefing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    if not ctx.is_master and record.get("ueg") != ctx.ueg:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    return _public(record)


@router.get("/{briefing_id}/assessment")
async def get_assessment(briefing_id: str, ctx: TeacherContext = Depends(require_master)):
    """Interne Kriterien-Einstufung (Niveau je Kriterium) — nur Master."""
    record = briefing_store.get(briefing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    return {
        "briefing_id": briefing_id,
        "target_tp": record.get("target_tp"),
        "ueg": record.get("ueg"),
        "sg": record.get("sg"),
        "code": record.get("code"),
        "evaluation_status": record.get("evaluation_status"),
        "assessment": record.get("assessment", {}),
    }


@router.get("/{briefing_id}/docx")
async def download_single_briefing(briefing_id: str, ctx: TeacherContext = Depends(teacher_context)):
    record = briefing_store.get(briefing_id)
    if not record or (not ctx.is_master and record.get("ueg") != ctx.ueg):
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    rubric = _rubric_or_422(int(record.get("target_tp", 0)))
    payload = await asyncio.to_thread(
        render_briefing_docx, [record], rubric=rubric, ueg=record.get("ueg") or ""
    )
    label = record.get("code") or briefing_id[:8]
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="KI-Briefing_{label}.docx"'},
    )


@router.patch("/{briefing_id}", response_model=BriefingPublic)
async def patch_assignment(
    briefing_id: str, patch: AssignmentPatch, ctx: TeacherContext = Depends(require_master)
):
    """Zuordnung Übungsgruppe/Stammgruppe nachtragen oder korrigieren —
    das Briefing selbst bleibt unverändert."""
    record = briefing_store.get(briefing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    ueg = normalize_ueg(patch.ueg)
    if not ueg:
        raise HTTPException(status_code=422, detail="Übungsgruppe ungültig (erwartet z.B. UEG07)")
    tp = int(record.get("target_tp", 0))
    record["ueg"] = ueg
    record["sg"] = patch.sg
    record["code"] = build_code(tp, ueg, patch.sg)
    record["code_source"] = "manual"
    formal = dict(record.get("formal") or {})
    formal["code"] = record["code"]
    formal["code_valid"] = True
    formal["code_matches_tp"] = True
    record["formal"] = formal
    if record.get("review_reason", "") and "nicht erkennbar" in str(record.get("review_reason")):
        record["review_reason"] = None
        record["needs_human_review"] = bool(record.get("guardrail_hits")) or (
            record.get("evaluation_status") not in ("ok",)
        )
    await asyncio.to_thread(briefing_store.save, record)
    logger.info("briefing_assigned", briefing_id=briefing_id, ueg=ueg, sg=patch.sg, by=ctx.tutor_id)
    return _public(record)
