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
    .venv/bin/python scripts/calibrate_briefings.py --all --language en   # englische Beispielabgaben
    .venv/bin/python scripts/calibrate_briefings.py --all --language both

Mit ``--language en`` laufen die englischen Beispielabgaben
(``backend/config/ki_rubrics/en/``) durch den englischen Prompt; zusätzlich
wird geprüft, dass die Spracherkennung sie als englisch erkennt.
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
    BriefingGenerator,
    build_system_prompt,
    build_user_prompt,
)
from backend.briefings.i18n import detect_language  # noqa: E402
from backend.briefings.rubrics import SUPPORTED_TPS, load_rubric  # noqa: E402


def _example_submission(tp: int, level: str, language: str = "de") -> ExtractedSubmission:
    rubric = load_rubric(tp, language)
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


async def run_tp(tp: int, generator: BriefingGenerator | None, dry_run: bool, language: str = "de") -> dict:
    rubric = load_rubric(tp, language)
    report: dict = {"tp": tp, "language": language, "levels": {}}
    if dry_run:
        print(f"=== TP{tp} [{language}] SYSTEM PROMPT ({len(build_system_prompt(rubric, language))} Zeichen) ===")
        print(build_system_prompt(rubric, language)[:1500] + "\n…")
    for level in rubric.levels:
        sub = _example_submission(tp, level, language)
        detected = detect_language(f"{sub.baustein1}\n{sub.baustein2}")
        if dry_run:
            print(f"--- TP{tp} · {level} · USER PROMPT ---")
            print(build_user_prompt(rubric, sub)[:600] + "\n…")
            continue
        assert generator is not None
        result = await generator.generate(
            briefing_id=f"calib-tp{tp}-{language}-{level}", rubric=rubric, sub=sub, language=language,
        )
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
            "detected_language": detected,
            "briefing": result["briefing"],
        }
        print(
            f"TP{tp} [{language}, erkannt {detected}] · erwartet {level:12s} · Treffer {matched}/{total} · "
            f"status={result['evaluation_status']} · guardrails={result['guardrail_hits'] or '-'}"
        )
        for key in ("baustein1", "baustein2"):
            print(f"   {key}: {result['briefing'][key]['kernposition']}")
            print(f"      nächster Schritt: {result['briefing'][key].get('naechster_schritt', '')}")
            for thin in result["briefing"][key].get("duenne_stellen", []):
                print(f"      dünn: {thin}")
    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tp", type=int, choices=SUPPORTED_TPS)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Nur Prompts zeigen, kein LLM-Call")
    parser.add_argument("--out", type=Path, help="JSON-Report schreiben")
    parser.add_argument("--language", choices=["de", "en", "both"], default="de",
                        help="Sprache der Beispielabgaben und des Briefings (Standard de)")
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
        generator = BriefingGenerator(api_key=api_key)

    languages = ["de", "en"] if args.language == "both" else [args.language]
    reports = [await run_tp(tp, generator, args.dry_run, lang) for lang in languages for tp in tps]
    if args.out and not args.dry_run:
        args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
