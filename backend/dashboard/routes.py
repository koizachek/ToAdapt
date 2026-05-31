"""Instructor Dashboard — Matrikelnummer + Scores, keine Chat-Logs."""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SUBMISSIONS_DIR = Path(__file__).parent.parent / "db" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
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
    results = []
    for f in SUBMISSIONS_DIR.glob("*.json"):
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass
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


@router.get("/student/{matrikelnummer}", response_model=StudentRow)
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


@router.get("/students", response_model=list[StudentRow])
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
