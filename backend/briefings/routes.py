"""Routen der KI-Briefings: Upload je Übungsgruppenleiter, Abruf, DOCX-Download, Monitoring.

Rollen (Owner-Entscheidung 2026-09-13):
- Jeder eingeloggte Übungsgruppenleiter (Konto UEGL01–UEGL26) lädt eine
  ZIP-Datei mit den Einreichungen SEINER Gruppen hoch und lädt die
  erzeugten Briefings herunter. Er sieht genau das, was er
  selbst hochgeladen hat — die Zugehörigkeit entsteht durch den Upload,
  nicht durch eine Namensregel.
- Der Master darf dasselbe und sieht zusätzlich alles: Monitoring je Konto
  (wer hat wann was hoch- und heruntergeladen), interne Einstufung, alle
  Dokumente. Nur der Master löscht Auswertungen und Uploads
  (Owner-Entscheidung 2026-09-30).
- Touchpoint, Übungsgruppe und Stammgruppe kommen vom Deckblatt der Datei
  (Code ``TPn-UEGxx-SGy``). Kein Auswahlfeld beim Upload. Ist etwas nicht
  erkennbar, wird die Datei als "bitte zuordnen" markiert und der
  Übungsgruppenleiter trägt die Angaben nach.

Auth-Kette: Router-weit ``require_api_key`` (fail-closed) +
``reject_revoked_teacher_session``. Der Browser erreicht diese Routen nur
über den Teacher-Proxy des Frontends, der den X-API-Key server-seitig
ergänzt und die verifizierte Identität als Header mitschickt:
``X-Teacher-Id`` (Konto) und ``X-Teacher-Master`` (``1`` nur für den
Master). Requests OHNE Identitäts-Header (Skripte direkt mit API-Key)
gelten als Operator (= Master). Der Upload akzeptiert alternativ ein
kurzlebiges Upload-Token (Direkt-Upload aus dem Browser, Vercel-Body-Limit).

Es werden KEINE hochgeladenen Dateien persistiert. Nur der extrahierte Text
wird verdichtet und verworfen; gespeichert werden Briefing, formale
Vorprüfung und interne Einstufung. Vom Deckblatt wird nur der Code
gelesen; personenbezogene Angaben im Text werden vor allem Weiteren entfernt.

Eingangsprüfung (backend/briefings/intake.py, Owner-Entscheidung 2026-09-14):
Nur echte Abgaben werden ausgewertet — Deckblatt-Angaben vollständig, Bausteine
vorhanden, Bezug zum Running Case ON (Kernbegriffe + kurzer Modellaufruf).
Alles andere wird mit Grund abgelehnt (Status ``rejected``, kein Briefing).
Prompt-Injection-Versuche werden erkannt und im Briefing ausgewiesen.

Sprache (Owner-Entscheidung 2026-09-28): Die Sprache der Abgabe bestimmt die
Sprache des Briefings dieser Stammgruppe (``language`` am Datensatz, erkannt
in ``backend/briefings/i18n.py``).
"""

from __future__ import annotations

import asyncio
import io
import re
import uuid
import zipfile
from collections import Counter
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
from backend.briefings.docx_render import render_briefing_docx
from backend.briefings.extraction import (
    MAX_FILE_BYTES,
    MAX_ZIP_ENTRIES,
    SUPPORTED_EXTENSIONS,
    ExtractedSubmission,
    ZipValidationError,
    build_code,
    canvas_group,
    extract_submission,
    iter_submission_entries,
    normalize_ueg,
)
from backend.briefings.formal import formal_checks
from backend.briefings.generator import BriefingGenerator
from backend.briefings.i18n import detect_language
from backend.briefings.intake import (
    INJECTION_NOTE,
    TopicClassifier,
    injection_findings,
    topic_screen,
    validate_submission,
)
from backend.briefings.rubrics import SUPPORTED_TPS, BriefingRubric, load_rubric, open_touchpoints
from backend.briefings.upload_token import UPLOAD_TOKEN_HEADER, UploadTokenError, verify_upload_token
from backend.config.tutor_accounts import MASTER_ACCOUNT, TUTOR_ACCOUNTS
from backend.db.briefing_store import briefing_store
from backend.db.download_log import download_log
from backend.db.tutor_account_store import tutor_account_store
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
OPERATOR_LABEL = "operator"             # Uploads/Downloads per Skript ohne Identitäts-Header

TEACHER_ID_HEADER = "X-Teacher-Id"
TEACHER_MASTER_HEADER = "X-Teacher-Master"

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

STATUS_REJECTED = "rejected"                     # keine echte Abgabe → kein Briefing
DUPLICATE_GROUP_NOTE = (
    "Mehrere Abgaben dieses Uploads tragen dieselbe Stammgruppe — bitte Deckblätter prüfen und Zuordnung korrigieren."
)


# ---------------------------------------------------------------------------
# Tutor-Kontext
# ---------------------------------------------------------------------------

@dataclass
class TeacherContext:
    tutor_id: str | None      # Konto (UEGL05, master) oder None = Operator/Skript
    is_master: bool

    @property
    def label(self) -> str:
        return self.tutor_id or OPERATOR_LABEL

    def owns(self, record: dict) -> bool:
        if self.is_master:
            return True
        return bool(self.tutor_id) and record.get("uploaded_by") == self.tutor_id


