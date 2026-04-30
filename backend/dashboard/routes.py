"""Instructor Dashboard — Matrikelnummer + Scores, keine Chat-Logs."""

from collections import defaultdict
from pathlib import Path
import json

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SUBMISSIONS_DIR = Path(__file__).parent.parent / "db" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)


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
    by_tp: dict[int, float]           # TP → avg %
    by_bloom: dict[int, float]        # Bloom-Stufe → avg %
    by_objective: list[LearningObjectiveScore]


class DashboardOverview(BaseModel):
    total_students: int
    total_submissions: int
    avg_percentage: float
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
    return results


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=DashboardOverview)
async def get_overview():
    results = _load_all_results()
    if not results:
        return DashboardOverview(
            total_students=0, total_submissions=0, avg_percentage=0,
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

    return DashboardOverview(
        total_students=len(students),
        total_submissions=len(results),
        avg_percentage=avg_pct,
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

    return StudentRow(
        matrikelnummer=matrikelnummer,
        submissions_count=len(results),
        avg_percentage=avg_pct,
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
            by_tp=by_tp,
            by_bloom=by_bloom,
            by_objective=_aggregate_objectives(all_scores),
        ))

    return sorted(rows, key=lambda x: x.avg_percentage)
