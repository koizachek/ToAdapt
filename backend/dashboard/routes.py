"""Instructor Dashboard — Matrikelnummer + Scores, keine Chat-Logs."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import reject_revoked_teacher_session, require_api_key, require_research_key
from backend.db.dashboard_store import dashboard_store
from backend.db.group_upload_store import group_upload_store

logger = structlog.get_logger(__name__)
router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_api_key), Depends(reject_revoked_teacher_session)],
)

SEED_SUBMISSIONS_PATH = (
    Path(__file__).parent.parent
    / "db"
    / "dashboard_seed"
    / "teacher_alignment_20260531_17submissions.json"
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class LearningObjectiveScore(BaseModel):
    tag: str
    avg_awarded: float
    avg_max: float
    avg_pct: float
    n: int


class PenaltyCount(BaseModel):
    """Wiederkehrende Schwäche (aus Evaluator-Feedback) mit Häufigkeit."""
    text: str
    count: int


class ObjectiveDifficulty(BaseModel):
    tag: str
    avg_pct: float
    n: int


class CohortObjective(BaseModel):
    tag: str
    avg_pct: float
    students_below: int      # Studierende unter der Schwelle
    students_total: int      # Studierende mit Daten zu diesem Lernziel


class StudentDifficulty(BaseModel):
    """Fehlerquellen-Profil eines Studierenden für Tutor:innen."""
    matrikelnummer: str
    attention_level: str                 # "high" | "medium" | "low"
    attention_reasons: list[str]         # Codes, Frontend übersetzt
    submissions_count: int
    avg_percentage: float
    latest_percentage: float | None = None
    latest_target_tp: int | None = None
    weak_objectives: list[ObjectiveDifficulty]
    weak_blooms: dict[int, float]
    missing_canvas_blocks: list[PenaltyCount]
    recurring_penalties: list[PenaltyCount]
    needs_human_review_count: int
    # Integritäts-HINWEIS (kein Beweis): Antworten mit hohem Paste-Anteil
    paste_heavy_answers: int = 0


class DifficultyOverview(BaseModel):
    threshold_pct: float
    students: list[StudentDifficulty]            # high zuerst
    cohort_weak_objectives: list[CohortObjective]
    cohort_common_penalties: list[PenaltyCount]


class GroupWorkItem(BaseModel):
    """Bewertete Gruppenarbeit (Master-Upload) — Gruppenebene, keine Personen."""
    upload_id: str
    filename: str
    target_tp: int
    percentage: float
    total_points: float
    max_points: float
    needs_human_review: bool = False
    evaluation_status: str = "ok"
    evaluated_at: str | None = None


class GroupSummary(BaseModel):
    """Gruppen-Aggregat für Tutor:innen — enthält KEINE Einzelkennungen."""
    group_code: str
    members_active: int
    submissions_count: int
    avg_percentage: float
    needs_human_review_count: int
    technical_fallback_count: int
    paste_heavy_answers: int
    attention_high: int
    attention_medium: int
    attention_low: int
    # Zweite Datenquelle: außerhalb der Plattform erstellte Gruppenarbeiten,
    # per Master-Upload bewertet (gleiche TP-Rubrics).
    group_work_count: int = 0
    group_work_avg_pct: float | None = None


class GroupObjective(BaseModel):
    tag: str
    avg_pct: float
    members_below: int
    members_total: int


class GroupDetail(GroupSummary):
    weak_objectives: list[GroupObjective]
    weak_blooms: dict[int, int]              # Bloom-Stufe → Mitglieder unter Schwelle
    common_penalties: list[PenaltyCount]
    missing_canvas_blocks: list[PenaltyCount]
    group_work: list[GroupWorkItem] = []


class StudentRow(BaseModel):
    matrikelnummer: str
    submissions_count: int
    avg_percentage: float
    avg_canvas_alignment_pct: float = 0.0
    avg_rubric_fit_pct: float = 0.0
    exemplar_submissions_count: int = 0
    needs_human_review_count: int = 0
    technical_fallback_count: int = 0
    latest_percentage: float | None = None
    latest_canvas_alignment_pct: float | None = None
    latest_rubric_fit_pct: float | None = None
    latest_target_tp: int | None = None
    latest_evaluated_at: str | None = None
    by_tp: dict[int, float]           # TP → avg %
    by_bloom: dict[int, float]        # Bloom-Stufe → avg %
    by_objective: list[LearningObjectiveScore]


class DashboardOverview(BaseModel):
    total_students: int
    total_submissions: int
    avg_percentage: float
    avg_canvas_alignment_pct: float = 0.0
    avg_rubric_fit_pct: float = 0.0
    exemplar_submissions_count: int = 0
    needs_human_review_count: int = 0
    technical_fallback_count: int = 0
    by_tp: dict[int, float]
    by_bloom: dict[int, float]
    top_objectives: list[LearningObjectiveScore]   # top 5 by weakness


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_all_results() -> list[dict]:
    # Primär Mongo (überlebt Redeploys), Datei-Fallback für lokale Entwicklung.
    results = dashboard_store.load_all()
    if results:
        return results

    try:
        seed_results = json.loads(SEED_SUBMISSIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(seed_results, list):
        return []
    return seed_results


def _aggregate_objectives(scores_list: list[dict]) -> list[LearningObjectiveScore]:
    """Aggregiert Scores nach Lernziel-Tags."""
    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for score in scores_list:
        for tag in score.get("learning_objective_tags", []):
            buckets[tag].append((score["awarded_points"], score["max_points"]))

    out = []
    for tag, pairs in buckets.items():
        n = len(pairs)
        avg_a = sum(p[0] for p in pairs) / n
        avg_m = sum(p[1] for p in pairs) / n
        pct = round(avg_a / avg_m * 100, 1) if avg_m else 0
        out.append(LearningObjectiveScore(tag=tag, avg_awarded=avg_a, avg_max=avg_m, avg_pct=pct, n=n))

    return sorted(out, key=lambda x: x.avg_pct)   # weakest first


def _result_timestamp(result: dict) -> datetime:
    value = result.get("evaluated_at") or result.get("submitted_at") or ""
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.min


def _latest_result(results: list[dict]) -> dict | None:
    if not results:
        return None
    return max(results, key=_result_timestamp)


def _review_counts(results: list[dict]) -> tuple[int, int]:
    review_count = 0
    fallback_count = 0
    for result in results:
        for score in result.get("scores", []):
            if score.get("needs_human_review"):
                review_count += 1
            if score.get("evaluation_status") == "technical_fallback":
                fallback_count += 1
    return review_count, fallback_count


# Unterhalb dieser Quote gilt ein Lernziel/Bloom-Level als Schwierigkeit.
WEAK_THRESHOLD_PCT = 60.0

# Paste-Hinweis: Antwort gilt als "paste-lastig", wenn mehr als die Hälfte
# der Zeichen eingefügt wurde UND absolut substanziell Text eingefügt wurde.
PASTE_SHARE_THRESHOLD = 0.5
PASTE_MIN_CHARS = 300


def _count_paste_heavy(results: list[dict]) -> int:
    count = 0
    for r in results:
        for stats in (r.get("answer_stats") or {}).values():
            typed = stats.get("typed_chars", 0) or 0
            pasted = stats.get("pasted_chars", 0) or 0
            total = typed + pasted
            if total > 0 and pasted >= PASTE_MIN_CHARS and pasted / total > PASTE_SHARE_THRESHOLD:
                count += 1
    return count


def _normalize_phrase(text: str) -> str:
    return " ".join(text.strip().rstrip(".!").split())


def _add_phrase(bucket: dict[str, list], text: str) -> None:
    """Zählt Phrasen case-insensitiv, behält die erste Schreibweise als Anzeige."""
    norm = _normalize_phrase(text)
    if not norm:
        return
    key = norm.casefold()
    if key in bucket:
        bucket[key][1] += 1
    else:
        bucket[key] = [norm, 1]


def _top_phrases(bucket: dict[str, list], limit: int = 5) -> list[PenaltyCount]:
    ranked = sorted(bucket.values(), key=lambda item: -item[1])[:limit]
    return [PenaltyCount(text=text, count=count) for text, count in ranked]


def _student_difficulty(matrikel: str, results: list[dict]) -> StudentDifficulty:
    all_scores = [s for r in results for s in r.get("scores", [])]

    weak_objectives = [
        ObjectiveDifficulty(tag=o.tag, avg_pct=o.avg_pct, n=o.n)
        for o in _aggregate_objectives(all_scores)
        if o.avg_pct < WEAK_THRESHOLD_PCT
    ]

    bloom_buckets: dict[int, list[tuple]] = defaultdict(list)
    for s in all_scores:
        bloom_buckets[s["bloom_level"]].append((s["awarded_points"], s["max_points"]))
    weak_blooms = {}
    for lvl, pairs in bloom_buckets.items():
        max_sum = sum(p[1] for p in pairs)
        pct = round(sum(p[0] for p in pairs) / max_sum * 100, 1) if max_sum else 0.0
        if pct < WEAK_THRESHOLD_PCT:
            weak_blooms[lvl] = pct

    penalties: dict[str, list] = {}
    missing_blocks: dict[str, list] = {}
    for s in all_scores:
        for p in s.get("main_penalties", []):
            _add_phrase(penalties, str(p))
        for b in s.get("missing_canvas_blocks", []):
            _add_phrase(missing_blocks, str(b))

    avg_pct = round(sum(r["percentage"] for r in results) / len(results), 1)
    latest = _latest_result(results)
    latest_pct = latest.get("percentage") if latest else None
    review_count, _ = _review_counts(results)
    paste_heavy = _count_paste_heavy(results)

    reasons: list[str] = []
    if avg_pct < 50:
        reasons.append("low_avg")
    if latest_pct is not None and latest_pct < 45:
        reasons.append("low_latest")
    if len(weak_objectives) >= 2:
        reasons.append("multiple_weak_objectives")
    elif len(weak_objectives) == 1:
        reasons.append("weak_objective")
    if weak_blooms:
        reasons.append("weak_bloom")
    if review_count > 0:
        reasons.append("needs_review")
    if paste_heavy > 0:
        reasons.append("paste_heavy")

    if "low_avg" in reasons or "low_latest" in reasons or "multiple_weak_objectives" in reasons:
        attention = "high"
    elif reasons:
        attention = "medium"
    else:
        attention = "low"

    return StudentDifficulty(
        matrikelnummer=matrikel,
        attention_level=attention,
        attention_reasons=reasons,
        submissions_count=len(results),
        avg_percentage=avg_pct,
        latest_percentage=latest_pct,
        latest_target_tp=latest.get("target_tp") if latest else None,
        weak_objectives=weak_objectives,
        weak_blooms=weak_blooms,
        missing_canvas_blocks=_top_phrases(missing_blocks),
        recurring_penalties=_top_phrases(penalties),
        needs_human_review_count=review_count,
        paste_heavy_answers=paste_heavy,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=DashboardOverview)
async def get_overview():
    results = _load_all_results()
    if not results:
        return DashboardOverview(
            total_students=0, total_submissions=0, avg_percentage=0,
            avg_canvas_alignment_pct=0,
            avg_rubric_fit_pct=0,
            exemplar_submissions_count=0,
            needs_human_review_count=0,
            technical_fallback_count=0,
            by_tp={}, by_bloom={}, top_objectives=[],
        )

    students = set(r["matrikelnummer"] for r in results)
    all_scores = [s for r in results for s in r.get("scores", [])]

    # By TP
    tp_buckets: dict[int, list[float]] = defaultdict(list)
    for r in results:
        tp_buckets[r["target_tp"]].append(r["percentage"])
    by_tp = {tp: round(sum(v)/len(v), 1) for tp, v in tp_buckets.items()}

    # By Bloom
    bloom_buckets: dict[int, list[tuple]] = defaultdict(list)
    for s in all_scores:
        bloom_buckets[s["bloom_level"]].append((s["awarded_points"], s["max_points"]))
    by_bloom = {
        lvl: round(sum(p[0] for p in pairs) / sum(p[1] for p in pairs) * 100, 1)
        for lvl, pairs in bloom_buckets.items() if pairs
    }

    avg_pct = round(sum(r["percentage"] for r in results) / len(results), 1)
    avg_canvas_alignment_pct = round(
        sum(r.get("canvas_alignment_pct", 0) for r in results) / len(results),
        1,
    )
    avg_rubric_fit_pct = round(
        sum(r.get("rubric_fit_pct", 0) for r in results) / len(results),
        1,
    )
    exemplar_submissions_count = sum(
        1 for r in results if r.get("canvas_exemplar_candidate")
    )
    needs_human_review_count, technical_fallback_count = _review_counts(results)

    return DashboardOverview(
        total_students=len(students),
        total_submissions=len(results),
        avg_percentage=avg_pct,
        avg_canvas_alignment_pct=avg_canvas_alignment_pct,
        avg_rubric_fit_pct=avg_rubric_fit_pct,
        exemplar_submissions_count=exemplar_submissions_count,
        needs_human_review_count=needs_human_review_count,
        technical_fallback_count=technical_fallback_count,
        by_tp=by_tp,
        by_bloom=by_bloom,
        top_objectives=_aggregate_objectives(all_scores)[:5],
    )


UNGROUPED = "OHNE-GRUPPE"


def _results_by_group(results: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        grouped[str(r.get("group_code") or "").strip() or UNGROUPED].append(r)
    return grouped


def _group_uploads_by_group() -> dict[str, list[dict]]:
    """Bewertete Gruppenarbeiten (Master-Upload) nach Gruppencode.

    extraction_failed-Einträge bleiben draußen (keine belastbare Bewertung);
    nicht zuordenbare Dokumente laufen unter UNGROUPED, bis der Master-Tutor
    die Gruppe nachträgt.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in group_upload_store.load_all():
        if record.get("status") != "evaluated":
            continue
        code = str(record.get("group_code") or "").strip() or UNGROUPED
        grouped[code].append(record)
    return grouped