async def teacher_context(
    x_teacher_id: str | None = Header(default=None, alias=TEACHER_ID_HEADER),
    x_teacher_master: str | None = Header(default=None, alias=TEACHER_MASTER_HEADER),
) -> TeacherContext:
    if x_teacher_id is None and x_teacher_master is None:
        return TeacherContext(tutor_id=None, is_master=True)
    tutor_id = (x_teacher_id or "").strip() or None
    is_master = (x_teacher_master or "").strip().lower() in {"1", "true", "yes"}
    if not is_master and not tutor_id:
        raise HTTPException(status_code=401, detail="Tutor-Kennung fehlt")
    return TeacherContext(tutor_id=tutor_id, is_master=is_master)


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
    Jeder eingeloggte Übungsgruppenleiter darf hochladen."""
    if x_api_key is not None:
        await require_api_key(x_api_key)
        return await teacher_context(x_teacher_id, x_teacher_master)
    try:
        payload = verify_upload_token(x_upload_token)
    except UploadTokenError as exc:
        status_code = 503 if "nicht konfiguriert" in str(exc) else 401
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    from backend.db.revoked_sessions_store import revoked_session_store

    jti = str(payload.get("jti") or "")
    if jti and revoked_session_store.is_revoked(jti):
        raise HTTPException(status_code=401, detail="Sitzung wurde abgemeldet — bitte neu einloggen")
    tutor = str(payload.get("tutor") or "").strip() or None
    is_master = payload.get("master") is True
    if not tutor and not is_master:
        raise HTTPException(status_code=401, detail="Upload-Token ohne Konto")
    return TeacherContext(tutor_id=tutor, is_master=is_master)


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
    target_tp: int = 0                # 0 = Touchpoint nicht erkannt (nur bei abgelehnten Dateien)
    ueg: str = ""
    sg: int | None = None
    code: str | None = None
    code_source: str | None = None
    status: str                       # "briefed" | "rejected" | "extraction_failed" | "no_content"
    language: str = "de"              # Sprache der Abgabe = Sprache des Briefings (de | en)
    uploaded_at: str
    generated_at: str | None = None
    uploaded_by: str | None = None
    evaluation_status: str = "ok"     # "ok" | "technical_fallback" | "no_content" | "extraction_failed" | "rejected"
    needs_human_review: bool = False
    review_reason: str | None = None
    guardrail_hits: list[str] = Field(default_factory=list)
    formal: dict = Field(default_factory=dict)
    briefing: dict = Field(default_factory=dict)
    assessment: dict = Field(default_factory=dict)   # intern — nur Master
    text_chars: int = 0
    source: str = "briefing_upload"
    # Eingangsprüfung
    reject_reason: str | None = None                 # nur bei status == "rejected"
    topic_reason: str | None = None                  # Begründung der Themenprüfung
    pii_removed: list[str] = Field(default_factory=list)   # Labels entfernter Angaben (email, matrikel, …)
    injection_suspected: bool = False
    injection_findings: list[str] = Field(default_factory=list)


class BriefingPublic(BaseModel):
    """Tutor-sichtbare Sicht: ohne interne Einstufung."""
    briefing_id: str
    batch_id: str
    filename: str
    format: str = ""
    target_tp: int = 0
    ueg: str = ""
    sg: int | None = None
    code: str | None = None
    code_source: str | None = None
    status: str
    language: str = "de"
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
    reject_reason: str | None = None
    topic_reason: str | None = None
    pii_removed: list[str] = Field(default_factory=list)
    injection_suspected: bool = False
    injection_findings: list[str] = Field(default_factory=list)
    canvas_group: str = ""            # Gruppenname aus dem Canvas-Dateinamen ("stammteam3", "a4")


class BatchStatus(BaseModel):
    batch_id: str
    target_tp: int = 0                 # Historie; neu: Touchpoints stehen in ``tps``
    tps: list[int] = Field(default_factory=list)
    status: str                        # running | done | failed
    filename: str = ""
    total: int = 0
    processed: int = 0
    briefed: int = 0
    unassigned: int = 0
    failed: int = 0
    rejected: int = 0
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
    """Deckblatt-Angaben verifizieren oder nachtragen. Alle Felder optional;
    was fehlt, bleibt wie es ist."""
    target_tp: int | None = Field(default=None, ge=1, le=5)
    ueg: str | None = None
    sg: int | None = Field(default=None, ge=1, le=99)
    # Nur Master, nur False: einen falschen Prompt-Injection-Vermerk entfernen
    injection_suspected: bool | None = None


class BriefingOverviewRow(BaseModel):
    target_tp: int
    ueg: str
    briefed_count: int
    review_count: int
    groups: list[int]
    latest_uploaded_at: str | None = None


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _public(record: dict) -> BriefingPublic:
    data = {k: v for k, v in record.items() if k in BriefingPublic.model_fields}
    data["canvas_group"] = canvas_group(str(record.get("filename", "")))
    return BriefingPublic(**data)


def _latest_per_group(records: list[dict]) -> list[dict]:
    """Bei Mehrfach-Uploads derselben Stammgruppe durch DENSELBEN
    Übungsgruppenleiter gewinnt der neueste Upload. Uploads verschiedener
    Konten bleiben nebeneinander bestehen; nicht zuordenbare Datensätze
    bleiben alle erhalten. Tragen mehrere Abgaben DESSELBEN Uploads dieselbe
    Stammgruppe (falsch ausgefüllte Deckblätter), bleiben alle sichtbar und
    werden zur Prüfung markiert — keine verdrängt die andere."""
    latest: dict[tuple, list[dict]] = {}
    unassigned: list[dict] = []
    for r in records:
        if r.get("target_tp") and r.get("ueg") and r.get("sg"):
            key = (int(r["target_tp"]), r.get("uploaded_by"), r["ueg"], int(r["sg"]))
            current = latest.get(key)
            if current is None:
                latest[key] = [r]
            elif r.get("batch_id") and r.get("batch_id") == current[0].get("batch_id"):
                current.append(r)
            elif str(r.get("uploaded_at", "")) > max(str(c.get("uploaded_at", "")) for c in current):
                latest[key] = [r]
        else:
            unassigned.append(r)
    out: list[dict] = []
    for group in latest.values():
        if len(group) == 1:
            out.append(group[0])
            continue
        for r in group:
            reason = " ".join(x for x in (DUPLICATE_GROUP_NOTE, r.get("review_reason")) if x)
            out.append({**r, "needs_human_review": True, "review_reason": reason})
    return out + unassigned


def _tutor_filter_value(tutor: str | None) -> str | None:
    """Query-Parameter ``tutor`` des Masters → gespeicherter uploaded_by
    (``operator`` = Skript-Uploads ohne Konto, gespeichert als None)."""
    value = (tutor or "").strip()
    return None if value == OPERATOR_LABEL else value


def _visible_records(ctx: TeacherContext, *, tp: int | None = None, tutor: str | None = None) -> list[dict]:
    records = briefing_store.load_all()
    if tp is not None:
        records = [r for r in records if int(r.get("target_tp", 0) or 0) == tp]
    if ctx.is_master:
        if tutor:
            wanted = _tutor_filter_value(tutor)
            records = [r for r in records if r.get("uploaded_by") == wanted]
    else:
        records = [r for r in records if r.get("uploaded_by") == ctx.tutor_id]
    records = _latest_per_group(records)
    records.sort(
        key=lambda r: (
            int(r.get("target_tp", 0) or 0),
            r.get("ueg") or "~",
            int(r.get("sg") or 99),
            str(r.get("filename", "")),
        )
    )
    return records


def _rubric_or_422(tp: int) -> BriefingRubric:
    try:
        return load_rubric(tp)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _record_or_404(briefing_id: str, ctx: TeacherContext) -> dict:
    record = briefing_store.get(briefing_id)
    if not record or not ctx.owns(record):
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    return record


def _log_download(ctx: TeacherContext, *, tp: int, kind: str, scope: str, code: str | None = None,
                  briefing_id: str | None = None) -> None:
    try:
        download_log.log(tutor=ctx.label, target_tp=tp, kind=kind, scope=scope, code=code, briefing_id=briefing_id)
    except Exception as exc:  # pragma: no cover - Protokoll darf den Download nie verhindern
        logger.warning("download_log_failed", error=str(exc))


def _group_by_ueg(records: list[dict]) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for r in records:
        if r.get("ueg"):
            groups.setdefault(r["ueg"], []).append(r)
    return sorted(groups.items())


# ---------------------------------------------------------------------------
# Verarbeitung eines Eintrags
# ---------------------------------------------------------------------------

def _extract(filename: str, data: bytes) -> ExtractedSubmission:
    """Zwei Durchgänge: erst Kenndaten (Touchpoint) lesen, dann mit der
    passenden Vorlagen-Boilerplate des erkannten Touchpoints extrahieren."""
    sub = extract_submission(filename, data, None)
    tp = sub.kenndaten.tp
    if tp in SUPPORTED_TPS:
        sub = extract_submission(filename, data, tp)
    return sub


async def _generate_into(
    record: dict,
    *,
    sub: ExtractedSubmission,
    rubric: BriefingRubric,
    generator: BriefingGenerator,
) -> dict:
    """Erzeugt das Briefing für einen Datensatz und schreibt die
    Ergebnisfelder in ``record``."""
    kd = sub.kenndaten
    tp = rubric.tp
    language = record.get("language") or "de"
    result = await generator.generate(
        briefing_id=record["briefing_id"], rubric=load_rubric(tp, language), sub=sub, language=language,
    )
    status = "no_content" if result["evaluation_status"] == "no_content" else "briefed"
    assigned = bool(kd.ueg and kd.sg)
    injection = bool(record.get("injection_suspected"))
    needs_review = bool(result["needs_human_review"]) or injection or not assigned
    review_reason = result.get("review_reason")
    if injection:
        review_reason = INJECTION_NOTE + (f" {review_reason}" if review_reason else "")
    record.update(
        format=sub.format,
        target_tp=tp,
        ueg=kd.ueg,
        sg=kd.sg,
        code=(build_code(tp, kd.ueg, kd.sg) if assigned else None),
        code_source=kd.source or None,
        status=status,
        generated_at=naive_utcnow().isoformat(),
        evaluation_status=result["evaluation_status"],
        needs_human_review=needs_review,
        review_reason=review_reason,
        guardrail_hits=list(result.get("guardrail_hits", [])),
        formal=formal_checks(sub, rubric, tp),
        briefing=result["briefing"],
        assessment=result["assessment"],
        text_chars=sub.baustein1_chars + sub.baustein2_chars,
    )
    return record


# Canvas stellt dem Dateinamen den Gruppennamen voran ("stammteam3_…", "sg3_…").
# Nur Namen mit eindeutiger Nummer 1–8; "a4"/"b2" bleiben offen (nachtragen).
_CANVAS_GROUP_RE = re.compile(
    r"^(?:stamm\s*gruppe|stamm\s*team|core\s*team|home\s*group|home\s*team|projekt\s*gruppe|projekt\s*team|"
    r"gruppe|group|team|sg)\s*[-_ ]?0?([1-8])(?!\d)",
    re.IGNORECASE,
)


def _majority(values: list) -> object | None:
    """Der Wert, den mindestens zwei Drittel der erkannten Deckblätter tragen:
    einzelne falsch ausgefüllte Deckblätter kippen ihn nicht, ein ZIP mit
    zwei Übungsgruppen ergibt keinen."""
    if not values:
        return None
    value, count = Counter(values).most_common(1)[0]
    return value if count * 3 >= len(values) * 2 else None


def _upload_consensus(entries: list[tuple[str, bytes]]) -> tuple[str, int | None]:
    """Übungsgruppe und Touchpoint, die die Mehrheit der erkannten Deckblätter
    eines Uploads trägt (Canvas-Export einer Übungsgruppe zu einem Touchpoint)."""
    uegs: list[str] = []
    tps: list[int] = []
    for filename, payload in entries:
        try:
            kd = _extract(filename, payload).kenndaten
        except ValueError:
            continue
        if kd.ueg:
            uegs.append(kd.ueg)
        if kd.tp in SUPPORTED_TPS:
            tps.append(kd.tp)
    return str(_majority(uegs) or ""), _majority(tps)


def _fill_group(sub: ExtractedSubmission, filename: str, upload_ueg: str, upload_tp: int | None = None) -> list[str]:
    """Deckblatt ohne Übungs-/Stammgruppe/Touchpoint: Übungsgruppe und
    Touchpoint aus den übrigen Abgaben desselben Uploads, Stammgruppe aus dem
    Canvas-Präfix des Dateinamens (``stammteam4_…``, ``coreteam5_…``).
    Rückgabe: Hinweise."""
    kd = sub.kenndaten
    notes: list[str] = []
    if not kd.ueg and upload_ueg:
        kd.ueg = upload_ueg
        notes.append(f"Übungsgruppe {upload_ueg} aus den übrigen Abgaben dieses Uploads übernommen.")
    group = _CANVAS_GROUP_RE.match(filename or "")
    if not kd.sg and group:
        kd.sg = int(group.group(1))
        notes.append(f"Stammgruppe SG{kd.sg} aus dem Dateinamen übernommen.")
    if kd.tp not in SUPPORTED_TPS and upload_tp in SUPPORTED_TPS:
        kd.tp = upload_tp
        notes.append(f"Touchpoint {upload_tp} aus den übrigen Abgaben dieses Uploads übernommen.")
    if notes and not kd.source:
        kd.source = "upload"
    return notes


def _manual_assignments(uploaded_by: str | None) -> dict[str, tuple[int, str, int]]:
    """Zuordnungen, die dieses Konto früher von Hand eingetragen hat, je
    Dateiname (neueste zuerst gewinnt). Wird dieselbe Datei erneut
    hochgeladen, gilt die Korrektur weiter und muss nicht wiederholt werden."""
    out: dict[str, tuple[int, str, int]] = {}
    records = [
        r for r in briefing_store.load_all()
        if r.get("uploaded_by") == uploaded_by and r.get("code_source") == "manual"
        and r.get("target_tp") and r.get("ueg") and r.get("sg")
    ]
    for r in sorted(records, key=lambda r: str(r.get("uploaded_at", ""))):
        out[str(r.get("filename", ""))] = (int(r["target_tp"]), r["ueg"], int(r["sg"]))
    return out


def _rejected(base: dict, sub: ExtractedSubmission | None, reason: str) -> BriefingRecord:
    kd = sub.kenndaten if sub else None
    return BriefingRecord(
        **{**base, "format": sub.format if sub else base["format"]},
        target_tp=(kd.tp if kd and kd.tp in SUPPORTED_TPS else 0),
        ueg=(kd.ueg if kd else ""),
        sg=(kd.sg if kd else None),
        code=(build_code(kd.tp, kd.ueg, kd.sg) if kd and kd.tp in SUPPORTED_TPS and kd.ueg and kd.sg else None),
        code_source=(kd.source or None) if kd else None,
        status=STATUS_REJECTED,
        evaluation_status="rejected",
        needs_human_review=False,
        reject_reason=reason,
        formal={"filename": base["filename"], "format": sub.format if sub else base["format"],
                "notes": list(sub.notes) if sub else []},
        pii_removed=list(sub.pii_hits) if sub else [],
        text_chars=(sub.baustein1_chars + sub.baustein2_chars) if sub else 0,
    )


async def _process_entry(
    *,
    generator: BriefingGenerator,
    topic_classifier: TopicClassifier,
    rubrics: dict[int, BriefingRubric],
    batch_id: str,
    filename: str,
    data: bytes,
    uploaded_by: str | None,
    upload_ueg: str = "",
    upload_tp: int | None = None,
    manual: dict[str, tuple[int, str, int]] | None = None,
) -> BriefingRecord:
    briefing_id = str(uuid.uuid4())
    uploaded_at = naive_utcnow().isoformat()
    base = dict(
        briefing_id=briefing_id,
        batch_id=batch_id,
        filename=filename,
        format=filename.rsplit(".", 1)[-1].lower(),
        uploaded_at=uploaded_at,
        uploaded_by=uploaded_by,
    )

    try:
        sub = await asyncio.to_thread(_extract, filename, data)
    except ValueError as exc:
        logger.warning("briefing_extraction_failed", filename=filename, error=str(exc), cause=repr(exc.__cause__))
        return BriefingRecord(
            **base,
            status="extraction_failed",
            evaluation_status="extraction_failed",
            needs_human_review=True,
            review_reason=str(exc),
            formal={"filename": filename},
        )

    if manual and filename in manual:
        kd = sub.kenndaten
        kd.tp, kd.ueg, kd.sg = manual[filename]
        kd.code, kd.source = build_code(kd.tp, kd.ueg, kd.sg), "manual"
        fill_notes: list[str] = []
    else:
        fill_notes = _fill_group(sub, filename, upload_ueg, upload_tp)

    # 1. Formale Eingangsprüfung: nur leere Dateien werden abgelehnt; fehlendes
    #    Deckblatt oder fehlende Marker geben Hinweise (nachtragen statt ablehnen)
    decision = validate_submission(sub)
    if not decision.accepted:
        logger.info("briefing_rejected", filename=filename, reason=decision.reason, uploaded_by=uploaded_by)
        return _rejected(base, sub, decision.reason or "Keine Abgabe.")
    intake_notes = list(decision.notes) + fill_notes

    # 2. Themenprüfung: Kernbegriffe (kostenlos), dann kurzer Modellaufruf, der
    #    bei fehlendem Deckblatt auch den Touchpoint bestimmt
    combined = f"{sub.baustein1}\n{sub.baustein2}"
    passed, hits = topic_screen(combined)
    if not passed:
        logger.info("briefing_rejected", filename=filename, reason="topic_screen", hits=hits, uploaded_by=uploaded_by)
        return _rejected(base, sub, "Kein Bezug zum Running Case ON erkennbar — der Text enthält keine Kernbegriffe des Falls.")
    for tp_n in SUPPORTED_TPS:
        rubrics.setdefault(tp_n, load_rubric(tp_n))
    topic = await topic_classifier.check(rubrics, sub)
    if topic.on_topic is False:
        logger.info("briefing_rejected", filename=filename, reason="topic_classifier", uploaded_by=uploaded_by)
        return _rejected(base, sub, "Kein Bezug zum Arbeitsauftrag am Running Case ON: " + (topic.reason or "laut Themenprüfung."))
    if sub.kenndaten.tp not in SUPPORTED_TPS:
        # Nur das Modell kennt den Touchpoint: nie einer, für den es noch keine
        # Abgaben geben kann — sonst der zuletzt eröffnete.
        opened = open_touchpoints()
        guessed = topic.tp if topic.tp in opened else opened[-1]
        sub.kenndaten.tp = guessed
        sub.kenndaten.source = sub.kenndaten.source or "inhalt"
        intake_notes.append(f"Touchpoint {guessed} aus dem Inhalt bestimmt.")
    rubric = rubrics[sub.kenndaten.tp]
    topic_reason = topic.reason
    on_topic = topic.on_topic

    # 3. Prompt-Injection: Muster im Text + versteckter Text (Text bleibt, Hinweis ins Briefing)
    findings = injection_findings(sub)
    if findings:
        logger.warning("briefing_injection_suspected", filename=filename, uploaded_by=uploaded_by, findings=len(findings))

    record = dict(
        base,
        status="briefed",
        language=detect_language(combined),
        topic_reason=topic_reason or None,
        pii_removed=list(sub.pii_hits),
        injection_suspected=bool(findings),
        injection_findings=findings,
    )
    await _generate_into(record, sub=sub, rubric=rubric, generator=generator)
    extra = list(intake_notes)
    if on_topic is None:
        extra.insert(0, topic_reason or "Themenprüfung nicht möglich.")
    if extra:
        record["needs_human_review"] = True
        record["review_reason"] = " ".join([*extra, record.get("review_reason") or ""]).strip()
        record["formal"]["notes"] = [*intake_notes, *record["formal"].get("notes", [])]
    return BriefingRecord(**record)


# ---------------------------------------------------------------------------
# Routen: Upload und Batches
# ---------------------------------------------------------------------------

@upload_router.post("/upload", response_model=BriefingBatchResponse, status_code=202)
async def upload_submissions(
    file: list[UploadFile] = File(...),
    sync: bool = Form(default=False),
    ctx: TeacherContext = Depends(upload_auth),
):
    """Upload einer ZIP-Datei mit Einreichungen (PPTX/DOCX/PDF) → je Datei ein
    Briefing. Statt der ZIP gehen auch die Dateien selbst, einzeln oder
    mehrere auf einmal (Safari entpackt geladene ZIPs automatisch — dann gibt
    es keine ZIP mehr zum Auswählen). Touchpoint, Übungsgruppe und Stammgruppe
    werden vom Deckblatt gelesen. Speichert nur die Auswertung, nie die Dateien.

    Standard ist asynchron: Antwort 202 mit Batch-Status, Verarbeitung im
    Hintergrund (Fortschritt über GET /briefings/batches/{batch_id}).
    ``sync=1`` wartet auf das Ergebnis (Tests, Skripte, kleine Batches)."""
    api_key = get_openrouter_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY nicht konfiguriert")

    names = [(f.filename or "").rsplit("/", 1)[-1] for f in file]
    upload_name = names[0] if len(names) == 1 else f"{len(names)} Dateien"
    entries: list[tuple[str, bytes]] = []
    total_bytes = 0
    try:
        for name, part in zip(names, file):
            data = await part.read()
            total_bytes += len(data)
            if total_bytes > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Upload ist zu gross (max. 400 MB).")
            if name.lower().endswith(SUPPORTED_EXTENSIONS):
                # Abgabe direkt statt ZIP (eine PPTX ist selbst ein ZIP-Container)
                if len(data) > MAX_FILE_BYTES:
                    raise ZipValidationError(
                        f"'{name}' überschreitet das Dateilimit von {MAX_FILE_BYTES // (1024 * 1024)} MB."
                    )
                entries.append((name, data))
                continue
            try:
                entries.extend(iter_submission_entries(data))
            except ZipValidationError:
                if len(file) == 1:
                    raise
                # Mehrfachauswahl: Fremddateien im Ordner überspringen
                logger.info("briefing_upload_file_skipped", filename=name, uploaded_by=ctx.label)
        if not entries:
            raise ZipValidationError("Keine PPTX-, DOCX- oder PDF-Dateien im Upload.")
        if len(entries) > MAX_ZIP_ENTRIES:
            raise ZipValidationError(f"Upload enthält zu viele Dateien (max. {MAX_ZIP_ENTRIES}).")
    except ZipValidationError as exc:
        logger.info("briefing_upload_rejected", reason=str(exc), filename=upload_name, uploaded_by=ctx.label)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    upload_ueg, upload_tp = await asyncio.to_thread(_upload_consensus, entries)
    manual = await asyncio.to_thread(_manual_assignments, ctx.tutor_id)

    generator = BriefingGenerator(api_key=api_key)
    topic_classifier = TopicClassifier(api_key=api_key)
    rubrics: dict[int, BriefingRubric] = {}
    batch_id = str(uuid.uuid4())
    batch = new_batch(
        batch_id=batch_id,
        target_tp=0,
        total=len(entries),
        uploaded_by=ctx.tutor_id,
        filename=upload_name,
    )
    batch["tps"] = []
    await asyncio.to_thread(batch_store.save, batch)
    logger.info(
        "briefing_batch_started",
        batch_id=batch_id,
        total=len(entries),
        uploaded_by=ctx.label,
        sync=sync,
    )

    records: list[dict] = []

    async def _process(filename: str, payload: bytes) -> dict:
        record = await _process_entry(
            generator=generator,
            topic_classifier=topic_classifier,
            rubrics=rubrics,
            batch_id=batch_id,
            filename=filename,
            data=payload,
            uploaded_by=ctx.tutor_id,
            upload_ueg=upload_ueg,
            upload_tp=upload_tp,
            manual=manual,
        )
        dumped = record.model_dump()
        records.append(dumped)
        tp = int(dumped.get("target_tp") or 0)
        if tp and tp not in batch["tps"]:
            batch["tps"] = sorted([*batch["tps"], tp])
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
        return BriefingBatchResponse(**with_stale_flag(batch), briefings=[_public(r) for r in records])

    start_background(coro)
    return BriefingBatchResponse(**with_stale_flag(batch))


def _visible_batches(ctx: TeacherContext, tutor: str | None = None) -> list[dict]:
    batches = [with_stale_flag(b) for b in batch_store.load_all()]
    if ctx.is_master:
        if tutor:
            wanted = _tutor_filter_value(tutor)
            batches = [b for b in batches if b.get("uploaded_by") == wanted]
    else:
        batches = [b for b in batches if b.get("uploaded_by") == ctx.tutor_id]
    for b in batches:
        b.setdefault("tps", [b["target_tp"]] if b.get("target_tp") else [])
    batches.sort(key=lambda b: str(b.get("started_at", "")), reverse=True)
    return batches


@router.get("/batches", response_model=list[BatchStatus])
async def list_batches(
    tutor: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Upload-Batches (neueste zuerst): eigene; Master alle (``tutor`` filtert)."""
    return [BatchStatus(**b) for b in _visible_batches(ctx, tutor)]


