from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "backend" / "db" / "submissions"


@dataclass(frozen=True)
class PublishSummary:
    source_path: Path
    output_dir: Path
    published: int
    skipped: int
    needs_human_review_count: int
    technical_fallback_count: int


def _score_counts(scores: list[dict[str, Any]]) -> tuple[int, int]:
    review_count = sum(1 for score in scores if score.get("needs_human_review"))
    fallback_count = sum(
        1 for score in scores if score.get("evaluation_status") == "technical_fallback"
    )
    return review_count, fallback_count


def _dashboard_payload(submission: dict[str, Any]) -> dict[str, Any] | None:
    scores = submission.get("scores") or []
    if submission.get("status") != "evaluated" or not scores:
        return None

    return {
        "submission_id": submission["submission_id"],
        "matrikelnummer": submission.get("matrikelnummer") or submission.get("user_id"),
        "case_id": submission.get("case_id"),
        "target_tp": submission.get("target_tp"),
        "percentage": submission.get("percentage", 0),
        "canvas_alignment_pct": submission.get("canvas_alignment_pct", 0),
        "rubric_fit_pct": submission.get("rubric_fit_pct", 0),
        "canvas_exemplar_candidate": submission.get("canvas_exemplar_candidate", False),
        "submitted_at": submission.get("submitted_at"),
        "evaluated_at": submission.get("evaluated_at"),
        "scores": scores,
        "experiment": submission.get("experiment"),
    }


def publish_dashboard_scores(
    source_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> PublishSummary:
    submissions = json.loads(source_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)

    published = 0
    skipped = 0
    review_total = 0
    fallback_total = 0

    for submission in submissions:
        payload = _dashboard_payload(submission)
        if payload is None:
            skipped += 1
            continue

        review_count, fallback_count = _score_counts(payload["scores"])
        review_total += review_count
        fallback_total += fallback_count

        out_path = output_dir / f"{payload['submission_id']}.json"
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        published += 1

    return PublishSummary(
        source_path=source_path,
        output_dir=output_dir,
        published=published,
        skipped=skipped,
        needs_human_review_count=review_total,
        technical_fallback_count=fallback_total,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Publish evaluated submission-state scores into the dashboard store."
    )
    parser.add_argument("source_path", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Dashboard JSON directory. Defaults to backend/db/submissions.",
    )
    args = parser.parse_args()

    summary = publish_dashboard_scores(args.source_path, args.output_dir)
    print(f"source={summary.source_path}")
    print(f"output_dir={summary.output_dir}")
    print(f"published={summary.published}")
    print(f"skipped={summary.skipped}")
    print(f"needs_human_review_count={summary.needs_human_review_count}")
    print(f"technical_fallback_count={summary.technical_fallback_count}")


if __name__ == "__main__":
    main()