def _group_work_items(uploads: list[dict]) -> list[GroupWorkItem]:
    items = [
        GroupWorkItem(
            upload_id=str(u.get("upload_id", "")),
            filename=str(u.get("filename", "")),
            target_tp=int(u.get("target_tp", 0)),
            percentage=float(u.get("percentage", 0.0)),
            total_points=float(u.get("total_points", 0.0)),
            max_points=float(u.get("max_points", 0.0)),
            needs_human_review=bool(u.get("needs_human_review", False)),
            evaluation_status=str(u.get("evaluation_status", "ok")),
            evaluated_at=u.get("evaluated_at"),
        )
        for u in uploads
    ]
    items.sort(key=lambda i: (i.target_tp, i.evaluated_at or ""))
    return items


def _group_detail(group_code: str, results: list[dict], uploads: list[dict] | None = None) -> GroupDetail:
    """Aggregiert eine Gruppe über ihre (pseudonymen) Mitglieder — Einzel-
    kennungen verlassen diese Funktion nicht. `uploads` sind die per
    Master-Upload bewerteten Gruppenarbeiten derselben Gruppe."""
    uploads = uploads or []
    by_member: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_member[r["matrikelnummer"]].append(r)

    member_difficulties = [
        _student_difficulty(matrikel, member_results)
        for matrikel, member_results in by_member.items()
    ]

    attention = {"high": 0, "medium": 0, "low": 0}
    for d in member_difficulties:
        attention[d.attention_level] += 1

    review_count, fallback_count = _review_counts(results)

    # Lernziele: pro Mitglied bewerten, dann zählen wie viele unter Schwelle
    tag_pcts: dict[str, list[float]] = defaultdict(list)
    for matrikel, member_results in by_member.items():
        all_scores = [s for r in member_results for s in r.get("scores", [])]
        for o in _aggregate_objectives(all_scores):
            tag_pcts[o.tag].append(o.avg_pct)
    weak_objectives = sorted(
        (
            GroupObjective(
                tag=tag,
                avg_pct=round(sum(pcts) / len(pcts), 1),
                members_below=sum(1 for pct in pcts if pct < WEAK_THRESHOLD_PCT),
                members_total=len(pcts),
            )
            for tag, pcts in tag_pcts.items()
        ),
        key=lambda o: (-o.members_below, o.avg_pct),
    )[:8]

    bloom_below: dict[int, int] = defaultdict(int)
    for d in member_difficulties:
        for level in d.weak_blooms:
            bloom_below[int(level)] += 1

    penalties: dict[str, list] = {}
    missing_blocks: dict[str, list] = {}
    for r in results:
        for s in r.get("scores", []):
            for p in s.get("main_penalties", []):
                _add_phrase(penalties, str(p))
            for b in s.get("missing_canvas_blocks", []):
                _add_phrase(missing_blocks, str(b))

    group_work_pcts = [float(u.get("percentage", 0.0)) for u in uploads]

    return GroupDetail(
        group_code=group_code,
        members_active=len(by_member),
        submissions_count=len(results),
        avg_percentage=(
            round(sum(r["percentage"] for r in results) / len(results), 1) if results else 0.0
        ),
        needs_human_review_count=review_count,
        technical_fallback_count=fallback_count,
        paste_heavy_answers=_count_paste_heavy(results),
        attention_high=attention["high"],
        attention_medium=attention["medium"],
        attention_low=attention["low"],
        group_work_count=len(uploads),
        group_work_avg_pct=(
            round(sum(group_work_pcts) / len(group_work_pcts), 1) if group_work_pcts else None
        ),
        weak_objectives=weak_objectives,
        weak_blooms=dict(bloom_below),
        common_penalties=_top_phrases(penalties, limit=6),
        missing_canvas_blocks=_top_phrases(missing_blocks, limit=6),
        group_work=_group_work_items(uploads),
    )