@router.get("/batches/{batch_id}", response_model=BatchStatus)
async def get_batch(batch_id: str, ctx: TeacherContext = Depends(teacher_context)):
    batch = batch_store.get(batch_id)
    if not batch or not ctx.owns(batch):
        raise HTTPException(status_code=404, detail="Batch nicht gefunden")
    out = with_stale_flag(batch)
    out.setdefault("tps", [out["target_tp"]] if out.get("target_tp") else [])
    return BatchStatus(**out)


@router.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str, ctx: TeacherContext = Depends(require_master)):
    """Löscht einen Upload mit allen seinen Auswertungen endgültig — nur Master."""
    batch = batch_store.get(batch_id)
    records = [r for r in briefing_store.load_all() if r.get("batch_id") == batch_id]
    if not batch and not records:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden")
    if batch and batch.get("status") == "running" and not with_stale_flag(batch)["stale"]:
        raise HTTPException(status_code=409, detail="Upload wird noch verarbeitet — bitte warten")
    deleted = 0
    for r in records:
        deleted += int(await asyncio.to_thread(briefing_store.delete, str(r["briefing_id"])))
    await asyncio.to_thread(batch_store.delete, batch_id)
    logger.info(
        "briefing_batch_deleted", batch_id=batch_id, records=deleted, by=ctx.label,
        uploaded_by=(batch or {}).get("uploaded_by") or (records[0].get("uploaded_by") if records else None),
    )
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# Routen: Monitoring (Master)
# ---------------------------------------------------------------------------

