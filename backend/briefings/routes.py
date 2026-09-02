"""Routen der KI-Briefings: Master-Upload, Abruf, DOCX-Download.

Auth-Kette: Router-weit ``require_api_key`` (fail-closed, 503 ohne Key) +
``reject_revoked_teacher_session``. Der Browser erreicht diese Routen nur
über den Teacher-Proxy des Frontends, der den X-API-Key server-seitig
ergänzt und die verifizierte Tutor-Identität als Header mitschickt:

- ``X-Teacher-Id``     — Tutor-Kennung aus der signierten Session
                         (Konvention: Kennung nennt die Übungsgruppe(n),
                         z.B. ``UEG07`` oder ``UEG07+UEG12`` — eine ÜGL kann
                         mehrere Übungsgruppen führen; ``parse_uegs``)
- ``X-Teacher-Master`` — ``1`` nur für den Master-Tutor

Sichtbarkeit: Der Master sieht alles (inkl. interner Einstufung). Eine
reguläre ÜGL sieht nur die Briefings ihrer eigenen Übungsgruppen — und nie
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
import io
import uuid
import zipfile
from dataclasses import dataclass

import structlog
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.auth import API_KEY_HEADER, reject_revoked_teacher_session, require_api_key
from backend.briefings.batches import (
    batch_store,
    new_batch,
    run_batch,
    start_background,
    with_stale_flag,
)
from backend.briefings.docx_render import render_briefing_docx, render_feedback_docx
from backend.briefings.extraction import (
    ZipValidationError,
    build_code,
    extract_submission,
    iter_submission_entries,
    normalize_ueg,
    parse_uegs,
)
from backend.briefings.formal import formal_checks
from backend.briefings.generator import FeedbackGenerator
from backend.briefings.rubrics import (
    SUPPORTED_TPS,
    BriefingRubric,
    feedback_release_date,
    feedback_released,
    load_rubric,
)
from backend.briefings.upload_token import UPLOAD_TOKEN_HEADER, UploadTokenError, verify_upload_token
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
    uegs: list[str]     # eigene Übungsgruppen (normalisiert), leer = keine Zuordnung

    @property
    def ueg(self) -> str:
        return self.uegs[0] if self.uegs else ""

    def may_see(self, ueg: str | None) -> bool:
        return self.is_master or (bool(ueg) and ueg in self.uegs)


async def teacher_context(
    x_teacher_id: str | None = Header(default=None, alias=TEACHER_ID_HEADER),
    x_teacher_master: str | None = Header(default=None, alias=TEACHER_MASTER_HEADER),
) -> TeacherContext:
    if x_teacher_id is None and x_teacher_master is None:
        return TeacherContext(tutor_id=None, is_master=True, uegs=[])
    tutor_id = (x_teacher_id or "").strip()
    is_master = (x_teacher_master or "").strip().lower() in {"1", "true", "yes"}
    return TeacherContext(tutor_id=tutor_id or None, is_master=is_master, uegs=parse_uegs(tutor_id))


def require_master(ctx: TeacherContext = Depends(teacher_context)) -> TeacherContext:
    if not ctx.is_master:
        raise HTTPException(status_code=403, detail="Nur für den Master-Tutor")
    return ctx


async def upload_auth(
    x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER),
    x_upload_token: str | None = Header(default=None, alias=UPLOAD_TOKEN_HEADER),
    x_teacher_id: str | None = Header(default=None, alias=TEACHER_ID_HEADER),
    x_teacher_master: str | None = Header(default=None, alias=TEACHER_MASTER_HEADER),
) -> TeacherContext:
    """Upload-Route: X-API-Key (Proxy/Skripte) ODER kurzlebiges X-Upload-Token
    (Direkt-Upload aus dem Browser, weil Vercel Bodies auf 4,5 MB begrenzt).
    Beide Wege enden in einem Master-Kontext — sonst 403."""
    if x_api_key is not None:
        await require_api_key(x_api_key)
        ctx = await teacher_context(x_teacher_id, x_teacher_master)
        return require_master(ctx)
    try:
        payload = verify_upload_token(x_upload_token)
    except UploadTokenError as exc:
        status_code = 503 if "nicht konfiguriert" in str(exc) else 401
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    from backend.db.revoked_sessions_store import revoked_session_store

    jti = str(payload.get("jti") or "")
    if jti and revoked_session_store.is_revoked(jti):
        raise HTTPException(status_code=401, detail="Sitzung wurde abgemeldet — bitte neu einloggen")
    tutor = str(payload.get("tutor") or "") or None
    return TeacherContext(tutor_id=tutor, is_master=True, uegs=parse_uegs(tutor))


# Eigener Router für den Upload: KEIN router-weites require_api_key, weil der
# Direkt-Upload aus dem Browser per Upload-Token authentifiziert wird.
upload_router = APIRouter(
    prefix="/briefings",
    tags=["briefings"],
    dependencies=[Depends(reject_revoked_teacher_session)],
)


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
    # Produkt 2: KI-Feedback an die Stammgruppe — beim Upload erzeugt,
    # aber erst nach dem Termin freigegeben (feedback_only_after_session).
    feedback: dict = Field(default_factory=dict)
    feedback_status: str = "pending"                 # ok | technical_fallback | no_content | pending
    feedback_guardrail_hits: list[str] = Field(default_factory=list)
    feedback_needs_human_review: bool = False
    feedback_review_reason: str | None = None
    text_chars: int = 0
    source: str = "briefing_upload"


class BriefingPublic(BaseModel):
    """Tutor-sichtbare Sicht: ohne interne Einstufung; Feedback-Inhalt nur
    nach Freigabe (oder für den Master)."""
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
    feedback: dict = Field(default_factory=dict)
    feedback_status: str = "pending"
    feedback_guardrail_hits: list[str] = Field(default_factory=list)
    feedback_needs_human_review: bool = False
    feedback_review_reason: str | None = None
    feedback_released: bool = False
    feedback_available_from: str | None = None
    text_chars: int = 0
    source: str = "briefing_upload"


class BatchStatus(BaseModel):
    batch_id: str
    target_tp: int
    status: str                        # running | done | failed
    filename: str = ""
    total: int = 0
    processed: int = 0
    briefed: int = 0
    unassigned: int = 0
    failed: int = 0
    review: int = 0
    uploaded_by: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    stale: bool = False


class BriefingBatchResponse(BatchStatus):
    """Antwort des Uploads: Batch-Status; ``briefings`` nur im
    synchronen Modus (``sync=1``, Tests/Skripte) gefüllt."""
    briefings: list[BriefingPublic] = Field(default_factory=list)


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

def _public(record: dict, ctx: TeacherContext | None = None) -> BriefingPublic:
    data = {k: v for k, v in record.items() if k in BriefingPublic.model_fields}
    tp = int(record.get("target_tp", 0) or 0)
    released = feedback_released(tp)
    release = feedback_release_date(tp)
    data["feedback_released"] = released
    data["feedback_available_from"] = release.isoformat() if release else None
    # Feedback-Inhalt verlässt den Server erst nach dem Termin — Master
    # sieht ihn jederzeit (Qualitätssicherung), verteilt aber nicht vorher.
    if not released and not (ctx and ctx.is_master):
        data["feedback"] = {}
    return BriefingPublic(**data)


def _feedback_access(record: dict, ctx: TeacherContext, force: bool, *, ueg_label: str) -> None:
    """423, solange das Feedback nicht freigegeben ist. Master darf mit
    ``force=1`` vorher lesen (Qualitätssicherung) — wird geloggt."""
    tp = int(record.get("target_tp", 0) or 0)
    if feedback_released(tp):
        return
    if ctx.is_master and force:
        logger.warning(
            "feedback_release_forced", by=ctx.tutor_id, target_tp=tp, ueg=ueg_label,
        )
        return
    release = feedback_release_date(tp)
    raise HTTPException(
        status_code=423,
        detail=(
            "Feedback erst nach dem Termin: freigegeben ab "
            f"{release.strftime('%d.%m.%Y') if release else 'unbekannt'}."
        ),
    )


def _feedback_ready(record: dict) -> bool:
    return record.get("status") == "briefed" and record.get("feedback_status") in ("ok", "technical_fallback")


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
        if not ctx.uegs:
            return []
        records = [r for r in records if r.get("ueg") in ctx.uegs]
        if ueg:
            wanted = normalize_ueg(ueg)
            records = [r for r in records if r.get("ueg") == wanted]
    records = _latest_per_group(records)
    records.sort(key=lambda r: (int(r.get("target_tp", 0)), r.get("ueg") or "~", int(r.get("sg") or 99)))
    return records


def _rubric_or_422(tp: int) -> BriefingRubric:
    try:
        return load_rubric(tp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _bundle_targets(ctx: TeacherContext, ueg: str | None) -> list[str]:
    """Übungsgruppen für einen Bundle-Download. Master: ``ueg`` Pflicht.
    ÜGL: ohne ``ueg`` alle eigenen Übungsgruppen; mit ``ueg`` nur diese
    (403, wenn fremd)."""
    if ctx.is_master:
        wanted = normalize_ueg(ueg or "")
        if not wanted:
            raise HTTPException(status_code=422, detail="ueg fehlt oder ist ungültig (z.B. UEG07)")
        return [wanted]
    if not ctx.uegs:
        raise HTTPException(
            status_code=403,
            detail="Ihre Tutor-Kennung ist keiner Übungsgruppe zugeordnet (erwartet z.B. UEG07 oder UEG07+UEG12).",
        )
    if ueg:
        wanted = normalize_ueg(ueg)
        if wanted not in ctx.uegs:
            raise HTTPException(status_code=403, detail="Diese Übungsgruppe gehört nicht zu Ihrer Kennung")
        return [wanted]
    return list(ctx.uegs)


def _missing_groups(records: list[dict]) -> list[int]:
    present = {int(r["sg"]) for r in records if r.get("sg")}
    return [n for n in STAMMGRUPPEN if n not in present]


# ---------------------------------------------------------------------------
# Verarbeitung eines Eintrags
# ---------------------------------------------------------------------------

async def _process_entry(
    *,
    generator: FeedbackGenerator,
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
    # Produkt 2 gleich mit erzeugen (zweiter Call, eigener gecachter
    # System-Prompt); die interne Einstufung dient als Konsistenzhilfe.
    feedback = await generator.generate_feedback(
        briefing_id=briefing_id, rubric=rubric, sub=sub,
        assessment=result["assessment"] if result["evaluation_status"] == "ok" else None,
    )

    return BriefingRecord(
        feedback=feedback["feedback"],
        feedback_status=feedback["feedback_status"],
        feedback_guardrail_hits=list(feedback.get("feedback_guardrail_hits", [])),
        feedback_needs_human_review=bool(feedback.get("feedback_needs_human_review")),
        feedback_review_reason=feedback.get("feedback_review_reason"),
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

@upload_router.post("/upload", response_model=BriefingBatchResponse, status_code=202)
async def upload_submissions(
    file: UploadFile = File(...),
    target_tp: int = Form(...),
    sync: bool = Form(default=False),
    ctx: TeacherContext = Depends(upload_auth),
):
    """Master-Upload: ZIP mit Stammgruppen-Abgaben (PPTX/DOCX/PDF) → je
    Datei ein Briefing. Speichert nur Briefing + Einstufung, nie Dateien.

    Standard ist asynchron: Antwort 202 mit Batch-Status, Verarbeitung im
    Hintergrund (Fortschritt über GET /briefings/batches/{batch_id}).
    ``sync=1`` wartet auf das Ergebnis (Tests, Skripte, kleine Batches)."""
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

    generator = FeedbackGenerator(api_key=api_key)
    batch_id = str(uuid.uuid4())
    batch = new_batch(
        batch_id=batch_id,
        target_tp=target_tp,
        total=len(entries),
        uploaded_by=ctx.tutor_id,
        filename=file.filename or "",
    )
    await asyncio.to_thread(batch_store.save, batch)
    logger.info(
        "briefing_batch_started",
        batch_id=batch_id,
        target_tp=target_tp,
        total=len(entries),
        uploaded_by=ctx.tutor_id,
        sync=sync,
    )

    records: list[dict] = []

    async def _process(filename: str, payload: bytes) -> dict:
        record = await _process_entry(
            generator=generator,
            rubric=rubric,
            batch_id=batch_id,
            target_tp=target_tp,
            filename=filename,
            data=payload,
            uploaded_by=ctx.tutor_id,
        )
        dumped = record.model_dump()
        records.append(dumped)
        return dumped

    coro = run_batch(
        batch,
        entries,
        _process,
        concurrency=UPLOAD_CONCURRENCY,
        save_record=briefing_store.save,
    )
    if sync:
        await coro
        records.sort(key=lambda r: str(r.get("filename", "")))
        return BriefingBatchResponse(**with_stale_flag(batch), briefings=[_public(r, ctx) for r in records])

    start_background(coro)
    return BriefingBatchResponse(**with_stale_flag(batch))


@router.get("/batches", response_model=list[BatchStatus])
async def list_batches(
    tp: int | None = Query(default=None, ge=1, le=5),
    ctx: TeacherContext = Depends(require_master),
):
    """Upload-Batches (neueste zuerst) — nur Master."""
    batches = [with_stale_flag(b) for b in batch_store.load_all()]
    if tp is not None:
        batches = [b for b in batches if int(b.get("target_tp", 0)) == tp]
    batches.sort(key=lambda b: str(b.get("started_at", "")), reverse=True)
    return [BatchStatus(**b) for b in batches]


@router.get("/batches/{batch_id}", response_model=BatchStatus)
async def get_batch(batch_id: str, ctx: TeacherContext = Depends(require_master)):
    batch = batch_store.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch nicht gefunden")
    return BatchStatus(**with_stale_flag(batch))


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
    """Briefing-Dokument je Übungsgruppe für einen Touchpoint (einheitliches
    DOCX mit allen Stammgruppen). ÜGL mit mehreren Übungsgruppen und ohne
    ``ueg``: ZIP mit einem DOCX je Übungsgruppe. Master: ``ueg`` Pflicht."""
    rubric = _rubric_or_422(tp)
    targets = _bundle_targets(ctx, ueg)
    documents: list[tuple[str, list[dict]]] = []
    for target in targets:
        records = _visible_records(ctx, tp=tp, ueg=target)
        if records:
            documents.append((target, records))
    if not documents:
        raise HTTPException(status_code=404, detail="Keine Briefings für diese Übungsgruppe(n)")

    def _render(target: str, records: list[dict]) -> bytes:
        return render_briefing_docx(records, rubric=rubric, ueg=target, missing_groups=_missing_groups(records))

    if len(documents) == 1:
        target, records = documents[0]
        payload = await asyncio.to_thread(_render, target, records)
        return Response(
            content=payload,
            media_type=DOCX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="KI-Briefing_TP{tp}_{target}.docx"'},
        )

    def _build_zip() -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for target, records in documents:
                archive.writestr(f"KI-Briefing_TP{tp}_{target}.docx", _render(target, records))
        return buffer.getvalue()

    payload = await asyncio.to_thread(_build_zip)
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="KI-Briefings_TP{tp}_{ctx.tutor_id or "UEG"}.zip"'},
    )


@router.get("/feedback/zip")
async def download_feedback_bundle(
    tp: int = Query(..., ge=1, le=5),
    ueg: str | None = Query(default=None),
    force: bool = Query(default=False),
    ctx: TeacherContext = Depends(teacher_context),
):
    """ZIP mit einem Feedback-DOCX je Stammgruppe einer Übungsgruppe — zur
    Weitergabe durch die ÜGL (z.B. über Canvas). Erst nach dem Termin."""
    rubric = _rubric_or_422(tp)
    targets = _bundle_targets(ctx, ueg)
    records = [
        r for target in targets
        for r in _visible_records(ctx, tp=tp, ueg=target)
        if _feedback_ready(r) and r.get("sg")
    ]
    if not records:
        raise HTTPException(status_code=404, detail="Keine Feedbacks für diese Übungsgruppe(n)")
    _feedback_access(records[0], ctx, force, ueg_label="+".join(targets))

    def _build() -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for record in records:
                folder = f"{record.get('ueg')}/" if len(targets) > 1 else ""
                name = f"{folder}KI-Feedback_{record.get('code') or record['briefing_id'][:8]}.docx"
                archive.writestr(name, render_feedback_docx(record, rubric=rubric))
        return buffer.getvalue()

    payload = await asyncio.to_thread(_build)
    label = targets[0] if len(targets) == 1 else (ctx.tutor_id or "UEG")
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="KI-Feedback_TP{tp}_{label}.zip"'},
    )


@router.get("", response_model=list[BriefingPublic])
async def list_briefings(
    tp: int | None = Query(default=None, ge=1, le=5),
    ueg: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Briefings (tutor-sichtbare Sicht). ÜGL: nur die eigene Übungsgruppe."""
    return [_public(r, ctx) for r in _visible_records(ctx, tp=tp, ueg=ueg)]


@router.get("/{briefing_id}", response_model=BriefingPublic)
async def get_briefing(briefing_id: str, ctx: TeacherContext = Depends(teacher_context)):
    record = briefing_store.get(briefing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    if not ctx.may_see(record.get("ueg")):
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    return _public(record, ctx)


@router.get("/{briefing_id}/feedback/docx")
async def download_feedback(
    briefing_id: str,
    force: bool = Query(default=False),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Feedback-DOCX EINER Stammgruppe — erst nach dem Termin (423 vorher)."""
    record = briefing_store.get(briefing_id)
    if not record or not ctx.may_see(record.get("ueg")):
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    if not _feedback_ready(record):
        raise HTTPException(status_code=404, detail="Für diese Abgabe liegt kein Feedback vor")
    _feedback_access(record, ctx, force, ueg_label=str(record.get("ueg") or ""))
    rubric = _rubric_or_422(int(record.get("target_tp", 0)))
    payload = await asyncio.to_thread(render_feedback_docx, record, rubric=rubric)
    label = record.get("code") or briefing_id[:8]
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="KI-Feedback_{label}.docx"'},
    )


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
    if not record or not ctx.may_see(record.get("ueg")):
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
    return _public(record, ctx)