@router.get("/groups", response_model=list[GroupSummary])
async def list_groups():
    """Gruppen-Übersicht für Tutor:innen (nur Aggregate, keine Personen).

    Vereint beide Datenquellen: individuelle Submissions und per
    Master-Upload bewertete Gruppenarbeiten — Gruppen, die bisher nur über
    eine der beiden Quellen sichtbar sind, erscheinen trotzdem.
    """
    grouped = _results_by_group(_load_all_results())
    uploads_grouped = _group_uploads_by_group()
    codes = set(grouped) | set(uploads_grouped)
    details = [
        _group_detail(code, grouped.get(code, []), uploads_grouped.get(code, []))
        for code in codes
    ]
    order = {code: i for i, code in enumerate(sorted(codes))}
    details.sort(key=lambda d: (d.group_code == UNGROUPED, order.get(d.group_code, 0)))
    return [GroupSummary(**d.model_dump(include=set(GroupSummary.model_fields))) for d in details]


@router.get("/groups/{group_code}", response_model=GroupDetail)
async def group_detail(group_code: str):
    """Fehlerquellen-Zusammenfassung EINER Gruppe (keine Einzelprofile)."""
    grouped = _results_by_group(_load_all_results())
    uploads_grouped = _group_uploads_by_group()
    normalized = group_code.strip().upper()
    code = (
        normalized if (normalized in grouped or normalized in uploads_grouped) else group_code
    )
    results = grouped.get(code, [])
    uploads = uploads_grouped.get(code, [])
    if not results and not uploads:
        raise HTTPException(status_code=404, detail="Gruppe nicht gefunden")
    return _group_detail(code, results, uploads)