@router.get("/monitoring")
async def monitoring(ctx: TeacherContext = Depends(require_master)):
    """Je Konto UEGL01–UEGL26 (plus master/operator, falls sie hochgeladen
    haben): Uploads je Touchpoint mit Gruppen und Status, letzter Upload,
    letzter Briefing-Download, offene Prüffälle, Kontostatus (Passwort gesetzt,
    Zurücksetzen angefragt)."""
    records = _latest_per_group(briefing_store.load_all())
    # Nur Briefing-Downloads; Alt-Einträge aus der Zeit mit KI-Feedback-Dokument bleiben aussen vor.
    downloads = [d for d in download_log.load_all() if d.get("kind", "briefing") == "briefing"]
    accounts = {a["account"]: tutor_account_store.public_view(a) for a in tutor_account_store.list_all()}

    def _label(value: str | None) -> str:
        return value or OPERATOR_LABEL

    uploaders = list(TUTOR_ACCOUNTS)
    for extra in sorted({_label(r.get("uploaded_by")) for r in records} | {_label(d.get("tutor")) for d in downloads}):
        if extra not in uploaders:
            uploaders.append(extra)

    rows = []
    for account in uploaders:
        own = [r for r in records if _label(r.get("uploaded_by")) == account]
        own_downloads = [d for d in downloads if _label(d.get("tutor")) == account]
        per_tp: dict[int, dict] = {}
        for r in own:
            tp = int(r.get("target_tp") or 0)
            entry = per_tp.setdefault(tp, {
                "target_tp": tp, "count": 0, "briefed": 0, "review": 0,
                "latest_uploaded_at": None, "last_download_briefing_at": None, "groups": [],
            })
            entry["count"] += 1
            entry["briefed"] += int(r.get("status") == "briefed")
            entry["review"] += int(bool(r.get("needs_human_review")))
            entry["latest_uploaded_at"] = max(entry["latest_uploaded_at"] or "", str(r.get("uploaded_at", ""))) or None
            entry["groups"].append({
                "briefing_id": r["briefing_id"],
                "code": r.get("code"),
                "ueg": r.get("ueg") or "",
                "sg": r.get("sg"),
                "status": r.get("status"),
                "evaluation_status": r.get("evaluation_status"),
                "needs_human_review": bool(r.get("needs_human_review")),
                "injection_suspected": bool(r.get("injection_suspected")),
                "reject_reason": r.get("reject_reason"),
                "uploaded_at": r.get("uploaded_at"),
                "filename": r.get("filename"),
            })
        for d in own_downloads:
            tp = int(d.get("target_tp") or 0)
            entry = per_tp.setdefault(tp, {
                "target_tp": tp, "count": 0, "briefed": 0, "review": 0,
                "latest_uploaded_at": None, "last_download_briefing_at": None, "groups": [],
            })
            entry["last_download_briefing_at"] = max(entry["last_download_briefing_at"] or "", str(d.get("at", ""))) or None
        for entry in per_tp.values():
            entry["groups"].sort(key=lambda g: (g["ueg"] or "~", g["sg"] or 99))
        rows.append({
            "account": account,
            "is_tutor_account": account in TUTOR_ACCOUNTS,
            "is_master": account == MASTER_ACCOUNT,
            **(accounts.get(account) or {
                "password_set": None, "password_set_at": None, "last_login_at": None,
                "reset_requested_at": None, "reset_code_active": False, "reset_code_expires_at": None,
            }),
            "upload_count": len(own),
            "review_open": sum(1 for r in own if r.get("needs_human_review")),
            "rejected": sum(1 for r in own if r.get("status") == STATUS_REJECTED),
            "injection_suspected": sum(1 for r in own if r.get("injection_suspected")),
            "latest_uploaded_at": max((str(r.get("uploaded_at", "")) for r in own), default=None),
            "last_download_at": max((str(d.get("at", "")) for d in own_downloads), default=None),
            "touchpoints": [per_tp[k] for k in sorted(per_tp)],
        })
    return {"generated_at": naive_utcnow().isoformat(), "accounts": rows}


