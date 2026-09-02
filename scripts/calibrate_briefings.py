"""Kalibrierungslauf für den Briefing-Generator gegen die Beispielabgaben.

Die Kursleitung liefert je Touchpoint drei konstruierte Beispielabgaben
(ueberzeugend / tragfaehig / ansatzweise) mit Einordnung — ausdrücklich zum
Extraktor-Test und zur Prompt-Kalibrierung. Dieses Skript schickt sie durch
den echten Generator und vergleicht die interne Kriterien-Einstufung mit dem
erwarteten Niveau. Das ist das Gate für Änderungen an Prompt oder Rubric
(Klasse B ohne Teacher-Alignment-Baseline — bis reale, anonymisierte
Abgaben vorliegen).

ACHTUNG: Die Beispielabgaben stehen im System-Prompt als Kalibrierungsanker.
Der Lauf misst daher Selbstkonsistenz (erkennt der Judge seine eigenen
Anker wieder?), nicht Generalisierung. Ein Fehlschlag hier ist ein hartes
Warnsignal; ein Erfolg ist notwendig, nicht hinreichend.

Aufruf (vom Repo-Root, OPENROUTER_API_KEY in der Umgebung):
    .venv/bin/python scripts/calibrate_briefings.py --tp 1
    .venv/bin/python scripts/calibrate_briefings.py --all --out report.json
    .venv/bin/python scripts/calibrate_briefings.py --tp 1 --dry-run   # nur Prompts zeigen
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from backend.briefings.extraction import ExtractedSubmission, Kenndaten, count_chars  # noqa: E402
from backend.briefings.generator import (  # noqa: E402
    FeedbackGenerator,
    build_feedback_system_prompt,
    build_system_prompt,
    build_user_prompt,
)
from backend.briefings.rubrics import SUPPORTED_TPS, load_rubric  # noqa: E402


def _example_submission(tp: int, level: str) -> ExtractedSubmission:
    rubric = load_rubric(tp)
    ex = rubric.examples[level]
    sub = ExtractedSubmission(
        filename=f"TP{tp}_UEG00_SG0_{level}.pptx",
        format="pptx",
        kenndaten=Kenndaten(tp=tp, ueg="UEG00", sg=1, code=f"TP{tp}-UEG00-SG1", source="kenndaten"),
        baustein1=ex.slide2,
        baustein2=ex.slide3,
        template_detected=True,
    )
    sub.baustein1_chars = count_chars(ex.slide2)
    sub.baustein2_chars = count_chars(ex.slide3)
    return sub


async def run_tp(tp: int, generator: FeedbackGenerator | None, dry_run: bool, with_feedback: bool = False) -> dict:
    rubric = load_rubric(tp)
    report: dict = {"tp": tp, "levels": {}}
    if dry_run:
        print(f"=== TP{tp} SYSTEM PROMPT ({len(build_system_prompt(rubric))} Zeichen) ===")
        print(build_system_prompt(rubric)[:1500] + "\n…")
        if with_feedback:
            print(f"=== TP{tp} FEEDBACK SYSTEM PROMPT ({len(build_feedback_system_prompt(rubric))} Zeichen) ===")
    for level in rubric.levels:
        sub = _example_submission(tp, level)
        if dry_run:
            print(f"--- TP{tp} · {level} · USER PROMPT ---")
            print(build_user_prompt(rubric, sub)[:600] + "\n…")
            continue
        assert generator is not None
        result = await generator.generate(briefing_id=f"calib-tp{tp}-{level}", rubric=rubric, sub=sub)
        levels = {
            key: [k["niveau"] for k in result["assessment"].get(key, {}).get("kriterien", [])]
            for key in ("baustein1", "baustein2")
        }
        total = sum(len(v) for v in levels.values())
        matched = sum(1 for v in levels.values() for n in v if n == level)
        report["levels"][level] = {
            "evaluation_status": result["evaluation_status"],
            "guardrail_hits": result["guardrail_hits"],
            "needs_human_review": result["needs_human_review"],
            "criteria_levels": levels,
            "match_share": round(matched / total, 2) if total else None,
            "briefing": result["briefing"],
        }
        print(
            f"TP{tp} · erwartet {level:12s} · Treffer {matched}/{total} · "
            f"status={result['evaluation_status']} · guardrails={result['guardrail_hits'] or '-'}"
        )
        for key in ("baustein1", "baustein2"):
            print(f"   {key}: {result['briefing'][key]['kernposition']}")
        if with_feedback:
            fb = await generator.generate_feedback(
                briefing_id=f"calib-fb-tp{tp}-{level}", rubric=rubric, sub=sub, assessment=result["assessment"]
            )
            report["levels"][level]["feedback"] = fb["feedback"]
            report["levels"][level]["feedback_status"] = fb["feedback_status"]
            report["levels"][level]["feedback_guardrail_hits"] = fb["feedback_guardrail_hits"]
            print(f"   feedback: status={fb['feedback_status']} guardrails={fb['feedback_guardrail_hits'] or '-'}")
            for key in ("baustein1", "baustein2"):
                print(f"     {key} · nächster Schritt: {fb['feedback'][key]['naechster_schritt']}")
            print(f"     Ausblick: {fb['feedback']['feed_forward']}")
    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tp", type=int, choices=SUPPORTED_TPS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Nur Prompts zeigen, kein LLM-Call")
    parser.add_argument("--out", type=Path, help="JSON-Report schreiben")
    parser.add_argument("--feedback", action="store_true", help="Zusätzlich das KI-Feedback (Produkt 2) erzeugen")
    args = parser.parse_args()
    if not args.tp and not args.all:
        parser.error("--tp N oder --all angeben")
    tps = list(SUPPORTED_TPS) if args.all else [args.tp]

    generator = None
    if not args.dry_run:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            print("OPENROUTER_API_KEY fehlt (oder --dry-run verwenden)", file=sys.stderr)
            return 2
        generator = FeedbackGenerator(api_key=api_key)

    reports = [await run_tp(tp, generator, args.dry_run, with_feedback=args.feedback) for tp in tps]
    if args.out and not args.dry_run:
        args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