@router.get(
    "/difficulties",
    response_model=DifficultyOverview,
    dependencies=[Depends(require_research_key)],
)
async def get_difficulties():
    """Fehlerquellen-Sicht für Tutor:innen.

    Zeigt pro Studierendem, wo es hakt (schwache Lernziele/Bloom-Stufen,
    fehlende Canvas-Blöcke, wiederkehrende Schwächen aus dem Evaluator-
    Feedback) und priorisiert, wer Aufmerksamkeit braucht. Kohorten-Teil:
    Welche Lernziele und Schwächen treten am häufigsten auf?
    """
    results = _load_all_results()
    by_student: dict[str, list] = defaultdict(list)
    for r in results:
        by_student[r["matrikelnummer"]].append(r)

    students = [
        _student_difficulty(matrikel, student_results)
        for matrikel, student_results in by_student.items()
    ]
    order = {"high": 0, "medium": 1, "low": 2}
    students.sort(key=lambda s: (order[s.attention_level], s.avg_percentage))

    # Kohorte: Lernziele — wie viele Studierende liegen jeweils unter der Schwelle?
    per_student_objectives: dict[str, dict[str, float]] = {}
    for matrikel, student_results in by_student.items():
        all_scores = [s for r in student_results for s in r.get("scores", [])]
        per_student_objectives[matrikel] = {
            o.tag: o.avg_pct for o in _aggregate_objectives(all_scores)
        }

    tag_pcts: dict[str, list[float]] = defaultdict(list)
    for objectives in per_student_objectives.values():
        for tag, pct in objectives.items():
            tag_pcts[tag].append(pct)

    cohort_weak_objectives = sorted(
        (
            CohortObjective(
                tag=tag,
                avg_pct=round(sum(pcts) / len(pcts), 1),
                students_below=sum(1 for pct in pcts if pct < WEAK_THRESHOLD_PCT),
                students_total=len(pcts),
            )
            for tag, pcts in tag_pcts.items()
        ),
        key=lambda o: (-o.students_below, o.avg_pct),
    )[:8]

    cohort_penalties: dict[str, list] = {}
    for r in results:
        for s in r.get("scores", []):
            for p in s.get("main_penalties", []):
                _add_phrase(cohort_penalties, str(p))

    return DifficultyOverview(
        threshold_pct=WEAK_THRESHOLD_PCT,
        students=students,
        cohort_weak_objectives=cohort_weak_objectives,
        cohort_common_penalties=_top_phrases(cohort_penalties, limit=8),
    )