# ---------------------------------------------------------------------------
# Routen: Übersicht, Downloads, Einzelabruf
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=list[BriefingOverviewRow])
async def briefing_overview(
    tp: int | None = Query(default=None, ge=1, le=5),
    tutor: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Je Touchpoint und Übungsgruppe: wie viele Briefings liegen vor, welche
    Stammgruppen sind dabei. Nur eigene Uploads; Master mit ``tutor``-Filter."""
    records = _visible_records(ctx, tp=tp, tutor=tutor)
    groups: dict[tuple[int, str], list[dict]] = {}
    for r in records:
        groups.setdefault((int(r.get("target_tp", 0) or 0), r.get("ueg") or ""), []).append(r)
    rows = [
        BriefingOverviewRow(
            target_tp=key[0],
            ueg=key[1],
            briefed_count=sum(1 for r in items if r.get("status") == "briefed"),
            review_count=sum(1 for r in items if r.get("needs_human_review")),
            groups=sorted({int(r["sg"]) for r in items if r.get("sg")}),
            latest_uploaded_at=max((str(r.get("uploaded_at", "")) for r in items), default=None),
        )
        for key, items in groups.items()
    ]
    rows.sort(key=lambda row: (row.target_tp, row.ueg or "~"))
    return rows


def _bundle_records(ctx: TeacherContext, *, tp: int, tutor: str | None, ueg: str | None) -> list[dict]:
    if ctx.is_master and not tutor:
        raise HTTPException(status_code=422, detail="tutor fehlt (Konto, dessen Dokumente heruntergeladen werden)")
    records = [r for r in _visible_records(ctx, tp=tp, tutor=tutor) if r.get("ueg") and r.get("status") == "briefed"]
    if ueg:
        wanted = normalize_ueg(ueg)
        if not wanted:
            raise HTTPException(status_code=422, detail="ueg ungültig (z.B. UEG07)")
        records = [r for r in records if r.get("ueg") == wanted]
    return records


@router.get("/docx")
async def download_briefing_bundle(
    tp: int = Query(..., ge=1, le=5),
    ueg: str | None = Query(default=None),
    tutor: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Briefing-Dokument je Übungsgruppe für einen Touchpoint (DOCX mit allen
    Stammgruppen). Bei mehreren Übungsgruppen ohne ``ueg``: ZIP mit einem
    DOCX je Übungsgruppe. Master lädt mit ``tutor`` die Dokumente eines Kontos."""
    rubric = _rubric_or_422(tp)
    documents = _group_by_ueg(_bundle_records(ctx, tp=tp, tutor=tutor, ueg=ueg))
    if not documents:
        raise HTTPException(status_code=404, detail="Keine Briefings für diesen Touchpoint")
    owner = (tutor or ctx.label) if ctx.is_master else ctx.label

    def _render(target: str, records: list[dict]) -> bytes:
        return render_briefing_docx(records, rubric=rubric, ueg=target)

    _log_download(ctx, tp=tp, kind="briefing", scope="bundle", code="+".join(u for u, _ in documents))
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
        headers={"Content-Disposition": f'attachment; filename="KI-Briefings_TP{tp}_{owner}.zip"'},
    )


