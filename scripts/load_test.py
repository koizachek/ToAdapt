"""Lasttest für den ToAdapt-Studierenden-Flow (Rollout-Gate W1).

Simuliert N Studierende, die parallel den vollen Zyklus durchlaufen
(Session anlegen → Chat-Turns → Antworten speichern → Submit mit
Judge-Bewertung) plus M Tutor:innen, die das Gruppen-Dashboard abrufen.
Gemessen werden p50/p95/p99-Latenzen pro Operation, 429-/5xx-Raten und die
Gate-Schwellen aus ROLLOUT_CHECKLIST.md W1 (Chat p95 < 10 s, Submit < 30 s,
keine 5xx).

NUR gegen Staging/Lokal mit LLM-Stub fahren — niemals gegen Produktion.

ACHTUNG Mongo-Isolation (real passierte Falle, 2026-07-10): Das Backend lädt
seine .env über den MODULPFAD (load_dotenv/find_dotenv), nicht über das
Arbeitsverzeichnis — ein "isoliert" gestartetes Backend verbindet sich also
trotzdem mit der Produktions-Mongo aus der Repo-.env. Für den Lasttest die
Mongo-Variablen deshalb EXPLIZIT überschreiben: entweder ganz aus
(MONGODB_MAS_NAME='' MONGODB_MAS_KEY='' MONGODB_HOST='' MONGODB_URI='')
oder auf die Staging-DB (MONGODB_DATABASE=toadapt_staging).

    # Terminal 1: Stub
    .venv/bin/python -m uvicorn scripts.llm_stub:app --port 9500
    # Terminal 2: Backend (Staging-Konfiguration, Mongo explizit isoliert!)
    MONGODB_MAS_NAME='' MONGODB_MAS_KEY='' MONGODB_HOST='' MONGODB_URI='' \
    OPENROUTER_BASE_URL=http://127.0.0.1:9500/v1 OPENROUTER_API_KEY=stub \
    GROUP_CODE_MAX=360 TOADAPT_API_KEY=<key> PSEUDONYM_SECRET=staging \
    .venv/bin/python -m uvicorn backend.main:app --proxy-headers --port 8000
    # Terminal 3: Lasttest
    .venv/bin/python scripts/load_test.py --base-url http://127.0.0.1:8000 \
        --students 300 --tutors 40 --turns 5 --api-key <key> --report report.md

Denkpausen (--think-min/--think-max) realistisch halten: Die LLM-Kapazität
ist LLM_MAX_CONCURRENCY / Antwortzeit (Default 16 / ~1,2 s ≈ 13 Calls/s).
Liegt die erzeugte Chat-Rate darüber, misst der Test nur die Warteschlange —
reale Studierende denken zwischen Turns Minuten, nicht Sekunden.

Rate-Limit-Hinweis: Session-/Submission-Erstellung ist pro Client-IP auf
20/min begrenzt. Reale Studierende haben eigene IPs; der Lastgenerator hat
eine. Darum spooft --spoof-ips (Default: an) pro virtuellem Studierenden
eine X-Forwarded-For-Adresse — das Backend muss dafür mit --proxy-headers
laufen (auf Railway ohnehin der Fall). Gegen Remote-Staging, das gespoofte
Header verwirft, stattdessen --ramp-seconds erhöhen.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

ANSWER_TEXT = (
    "Wir sehen die zentrale Herausforderung darin, dass die bestehenden "
    "Staerken des Unternehmens und die neuen Anforderungen des Marktes "
    "auseinanderlaufen. Aus den Zahlen im Case leiten wir ab, dass der "
    "wichtigste Kanal weiterhin profitabel ist, waehrend die digitalen "
    "Kanaele hinter dem Branchendurchschnitt zurueckbleiben. Unsere "
    "Entscheidung stuetzt sich auf drei Belege aus dem Text: die "
    "Entwicklung des Gewinns pro Kundin, die Einschaetzung des Managements "
    "und die Grobeinschaetzung der Anwendungsfaelle. Daraus folgt fuer uns, "
    "dass das Unternehmen zuerst intern Kompetenzen aufbauen sollte, bevor "
    "es nach aussen sichtbar wird. Den Zielkonflikt zwischen Geschwindigkeit "
    "und Sorgfalt gehen wir bewusst ein, weil ein Vertrauensverlust bei der "
    "Kernkundschaft schwerer wiegt als ein spaeterer Markteintritt. Als "
    "Kennzahl schlagen wir die Bearbeitungszeit pro Anfrage vor, weil sie "
    "den Effekt direkt misst und frueh Rueckmeldung gibt."
)


@dataclass
class Metrics:
    """Sammelt (Operation, HTTP-Status, Dauer) über alle virtuellen Nutzer."""
    samples: list[tuple[str, int, float]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def record(self, op: str, status: int, seconds: float) -> None:
        async with self.lock:
            self.samples.append((op, status, seconds))


def percentile(values: list[float], pct: float) -> float:
    """p-Quantil (nearest-rank) — leer ⇒ 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[rank]


