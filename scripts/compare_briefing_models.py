"""Modellvergleich für die KI-Briefings: dieselben Abgaben, verschiedene LLMs.

Schickt jede Datei einer Test-ZIP durch Extraktion → Briefing → Feedback mit
dem angegebenen OpenRouter-Modell und legt je Modell EIN Word-Dokument mit
allen Stammgruppen ab (identischer Renderer wie im Betrieb) plus die rohen
Datensätze als JSON (für Nachvergleiche). Optional wird ein bestehender
Lauf aus dem lokalen Datei-Store (backend/db/briefings/*.json, z.B. der
Produktions-Default Claude) ohne neue LLM-Calls als Vergleichsdokument
gerendert.

Aufruf (vom Repo-Root, echte LLM-Calls, kostet Geld):
    .venv/bin/python scripts/compare_briefing_models.py \\
        --zip docs/beispiele/TP1_UEG07_submissions.zip \\
        --model mistralai/mistral-large-2512 --model deepseek/deepseek-v3.2 \\
        --from-store anthropic/claude-sonnet-4.5 \\
        --out docs/beispiele/modellvergleich

Klasse B2 (Tutor-Pipeline) — Ergebnisse sind Vergleichsmaterial, keine
Freigabe eines Modells. Die Modellwahl für den Betrieb bleibt OPENROUTER_MODEL.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import uuid
import zipfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.briefings.docx_render import render_briefing_docx  # noqa: E402
from backend.briefings.extraction import build_code, extract_submission  # noqa: E402
from backend.briefings.formal import formal_checks  # noqa: E402
from backend.briefings.generator import FeedbackGenerator  # noqa: E402
from backend.briefings.rubrics import SUPPORTED_TPS, load_rubric  # noqa: E402
from backend.llm import get_openrouter_key  # noqa: E402
from backend.timeutils import naive_utcnow  # noqa: E402

STORE_DIR = Path(__file__).resolve().parent.parent / "backend" / "db" / "briefings"


def _slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9.]+", "-", model).strip("-")


async def _run_model(model: str, entries: list[tuple[str, bytes]], api_key: str) -> list[dict]:
    generator = FeedbackGenerator(api_key=api_key, model=model)
    rubrics = {}
    records: list[dict] = []
    for filename, data in entries:
        sub = extract_submission(filename, data, None)
        tp = sub.kenndaten.tp
        if tp in SUPPORTED_TPS:
            sub = extract_submission(filename, data, tp)
        if tp not in SUPPORTED_TPS:
            print(f"  {filename}: Touchpoint nicht erkannt — übersprungen")
            continue
        rubric = rubrics.setdefault(tp, load_rubric(tp))
        kd = sub.kenndaten
        started = time.perf_counter()
        result = await generator.generate(briefing_id=str(uuid.uuid4()), rubric=rubric, sub=sub)
        feedback = await generator.generate_feedback(
            briefing_id=str(uuid.uuid4()), rubric=rubric, sub=sub,
            assessment=result["assessment"] if result["evaluation_status"] == "ok" else None,
        )
        seconds = time.perf_counter() - started
        q = result["briefing"].get("rueckfragen", {})
        print(
            f"  {filename}: {result['evaluation_status']} · Feedback {feedback['feedback_status']} · "
            f"Rückfragen {len(q.get('zu_staerken', []))}+{len(q.get('zu_schwaechen', []))} · "
            f"Leitplanken {result.get('guardrail_hits') or '-'} / {feedback.get('feedback_guardrail_hits') or '-'} · {seconds:.0f}s"
        )
        records.append({
            "briefing_id": str(uuid.uuid4()),
            "filename": filename,
            "format": sub.format,
            "target_tp": tp,
            "ueg": kd.ueg,
            "sg": kd.sg,
            "code": build_code(tp, kd.ueg, kd.sg) if kd.ueg and kd.sg else None,
            "status": "no_content" if result["evaluation_status"] == "no_content" else "briefed",
            "uploaded_at": naive_utcnow().isoformat(),
            "uploaded_by": f"modellvergleich:{model}",
            "evaluation_status": result["evaluation_status"],
            "needs_human_review": bool(result["needs_human_review"]),
            "review_reason": result.get("review_reason"),
            "guardrail_hits": list(result.get("guardrail_hits", [])),
            "formal": formal_checks(sub, rubric, tp),
            "briefing": result["briefing"],
            "assessment": result["assessment"],
            "feedback": feedback["feedback"],
            "feedback_status": feedback["feedback_status"],
            "feedback_guardrail_hits": list(feedback.get("feedback_guardrail_hits", [])),
            "feedback_needs_human_review": bool(feedback.get("feedback_needs_human_review")),
            "feedback_review_reason": feedback.get("feedback_review_reason"),
            "model": model,
            "seconds": round(seconds, 1),
        })
    return records


def _from_store(uploaded_by: str) -> list[dict]:
    records = []
    for f in STORE_DIR.glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r.get("uploaded_by") == uploaded_by and r.get("status") == "briefed":
            records.append(r)
    # neuester Datensatz je Gruppe
    latest: dict[tuple, dict] = {}
    for r in records:
        key = (r.get("target_tp"), r.get("ueg"), r.get("sg"))
        if key not in latest or r["uploaded_at"] > latest[key]["uploaded_at"]:
            latest[key] = r
    return list(latest.values())


def _write(records: list[dict], model_label: str, out: Path) -> None:
    if not records:
        print(f"  {model_label}: keine Datensätze")
        return
    tp = int(records[0]["target_tp"])
    ueg = records[0].get("ueg") or "UEG"
    rubric = load_rubric(tp)
    slug = _slug(model_label)
    docx = out / f"KI-Briefing_TP{tp}_{ueg}_{slug}.docx"
    docx.write_bytes(render_briefing_docx(sorted(records, key=lambda r: int(r.get("sg") or 99)), rubric=rubric, ueg=ueg))
    (out / f"KI-Briefing_TP{tp}_{ueg}_{slug}.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    print(f"  → {docx.relative_to(Path.cwd()) if docx.is_absolute() else docx}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zip", required=True, type=Path, help="ZIP mit Abgaben (PPTX/DOCX/PDF)")
    parser.add_argument("--model", action="append", default=[], help="OpenRouter-Modell-ID (mehrfach möglich)")
    parser.add_argument("--from-store", default=None,
                        help="Label für einen bestehenden Lauf aus backend/db/briefings (uploaded_by-Filter über --store-uploaded-by)")
    parser.add_argument("--store-uploaded-by", default="UEGL00")
    parser.add_argument("--out", type=Path, default=Path("docs/beispiele/modellvergleich"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.zip) as z:
        entries = [(n, z.read(n)) for n in sorted(z.namelist()) if not n.endswith("/")]
    print(f"{len(entries)} Dateien aus {args.zip}")

    if args.from_store:
        print(f"\n[{args.from_store}] aus lokalem Store (uploaded_by={args.store_uploaded_by}, keine LLM-Calls)")
        _write(_from_store(args.store_uploaded_by), args.from_store, args.out)

    if args.model:
        api_key = get_openrouter_key()
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY fehlt")
        for model in args.model:
            print(f"\n[{model}]")
            records = asyncio.run(_run_model(model, entries, api_key))
            _write(records, model, args.out)


if __name__ == "__main__":
    main()