@router.get(
    "/student/{matrikelnummer}",
    response_model=StudentRow,
    dependencies=[Depends(require_research_key)],
)
async def get_student(matrikelnummer: str):
    results = [r for r in _load_all_results() if r["matrikelnummer"] == matrikelnummer]
    if not results:
        raise HTTPException(status_code=404, detail="Student nicht gefunden")

    all_scores = [s for r in results for s in r.get("scores", [])]

    tp_buckets: dict[int, list[float]] = defaultdict(list)
    for r in results:
        tp_buckets[r["target_tp"]].append(r["percentage"])
    by_tp = {tp: round(sum(v)/len(v), 1) for tp, v in tp_buckets.items()}

    bloom_buckets: dict[int, list[tuple]] = defaultdict(list)
    for s in all_scores:
        bloom_buckets[s["bloom_level"]].append((s["awarded_points"], s["max_points"]))
    by_bloom = {
        lvl: round(sum(p[0] for p in pairs) / sum(p[1] for p in pairs) * 100, 1)
        for lvl, pairs in bloom_buckets.items() if pairs
    }

    avg_pct = round(sum(r["percentage"] for r in results) / len(results), 1)
    latest = _latest_result(results)
    needs_human_review_count, technical_fallback_count = _review_counts(results)

    return StudentRow(
        matrikelnummer=matrikelnummer,
        submissions_count=len(results),
        avg_percentage=avg_pct,
        avg_canvas_alignment_pct=round(
            sum(r.get("canvas_alignment_pct", 0) for r in results) / len(results),
            1,
        ),
        avg_rubric_fit_pct=round(
            sum(r.get("rubric_fit_pct", 0) for r in results) / len(results),
            1,
        ),
        exemplar_submissions_count=sum(
            1 for r in results if r.get("canvas_exemplar_candidate")
        ),
        needs_human_review_count=needs_human_review_count,
        technical_fallback_count=technical_fallback_count,
        latest_percentage=latest.get("percentage") if latest else None,
        latest_canvas_alignment_pct=latest.get("canvas_alignment_pct") if latest else None,
        latest_rubric_fit_pct=latest.get("rubric_fit_pct") if latest else None,
        latest_target_tp=latest.get("target_tp") if latest else None,
        latest_evaluated_at=latest.get("evaluated_at") if latest else None,
        by_tp=by_tp,
        by_bloom=by_bloom,
        by_objective=_aggregate_objectives(all_scores),
    )