@router.get("", response_model=list[BriefingPublic])
async def list_briefings(
    tp: int | None = Query(default=None, ge=1, le=5),
    tutor: str | None = Query(default=None),
    ctx: TeacherContext = Depends(teacher_context),
):
    """Briefings (tutor-sichtbare Sicht): eigene Uploads; Master alle
    (``tutor`` filtert auf ein Konto)."""
    return [_public(r) for r in _visible_records(ctx, tp=tp, tutor=tutor)]


@router.get("/{briefing_id}", response_model=BriefingPublic)
async def get_briefing(briefing_id: str, ctx: TeacherContext = Depends(teacher_context)):
    return _public(_record_or_404(briefing_id, ctx))


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
        "uploaded_by": record.get("uploaded_by"),
        "evaluation_status": record.get("evaluation_status"),
        "assessment": record.get("assessment", {}),
    }


@router.get("/{briefing_id}/docx")
async def download_single_briefing(briefing_id: str, ctx: TeacherContext = Depends(teacher_context)):
    record = _record_or_404(briefing_id, ctx)
    if record.get("status") != "briefed":
        raise HTTPException(status_code=404, detail="Für diese Abgabe liegt kein Briefing vor")
    tp = int(record.get("target_tp", 0) or 0)
    rubric = _rubric_or_422(tp)
    _log_download(ctx, tp=tp, kind="briefing", scope="single", code=record.get("code"), briefing_id=briefing_id)
    payload = await asyncio.to_thread(
        render_briefing_docx, [record], rubric=rubric, ueg=record.get("ueg") or ""
    )
    label = record.get("code") or briefing_id[:8]
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="KI-Briefing_{label}.docx"'},
    )