def summarize(samples: list[tuple[str, int, float]]) -> dict[str, dict]:
    """Aggregiert pro Operation: Anzahl, ok/429/4xx/5xx, p50/p95/p99/max."""
    by_op: dict[str, dict] = {}
    for op, status, seconds in samples:
        entry = by_op.setdefault(op, {"n": 0, "ok": 0, "s429": 0, "s4xx": 0, "s5xx": 0, "lat": []})
        entry["n"] += 1
        if status == 429:
            entry["s429"] += 1
        elif 200 <= status < 300:
            entry["ok"] += 1
            entry["lat"].append(seconds)
        elif status >= 500 or status == 0:
            entry["s5xx"] += 1
        else:
            entry["s4xx"] += 1
    for entry in by_op.values():
        lat = entry.pop("lat")
        entry["p50"] = percentile(lat, 50)
        entry["p95"] = percentile(lat, 95)
        entry["p99"] = percentile(lat, 99)
        entry["max"] = max(lat) if lat else 0.0
    return by_op


def spoofed_ip(index: int) -> str:
    """Eindeutige, dokumentationsreservierte Test-IP pro virtuellem Nutzer."""
    return f"10.42.{(index // 250) % 250}.{index % 250 + 1}"


async def _call(
    client: httpx.AsyncClient, metrics: Metrics, op: str, method: str, url: str, **kwargs,
) -> httpx.Response | None:
    start = time.monotonic()
    try:
        response = await client.request(method, url, **kwargs)
    except httpx.HTTPError:
        await metrics.record(op, 0, time.monotonic() - start)
        return None
    await metrics.record(op, response.status_code, time.monotonic() - start)
    return response


async def student_journey(
    index: int, args: argparse.Namespace, client: httpx.AsyncClient,
    metrics: Metrics, questions: list[str], start_delay: float,
) -> None:
    await asyncio.sleep(start_delay)
    headers = {}
    if args.spoof_ips:
        headers["X-Forwarded-For"] = spoofed_ip(index)
    if args.student_access_code:
        headers["X-Student-Access-Code"] = args.student_access_code

    group = f"G{index % args.group_max + 1}"
    user = f"lasttest-{index:04d}"

    session_response = await _call(
        client, metrics, "create_session", "POST", "/sessions",
        json={"user_id": user, "group_code": group, "case_id": args.case_id},
        headers=headers,
    )
    if session_response is None or session_response.status_code != 201:
        return
    session_id = session_response.json()["session_id"]

    submission_response = await _call(
        client, metrics, "create_submission", "POST", "/submissions",
        json={
            "user_id": user, "matrikelnummer": f"00-{index:03d}-000",
            "group_code": group, "case_id": args.case_id, "target_tp": 1,
        },
        headers=headers,
    )
    if submission_response is None or submission_response.status_code != 201:
        return
    submission_id = submission_response.json()["submission_id"]

    history: list[dict] = []
    for turn in range(args.turns):
        message = f"Wie haengt Beobachtung {turn + 1} mit der Kernfrage des Falls zusammen?"
        chat_response = await _call(
            client, metrics, "chat", "POST", f"/sessions/{session_id}/chat",
            json={"content": message, "history": history[-10:]}, headers=headers,
        )
        if chat_response is not None and chat_response.status_code == 200:
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": chat_response.json()["content"]})
        # Lesende/denkende Pause zwischen Turns (gestaucht, aber > 0,
        # damit die Chat-Rate pro Session realistisch bleibt).
        await asyncio.sleep(random.uniform(*args.think_seconds))

    for question_id in questions:
        await _call(
            client, metrics, "save_answer", "POST",
            f"/submissions/{submission_id}/answer",
            json={"question_id": question_id, "answer_text": f"{ANSWER_TEXT} ({user})"},
            headers=headers,
        )

    if args.submit:
        await _call(
            client, metrics, "submit", "POST",
            f"/submissions/{submission_id}/submit", headers=headers,
            timeout=httpx.Timeout(120.0),
        )