@router.get(
    "/students",
    response_model=list[StudentRow],
    dependencies=[Depends(require_research_key)],
)
async def list_students():
    results = _load_all_results()
    by_student: dict[str, list] = defaultdict(list)
    for r in results:
        by_student[r["matrikelnummer"]].append(r)

    rows = []
    for matrikel, student_results in by_student.items():
        all_scores = [s for r in student_results for s in r.get("scores", [])]
        latest = _latest_result(student_results)
        needs_human_review_count, technical_fallback_count = _review_counts(student_results)
        tp_buckets: dict[int, list[float]] = defaultdict(list)
        for r in student_results:
            tp_buckets[r["target_tp"]].append(r["percentage"])
        by_tp = {tp: round(sum(v)/len(v), 1) for tp, v in tp_buckets.items()}

        bloom_buckets: dict[int, list[tuple]] = defaultdict(list)
        for s in all_scores:
            bloom_buckets[s["bloom_level"]].append((s["awarded_points"], s["max_points"]))
        by_bloom = {
            lvl: round(sum(p[0] for p in pairs) / sum(p[1] for p in pairs) * 100, 1)
            for lvl, pairs in bloom_buckets.items() if pairs
        }

        rows.append(StudentRow(
            matrikelnummer=matrikel,
            submissions_count=len(student_results),
            avg_percentage=round(sum(r["percentage"] for r in student_results) / len(student_results), 1),
            avg_canvas_alignment_pct=round(
                sum(r.get("canvas_alignment_pct", 0) for r in student_results) / len(student_results),
                1,
            ),
            avg_rubric_fit_pct=round(
                sum(r.get("rubric_fit_pct", 0) for r in student_results) / len(student_results),
                1,
            ),
            exemplar_submissions_count=sum(
                1 for r in student_results if r.get("canvas_exemplar_candidate")
            ),
            needs_human_review_count=needs_human_review_count,
            technical_fallback_count=technical_fallback_count,
            latest_percentage=latest.get("percentage") if latest else None,
            latest_canvas_alignment_pct=latest.get("canvas_alignment_pct") if latest else None,
            latest_rubric_fit_pct=latest.get("rubric_fit_pct") if latest else None,
            latest_target_tp=latest.get("target_tp") if latest else None,
            latest_evaluated_at=latest.get("evaluated_at") if latest else None,
            by_tp=by_tp,
            by_bloom=by_bloom,
            by_objective=_aggregate_objectives(all_scores),
        ))

    return sorted(rows, key=lambda x: x.avg_percentage)
