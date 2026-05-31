"""Retry only LLM-judge scores that ended in technical_fallback."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.cases.manager import case_manager
from backend.evaluator.rubric_evaluator import RubricEvaluator
from backend.llm import get_openrouter_key
from backend.models.submission import QuestionScore, Submission, SubmissionStatus


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DASHBOARD_DIR = REPO_ROOT / "backend" / "db" / "submissions"
DEFAULT_COMPARISON_CSV = (
    REPO_ROOT
    / "data"
    / "prolific_runs"
    / "derived"
    / "aligned_rescores"
    / "teacher_rubric_comparison_aligned_20260531T140830Z_item_comparison.csv"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")


def _load_answer_index(path: Path) -> dict[tuple[str, str], str]:
    if not path.exists():
        return {}

    answers: dict[tuple[str, str], str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            submission_id = (row.get("submission_id") or "").strip()
            question_id = (row.get("question_id") or "").strip()
            answer_text = row.get("answer_text") or ""
            if submission_id and question_id and answer_text.strip():
                answers[(submission_id, question_id)] = answer_text
    return answers


def _fallback_question_ids(scores: list[dict[str, Any]]) -> list[str]:
    return [
        str(score.get("question_id"))
        for score in scores
        if score.get("evaluation_status") == "technical_fallback"
        and score.get("question_id")
    ]


def _submission_from_dashboard(payload: dict[str, Any], answers: dict[str, str]) -> Submission:
    return Submission(
        submission_id=payload["submission_id"],
        user_id=payload.get("user_id") or payload.get("matrikelnummer") or payload["submission_id"],
        matrikelnummer=payload.get("matrikelnummer") or payload["submission_id"],
        case_id=payload["case_id"],
        target_tp=int(payload.get("target_tp") or 1),
        answers=answers,
        scores=[QuestionScore.model_validate(score) for score in payload.get("scores", [])],
        status=SubmissionStatus.EVALUATED,
    )


def _replace_score(scores: list[dict[str, Any]], replacement: QuestionScore) -> list[dict[str, Any]]:
    replaced = False
    output: list[dict[str, Any]] = []
    for score in scores:
        if score.get("question_id") == replacement.question_id:
            output.append(replacement.model_dump(mode="json", exclude_none=True))
            replaced = True
        else:
            output.append(score)
    if not replaced:
        output.append(replacement.model_dump(mode="json", exclude_none=True))
    return output


async def retry_dashboard_file(
    *,
    path: Path,
    evaluator: RubricEvaluator,
    answer_index: dict[tuple[str, str], str],
    dry_run: bool,
) -> tuple[int, int]:
    payload = _read_json(path)
    fallback_ids = _fallback_question_ids(payload.get("scores", []))
    if not fallback_ids:
        return 0, 0

    case = case_manager.get(payload["case_id"])
    if not case:
        raise RuntimeError(f"Case not found for {path}: {payload['case_id']}")

    answers = {
        question_id: answer_index.get((payload["submission_id"], question_id), "")
        for question_id in fallback_ids
    }
    missing_answers = [question_id for question_id, answer in answers.items() if not answer.strip()]
    if missing_answers:
        raise RuntimeError(
            f"Missing answer_text for {path.name}: {', '.join(missing_answers)}. "
            "Pass --comparison-csv with answer_text rows."
        )

    submission = _submission_from_dashboard(payload, answers)
    replaced_count = 0
    still_fallback_count = 0
    scores = list(payload.get("scores", []))

    for question_id in fallback_ids:
        score, _rubric = await evaluator.evaluate_question(
            submission=submission,
            case=case,
            question_id=question_id,
            answer_text=answers[question_id],
        )
        replaced_count += 1
        if score.evaluation_status == "technical_fallback":
            still_fallback_count += 1
        scores = _replace_score(scores, score)

    score_models = [QuestionScore.model_validate(score) for score in scores]
    result = evaluator.result_from_scores(
        submission=submission,
        case=case,
        scores=score_models,
    )

    payload["scores"] = [score.model_dump(mode="json", exclude_none=True) for score in result.scores]
    payload["total_points"] = result.total_points
    payload["max_points"] = result.max_points
    payload["percentage"] = result.percentage
    payload["canvas_alignment_pct"] = result.canvas_alignment_pct
    payload["rubric_fit_pct"] = result.rubric_fit_pct
    payload["canvas_exemplar_candidate"] = result.canvas_exemplar_candidate
    payload["technical_fallback_retried_at"] = datetime.utcnow().isoformat()

    if not dry_run:
        _write_json(path, payload)

    return replaced_count, still_fallback_count


async def main_async() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dashboard-dir", type=Path, default=DEFAULT_DASHBOARD_DIR)
    parser.add_argument("--comparison-csv", type=Path, default=DEFAULT_COMPARISON_CSV)
    parser.add_argument("--submission-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = get_openrouter_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY nicht konfiguriert")

    answer_index = _load_answer_index(args.comparison_csv)
    evaluator = RubricEvaluator(api_key=api_key)
    files = sorted(args.dashboard_dir.glob("*.json"))
    if args.submission_id:
        wanted = set(args.submission_id)
        files = [path for path in files if path.stem in wanted]

    total_retried = 0
    total_still_fallback = 0
    for path in files:
        retried, still_fallback = await retry_dashboard_file(
            path=path,
            evaluator=evaluator,
            answer_index=answer_index,
            dry_run=args.dry_run,
        )
        if retried:
            print(f"{path.name}: retried={retried} still_fallback={still_fallback}")
        total_retried += retried
        total_still_fallback += still_fallback

    print(f"total_retried={total_retried}")
    print(f"total_still_fallback={total_still_fallback}")
    return 0


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