async def tutor_journey(
    index: int, args: argparse.Namespace, client: httpx.AsyncClient,
    metrics: Metrics, duration: float,
) -> None:
    headers = {"X-API-Key": args.api_key}
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        groups_response = await _call(
            client, metrics, "dashboard_groups", "GET", "/dashboard/groups", headers=headers,
        )
        if groups_response is not None and groups_response.status_code == 200:
            groups = groups_response.json()
            if groups:
                code = groups[(index + len(groups) // 2) % len(groups)]["group_code"]
                await _call(
                    client, metrics, "dashboard_group_detail", "GET",
                    f"/dashboard/groups/{code}", headers=headers,
                )
        await asyncio.sleep(random.uniform(3.0, 8.0))


def render_report(args, by_op, wall_seconds: float) -> str:
    lines = [
        "# Lasttest-Protokoll (Rollout-Gate W1)",
        "",
        f"Zeitpunkt (UTC): {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Ziel: {args.base_url} · Studierende: {args.students} · Tutor:innen: {args.tutors}"
        f" · Chat-Turns: {args.turns} · Ramp: {args.ramp_seconds}s · Dauer: {wall_seconds:.0f}s",
        "",
        "| Operation | n | ok | 429 | 4xx | 5xx | p50 s | p95 s | p99 s | max s |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for op in sorted(by_op):
        e = by_op[op]
        lines.append(
            f"| {op} | {e['n']} | {e['ok']} | {e['s429']} | {e['s4xx']} | {e['s5xx']} "
            f"| {e['p50']:.2f} | {e['p95']:.2f} | {e['p99']:.2f} | {e['max']:.2f} |"
        )

    chat_p95 = by_op.get("chat", {}).get("p95", 0.0)
    submit_p95 = by_op.get("submit", {}).get("p95", 0.0)
    total_5xx = sum(e["s5xx"] for e in by_op.values())
    gates = [
        ("Chat p95 < 10 s", chat_p95 < 10.0, f"{chat_p95:.2f} s"),
        ("Submit p95 < 30 s", submit_p95 < 30.0, f"{submit_p95:.2f} s"),
        ("Keine 5xx", total_5xx == 0, f"{total_5xx}"),
    ]
    lines += ["", "## GATE W1"]
    for name, passed, value in gates:
        lines.append(f"- {'PASS' if passed else 'FAIL'}: {name} (gemessen: {value})")
    return "\n".join(lines) + "\n"


async def run(args: argparse.Namespace) -> int:
    limits = httpx.Limits(max_connections=args.students + args.tutors + 10)
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=httpx.Timeout(60.0), limits=limits,
    ) as client:
        health = await client.get("/health")
        health.raise_for_status()

        case = await client.get(f"/admin/cases/{args.case_id}")
        case.raise_for_status()
        questions = [q["question_id"] for q in case.json().get("questions", [])]
        if not questions:
            print(f"Case {args.case_id} hat keine Fragen — Abbruch.", file=sys.stderr)
            return 2

        metrics = Metrics()
        start = time.monotonic()
        tasks = [
            asyncio.create_task(student_journey(
                i, args, client, metrics, questions,
                start_delay=(i / max(1, args.students)) * args.ramp_seconds,
            ))
            for i in range(args.students)
        ]
        if args.api_key and args.tutors:
            # Tutor:innen laufen, solange voraussichtlich Studierendenlast anliegt.
            tutor_duration = args.ramp_seconds + args.turns * (args.think_seconds[1] + 8) + 30
            tasks += [
                asyncio.create_task(tutor_journey(i, args, client, metrics, tutor_duration))
                for i in range(args.tutors)
            ]
        await asyncio.gather(*tasks)
        wall_seconds = time.monotonic() - start

    by_op = summarize(metrics.samples)
    report = render_report(args, by_op, wall_seconds)
    print(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            handle.write(report)
        print(f"Protokoll geschrieben: {args.report}")

    return 0 if all(line_ok for line_ok in [
        by_op.get("chat", {}).get("p95", 0.0) < 10.0,
        by_op.get("submit", {}).get("p95", 0.0) < 30.0,
        sum(e["s5xx"] for e in by_op.values()) == 0,
    ]) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--students", type=int, default=300)
    parser.add_argument("--tutors", type=int, default=40)
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--case-id", default="alpes-bank-genai-001")
    parser.add_argument("--api-key", default="", help="TOADAPT_API_KEY für den Tutor-Teil (leer = ohne Tutor:innen)")
    parser.add_argument("--student-access-code", default="")
    parser.add_argument("--group-max", type=int, default=360)
    parser.add_argument("--ramp-seconds", type=float, default=60.0,
                        help="Zeitraum, über den die Studierenden-Starts verteilt werden")
    parser.add_argument("--think-min", dest="think_min", type=float, default=2.0)
    parser.add_argument("--think-max", dest="think_max", type=float, default=6.0)
    parser.add_argument("--no-submit", dest="submit", action="store_false",
                        help="Submit/Judge-Teil überspringen (nur Chat-Last)")
    parser.add_argument("--no-spoof-ips", dest="spoof_ips", action="store_false",
                        help="Kein X-Forwarded-For pro Nutzer (Rate-Limits greifen dann pro Generator-IP)")
    parser.add_argument("--report", default="", help="Markdown-Protokoll in diese Datei schreiben")
    args = parser.parse_args(argv)
    args.think_seconds = (args.think_min, args.think_max)
    return args


if __name__ == "__main__":
    sys.exit(asyncio.run(run(parse_args())))