@router.delete("/{briefing_id}")
async def delete_briefing(briefing_id: str, ctx: TeacherContext = Depends(require_master)):
    """Löscht eine einzelne Auswertung endgültig — nur Master."""
    record = briefing_store.get(briefing_id)
    if not record:
        raise HTTPException(status_code=404, detail="Briefing nicht gefunden")
    await asyncio.to_thread(briefing_store.delete, briefing_id)
    logger.info(
        "briefing_deleted", briefing_id=briefing_id, by=ctx.label,
        uploaded_by=record.get("uploaded_by"), code=record.get("code"), status=record.get("status"),
    )
    return {"deleted": 1}


@router.patch("/{briefing_id}", response_model=BriefingPublic)
async def patch_assignment(
    briefing_id: str, patch: AssignmentPatch, ctx: TeacherContext = Depends(teacher_context)
):
    """Deckblatt-Angaben (Touchpoint, Übungsgruppe, Stammgruppe) einer
    ausgewerteten Abgabe verifizieren oder korrigieren — für eigene Uploads;
    der Master für alle Konten (die Änderung erscheint beim jeweiligen
    Übungsgruppenleiter). Einzelne Angaben genügen, z.B. nur der Touchpoint.
    Der Master kann zusätzlich einen falschen Prompt-Injection-Vermerk
    entfernen. Abgelehnte oder unlesbare Dateien werden nicht korrigiert,
    sondern mit korrigiertem Deckblatt erneut hochgeladen."""
    record = _record_or_404(briefing_id, ctx)
    if record.get("status") in ("extraction_failed", STATUS_REJECTED):
        raise HTTPException(status_code=409, detail="Diese Datei wurde nicht ausgewertet — bitte korrigiert erneut hochladen")
    assignment = not (patch.target_tp is None and patch.ueg is None and patch.sg is None)
    if not assignment and patch.injection_suspected is None:
        raise HTTPException(status_code=422, detail="Nichts zu ändern")

    if patch.injection_suspected is not None:
        if not ctx.is_master:
            raise HTTPException(status_code=403, detail="Nur für den Master-Tutor")
        if patch.injection_suspected:
            raise HTTPException(status_code=422, detail="Der Vermerk kann nur entfernt werden")
        rest = (record.get("review_reason") or "").replace(INJECTION_NOTE, "").strip()
        record.update(
            injection_suspected=False, injection_findings=[], review_reason=rest or None,
            needs_human_review=bool(rest) or not (record.get("ueg") and record.get("sg")),
        )
        logger.info("briefing_injection_cleared", briefing_id=briefing_id, by=ctx.label)

    old_tp = int(record.get("target_tp", 0) or 0)
    tp = patch.target_tp or old_tp
    ueg = record.get("ueg") or ""
    sg = patch.sg if patch.sg is not None else record.get("sg")
    if assignment:
        if patch.ueg is not None:
            # "ÜG 6", "Gruppe 06", "UEG06" und "6" meinen dasselbe
            number = re.search(r"\d{1,2}", patch.ueg)
            ueg = normalize_ueg(number.group(0)) if number else ""
            if not ueg:
                raise HTTPException(status_code=422, detail="Übungsgruppe ungültig (erwartet z.B. UEG07)")
        complete = bool(tp and ueg and sg)
        record.update(
            target_tp=tp, ueg=ueg, sg=sg,
            code=build_code(tp, ueg, int(sg)) if complete else None, code_source="manual",
        )
        formal = dict(record.get("formal") or {})
        if complete:
            formal.update(code=record["code"], code_valid=True, code_matches_tp=True)
        notes = [n for n in formal.get("notes", []) if "Touchpoint" not in n or "hochgeladen" not in n]
        tp_changed = bool(old_tp and tp != old_tp)
        if tp_changed:
            notes.append(f"Touchpoint von {old_tp} auf {tp} geändert — die Auswertung wurde mit der Rubric von Touchpoint {old_tp} erstellt.")
            record["needs_human_review"] = True
            record["review_reason"] = notes[-1]
        intake_marks = ("Auf dem Deckblatt fehlen", "aus dem Inhalt bestimmt",
                        "aus den übrigen Abgaben dieses Uploads übernommen", "aus dem Dateinamen übernommen")
        if complete:
            notes = [n for n in notes if not any(m in n for m in intake_marks)]
        formal["notes"] = notes
        record["formal"] = formal
        if complete and record.get("review_reason") and not tp_changed:
            # Nachtrage-Hinweise sind mit der Bestätigung erledigt; andere Gründe bleiben.
            sentences = re.split(r"(?<=\.)\s+", record["review_reason"])
            rest = " ".join(x for x in sentences if not any(m in x for m in intake_marks)).strip()
            record["review_reason"] = rest or None
            record["needs_human_review"] = bool(rest)

    await asyncio.to_thread(briefing_store.save, record)
    logger.info("briefing_assigned", briefing_id=briefing_id, target_tp=tp, ueg=ueg, sg=sg, by=ctx.label)
    return _public(record)
