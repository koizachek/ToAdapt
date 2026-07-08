---
name: toadapt-validation-and-qa
description: >
  Validierung und Qualitätssicherung im ToAdapt-Repo: Was als Evidenz für eine
  Änderung zählt (CI < Smoke < Guardrail-Regression < Teacher-Alignment),
  Landkarte aller pytest-Tests, das Golden-Case-Inventar (alpes-bank-genai-001
  + Rubric-JSONs als kalibrierte Artefakte), Copy-Paste-Muster zum Ergänzen
  neuer Tests, CI-Anatomie inkl. PYTHONPATH-Falle, Akzeptanz-Schwellen.
  Lade diese Skill, wenn du: (a) vor einem Commit/Push wissen willst, welche
  Prüfungen Pflicht sind und wie man sie lokal ausführt; (b) einen neuen Test
  schreiben willst (TestClient, Mongo-Env wegräumen, LLM mocken, Stores auf
  tmp_path patchen); (c) den Judge/Evaluator/Prompts geändert hast und wissen
  musst, welcher Nachweis akzeptiert wird; (d) Tests fehlschlagen (z. B.
  ModuleNotFoundError backend, 2-Sekunden-Hänger, 48-Tests-Baseline verletzt);
  (e) den Golden Case oder eine Rubric-JSON anfassen willst; (f) fragst
  "reicht dieser Beweis?" oder "welcher Test deckt X ab?". Keywords: pytest,
  ruff, CI, ci.yml, TestClient, monkeypatch, Golden Case, Rubric, Alignment,
  Pearson, MAE, Evidenz, Regression, QA, Testabdeckung.
---

# ToAdapt — Validation & QA

Diese Skill definiert, was in diesem Repo als **Beweis** gilt, dass eine
Änderung funktioniert — und wie man diesen Beweis erbringt.

## Wann diese Skill NICHT gilt

| Deine Frage | Richtige Skill |
|---|---|
| "Darf ich das überhaupt ändern? Welches Gate gilt?" | `toadapt-change-control` |
| "Warum schlägt X in Produktion fehl?" (401/503/429/Mongo/CORS) | `toadapt-debugging-playbook` |
| "Wie starte ich Backend/Frontend lokal, wie deploye ich?" | `toadapt-run-and-operate` |
| "Wie baue ich die Umgebung (venv, npm) von Null auf?" | `toadapt-build-and-env` |
| "Was bedeutet Bloom/TP/Canvas/Scaffolding fachlich?" | `bwl-scaffolding-reference` |
| "Wie messe ich Laufzeitverhalten (Diagnostics, Logs)?" | `toadapt-diagnostics-and-tooling` |
| "Wie verbessere ich konkret das q4-Judge-Alignment?" | `toadapt-judge-alignment-campaign` |
| "Welche Env-Variable steuert was?" | `toadapt-config-and-flags` |

---

## 1. Evidenz-Staffelung: Was zählt als Beweis?

Von schwach nach stark. Wähle die Stufe nach dem, was du geändert hast —
NICHT nach dem, was am bequemsten ist.

| Stufe | Evidenz | Reicht für |
|---|---|---|
| 1 | **CI grün** (ruff + pytest; eslint + tsc + next build) | Refactorings ohne Verhaltensänderung, Doku, Tests selbst |
| 2 | **Lokaler Smoke-Test** (Backend starten, Endpoint real anfragen) | API-Routen-Änderungen, Auth-/Rate-Limit-Änderungen, neue Endpoints |
| 3 | **Guardrail-Regressionstests** (gezielte pytest-Fälle für neue verbotene/erlaubte Muster) | Änderungen an `backend/agents/orchestrator.py` (Guardrails, Prompts, Routing) und am Feedback-Sanitizing des Evaluators |
| 4 | **Teacher-Alignment-Metriken** (Vergleichs-Pipeline gegen Lehrkraft-Scores, siehe §6) | JEDE Änderung an `EVALUATOR_SYSTEM`, `EVALUATE_PROMPT`, den Kalibrierungsankern oder den Rubric-JSONs |

Harte Regeln:

- **"Sieht besser aus" zählt NIE als Evidenz für Judge-Änderungen.** Für den
  LLM-Judge (der Rubric-Evaluator, der Studierenden-Antworten bepunktet) sind
  Alignment-Metriken (Pearson, MAE gegen Lehrkraft-Bewertungen) die EINZIGE
  akzeptierte Evidenz. Einzelbeispiele anschauen ist Exploration, kein Beweis.
- Jede höhere Stufe setzt die niedrigeren voraus (Alignment-Nachweis ersetzt
  keine grüne CI).
- Die Entscheidung, WELCHE Stufe eine konkrete Änderung verlangt, trifft
  `toadapt-change-control` — diese Skill beschreibt, WIE man die Stufe erfüllt.

### Stufe 1+2 lokal ausführen (Kommandos, vom Repo-Root)

```bash
cd /Users/dianakozachek/ToAdapt   # Repo-Root; Pfade darunter sind repo-relativ

# Backend-Lint (ruff liegt NICHT im .venv — global installiert, Stand 2026-07-08)
ruff check .

# Backend-Tests — IMMER via `python -m pytest` (siehe PYTHONPATH-Falle, §7)
.venv/bin/python -m pytest tests/ -q
# Erwartung (Stand 2026-07-08): "48 passed"

# Frontend
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

Minimaler Smoke-Test (kein LLM-Key nötig für /health):

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8000 &
curl -s http://localhost:8000/health   # erwartet {"status":"ok",...}
```

Für vollständige Start-Anleitung (Env-Variablen, Frontend-Kopplung, Mongo):
`toadapt-run-and-operate`.

---

## 2. Test-Landkarte (Stand: 2026-07-08, 48 Tests)

Alle Tests liegen flach in `tests/` (kein `conftest.py`, kein `__init__.py`).
Konfiguration in `pyproject.toml`: `asyncio_mode = "auto"` (async-Tests
brauchen keinen Decorator), `testpaths = ["tests"]`.

| Datei | # | Deckt ab |
|---|---:|---|
| `tests/test_skeleton.py` | 7 | `/health` minimal (keine Infra-Details im Body), `/health/diagnostics` + `/dashboard/overview` fail-closed ohne Key, Session-Erstellung gegen den Golden Case, `current_tp_phase()`-Fensterlogik (TP-Phase aus Datum) |
| `tests/test_phase1_hardening.py` | 9 | Studenten-Zugangscode (`STUDENT_ACCESS_CODE` offen/erzwungen), Rate-Limiter (429 + Retry-After, Keying per Path-Param), Session-/Dashboard-Store-Fallbacks ohne Mongo, geteilter OpenRouter-HTTP-Client, LLM-Concurrency-Semaphore |
| `tests/test_case_editor.py` | 13 | Case-Validator (Framework-Namen-Verbot, NORDIC-HOME-Sperre, Bloom-Coverage-Warnung), PATCH-Editor (Revision-Bump, Draft-Reset), Approve-Gate (422 + `force`-Override), Retire, Teil-Regenerierung mit gemocktem LLM, JSON-Fence-Stripping |
| `tests/test_orchestrator_guardrails.py` | 3 | `guardrail_check()`: blockt direkte Use-Case-Empfehlung, Case-Spekulation (FINMA/Azure), Slang + Emoji |
| `tests/test_rubric_evaluator.py` | 7 | JSON-Extraktion (plain/fenced/umschlossen), Feedback-Sanitizing (Antwort-Templates raus), Canvas-Rationale-Sanitizing, `technical_fallback`-Payload (0 Punkte, `needs_human_review`), Totals-Neuberechnung aus Scores |
| `tests/test_rubric_loader.py` | 1 | Golden Case → alle 4 Rubrics ladbar, `required_canvas_blocks` pro q1–q4 korrekt verkettet |
| `tests/test_submission_store.py` | 1 | Submission-Recovery aus Store in den In-Memory-Cache (`routes._get_submission`) |
| `tests/test_dashboard_difficulties.py` | 3 | `/dashboard/difficulties`: API-Key-Pflicht, Priorisierung schwacher Studierender (attention_level, weak_objectives, Penalty-Aggregation case-insensitiv), Kohorten-Aggregation — mit **synthetischen** Submissions im tmp-Dateistore |
| `tests/test_export_review_workbooks.py` | 1 | Forschungs-Skript: Rubric-/Blind-/Chat-Workbooks (Blind-Sheet ohne Judge-Scores — Grundlage der Alignment-Studie) |
| `tests/test_compare_teacher_rubric_scores.py` | 1 | Forschungs-Skript: Lehrer-Workbook ist kanonischer Scope, rubric-only-Zeilen by design ausgeschlossen |
| `tests/test_import_prolific_runs.py` | 1 | Forschungs-Skript: Rohdaten-Import + SHA-256-Manifest, ignoriert `.DS_Store` |
| `tests/test_publish_dashboard_scores.py` | 1 | Forschungs-Skript: publiziert nur `status=="evaluated"` mit Scores, zählt Fallbacks/Review-Flags |

### Was NICHT abgedeckt ist (ehrlich)

- **Keine echten LLM-Pfade.** Chat (`POST /sessions/{id}/chat`),
  Case-Generierung und die eigentliche LLM-Evaluation laufen in Tests nur
  gemockt oder gar nicht. Ob ein Prompt gute Antworten produziert, beweist
  KEIN Test — dafür gibt es nur Stufe 4 (Alignment) bzw. manuelle Smokes.
- **Kein E2E-Test** (Frontend→Backend durchgeklickt). Frontend-CI prüft nur
  Lint/Typen/Build.
- **Kein Load-Test.** Rate-Limiter ist unit-getestet, Verhalten unter
  echter Parallellast (Railway, mehrere Worker) ist unbelegt.
- **Kein Mongo-Integrationstest** — alle Tests laufen bewusst OHNE Mongo
  (Datei-/No-op-Fallback). Mongo-Verhalten wird nur in Produktion via
  `/health/diagnostics` beobachtet (→ `toadapt-diagnostics-and-tooling`).
- `retry_technical_fallback_scores.py` ist das einzige Skript ohne Test —
  es macht echte LLM-Calls (nur mit `--dry-run` gefahrlos).

---

## 3. Golden-Inventar: Fixtures mit eigener Gate-Stufe

### Der Golden Case: `alpes-bank-genai-001`

Der EINZIGE kuratierte, freigegebene Case im Pool (`backend/cases/pool/`),
Stand 2026-07-08. Vier Dateien gehören zusammen:

| Datei | Rolle |
|---|---|
| `backend/cases/pool/alpes-bank-genai-001.json` | Deutscher Case: Sections, Exhibits, q1–q4 |
| `backend/cases/pool/alpes-bank-genai-001-en.json` | Englische Variante (Suffix `-en` schaltet EN-Agenten-Prompts) |
| `backend/cases/pool/alpes-bank-genai-001-agent.json` | Agent-Guidance (key_tensions, common_mistakes → fließen in Agenten-Prompts) |
| `backend/cases/pool/alpes-bank-genai-001-en-agent.json` | dito EN |

Fragenstruktur (Fixture-Anker — Tests und Kalibrierung hängen daran):

| Frage | Bloom | max_points | rubric_reference |
|---|---:|---:|---|
| q1 | 4 | 25 | tp1_rubric.json |
| q2 | 5 | 24 | tp2_rubric.json |
| q3 | 4 | 22 | tp3_rubric.json |
| q4 | 6 | 30 | tp4_rubric.json |

**Warum eigene Gate-Stufe:** Eine Änderung an diesem Case ist gleichzeitig
(a) eine Fixture-Änderung — `tests/test_rubric_loader.py` (asserted konkrete
Canvas-Blöcke pro Frage), `tests/test_skeleton.py` und
`tests/test_submission_store.py` referenzieren die case_id hart —, (b) eine
**studierendensichtbare Verhaltensänderung** (der Case IST das Produkt) und
(c) potenziell eine Kalibrierungs-Invalidierung (siehe unten). Zusätzlich ist
das Glossar pro Case im Frontend hartkodiert
(`CASE_GLOSSARY["alpes-bank-genai-001"]` in `frontend/app/cases/[id]/page.tsx`)
— Case-Inhalt und Glossar können auseinanderlaufen. Vor jeder Änderung:
`toadapt-change-control` laden.

### Die 4 Rubric-JSONs sind KALIBRIERTE Artefakte

`backend/config/rubrics/tp{1..4}_rubric.json` enthalten pro Frage
`evaluation_focus` (worauf der Judge achtet) und `required_canvas_blocks`
(Business-Model-Canvas-Blöcke mit `accepted_keywords` und `weight`), plus
Schwellen (`exemplar_threshold_pct`/`score_floor_pct`: 80/75, 82/75, 80/72,
82/75 für tp1–tp4).

**Entscheidend:** Die Kalibrierungsanker des Evaluators
(`_format_calibration_notes` in `backend/evaluator/rubric_evaluator.py`,
Zeile ~155) sind HARTKODIERT auf `question_id` q1–q4 und inhaltlich auf
GENAU DIESEN Case gemünzt ("drei definierte Use Cases", Make-or-Buy-Faktoren
etc.). Sie sind das Ergebnis der Teacher-Alignment-Studie (§6). Konsequenzen:

1. Rubric-JSON oder Case-Fragen ändern → Kalibrierung potenziell hinfällig →
   Stufe-4-Evidenz nötig.
2. Ein NEUER Case bekommt die Anker NICHT automatisch — seine q1–q4 erben
   Anker, die für einen anderen Case formuliert wurden. Das ist eine bekannte
   Design-Schwäche, kein Feature.

---

## 4. Tests ergänzen — die hiesigen Muster (Copy-Paste)

Neue Tests: Datei `tests/test_<thema>.py`, Funktionen `test_*`. Async-Tests
einfach als `async def` schreiben (`asyncio_mode = "auto"`). Keine echten
LLM-Calls, keine echten Teilnehmerdaten — immer synthetische Daten.

### Muster A: API-Test mit TestClient + sauberer Env

**Die wichtigste Regel: MONGODB_\*-Variablen IMMER wegräumen.** Die Stores
verbinden sich sonst real (`backend/db/mongo.py` baut die URI aus
`MONGODB_URI` ODER `MONGODB_MAS_NAME`+`MONGODB_MAS_KEY`+`MONGODB_HOST`/
`_CLUSTER_HOST`/`_CLUSTER`; `MongoClient(..., serverSelectionTimeoutMS=2000)`)
— Folge: 2-Sekunden-Stall pro Zugriff oder, schlimmer, Schreiben in eine
echte Datenbank, falls lokal eine `.env` geladen wurde.

```python
import pytest
from fastapi.testclient import TestClient
from backend.main import app

API_KEY = "test-admin-key"

@pytest.fixture()
def client(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)  # sonst 401 im Studenten-Flow
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)            # sonst 503 auf Admin-Routen (fail-closed)
    return TestClient(app)

def test_example(client):
    res = client.get("/dashboard/overview", headers={"X-API-Key": API_KEY})
    assert res.status_code == 200
```

Vorlage im Repo: `tests/test_case_editor.py` (Fixture `env`).

### Muster B: Datei-Stores auf tmp_path isolieren

Die Datei-Fallback-Stores schreiben sonst in den Working Tree
(`backend/cases/pool/`, `backend/db/submissions/`). Modul-Konstanten patchen:

```python
import backend.cases.manager as manager_module
import backend.db.dashboard_store as dashboard_store_module

monkeypatch.setattr(manager_module, "POOL_DIR", tmp_path)            # Case-Pool
monkeypatch.setattr(dashboard_store_module, "RESULTS_DIR", tmp_path) # Dashboard-Ergebnisse
```

(Analog existiert `RUNTIME_SUBMISSIONS_DIR` in `backend/db/submission_store.py`.)

### Muster C: LLM mocken

Genau EIN Interceptions-Punkt: `OpenRouterClient.complete`. Signatur ist
keyword-only — exakt so übernehmen:

```python
monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")  # Konstruktor wirft sonst ValueError

async def fake_complete(self, *, system, messages, max_tokens):
    return '{"section_id": "s1", "title": "Neuer Titel", "content": "Neuer Inhalt."}'

monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)
```

Vorlage: `tests/test_case_editor.py::test_regenerate_section_replaces_content`.

### Muster D: Synthetische Submissions für Dashboard-/Aggregations-Tests

Ergebnis-JSONs direkt in den (auf `tmp_path` gepatchten) Dateistore legen —
mit erfundenen Matrikelnummern, nie mit echten Daten:

```python
(tmp_path / "r0.json").write_text(json.dumps({
    "submission_id": "sub-1001-38.0", "matrikelnummer": "1001",
    "case_id": "case-1", "target_tp": 1, "percentage": 38.0,
    "evaluated_at": "2026-07-01T10:00:00",
    "scores": [{"question_id": "q1", "bloom_level": 4, "max_points": 8,
                "awarded_points": 2, "feedback": "…",
                "learning_objective_tags": ["wirkungskette"],
                "main_penalties": [], "missing_canvas_blocks": [],
                "needs_human_review": False, "evaluation_status": "ok"}],
}), encoding="utf-8")
```

Vorlage: `tests/test_dashboard_difficulties.py`.

### Muster E: scripts/ testen (kein Package)

`scripts/*.py` sind keine importierbaren Module — per `importlib` laden:

```python
import importlib.util, sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "mein_skript.py"
SPEC = importlib.util.spec_from_file_location("mein_skript", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
```

Vorlage: `tests/test_publish_dashboard_scores.py`.

### Guardrail-Regressionstests (Stufe 3)

Wenn du Guardrail-Patterns oder Agenten-Prompts änderst: Für JEDES neue
verbotene Muster einen Fall in `tests/test_orchestrator_guardrails.py`
ergänzen (und einen Positivfall, der NICHT blocken darf):

```python
from backend.agents.orchestrator import guardrail_check

def test_guardrail_blocks_neues_muster():
    ok, reason = guardrail_check("<verbotener Beispieltext>", 2)  # 2 = TP-Phase
    assert ok is False
```

Achtung, bekannte Lücke: `TP_CONFIGS[4]` hat keinen
`forbidden_framework_names`-Key — in TP4 greifen nur die globalen Patterns.
Tests für TP-spezifische Verbote also mit tp 1–3 schreiben oder die Lücke
bewusst adressieren (dann: `toadapt-change-control`).

---

## 5. CI-Anatomie (`.github/workflows/ci.yml`, Stand 2026-07-08)

Läuft bei jedem Push auf `main` und bei Pull Requests. Zwei Jobs:

| Job | Umgebung | Schritte |
|---|---|---|
| backend | Python 3.11 (Prod-Version; lokal läuft 3.13) | `pip install -r requirements.txt pytest pytest-asyncio ruff` → `ruff check .` → `pytest tests/ -q` mit `PYTHONPATH: .` |
| frontend | Node 22, cwd `frontend/` | `npm ci` → `npm run lint` (eslint) → `npx tsc --noEmit` → `npm run build` |

Wissenswert:

- **pytest/pytest-asyncio/ruff sind dev-only** — bewusst NICHT in
  `requirements.txt` (die ist die Prod-Dependency-Liste für Railway). CI
  installiert sie explizit dazu. Neue Test-Dependencies müssen in die
  CI-Install-Zeile, nicht in requirements.txt.
- **Die PYTHONPATH-Falle:** `tests/` hat kein `__init__.py` und es gibt kein
  `conftest.py` im Root — ein nacktes `pytest tests/ -q` findet das Package
  `backend` NICHT (8 Collection-Errors, lokal am 2026-07-08 reproduziert).
  Zwei funktionierende Varianten: `python -m pytest tests/ -q` vom Repo-Root
  (fügt CWD zu sys.path hinzu) oder `PYTHONPATH=. pytest tests/ -q` (so
  macht es CI). Wenn CI-pytest scheitert, lokal aber läuft: zuerst prüfen,
  ob der `env: PYTHONPATH: .`-Block im Workflow noch da ist.
- Ruff-Konfig in `pyproject.toml`: line-length 100, target py311, und
  absichtliche `E402`-Ignores für `backend/main.py` und
  `backend/db/submission_store.py` (dort MUSS `load_dotenv()` vor den
  Imports laufen — Hintergrund: `toadapt-failure-archaeology`). Diese
  Ignores nicht "aufräumen".
- CI ersetzt keine Stufe-2–4-Evidenz: sie startet keinen Server, ruft kein
  LLM und misst kein Alignment.

---

## 6. Akzeptanz-Schwellen

### Test-Baseline

- **48 Tests grün ist die Basis (Stand 2026-07-08) — nie unterschreiten.**
  Tests dürfen nur ersetzt/entfernt werden, wenn das getestete Feature selbst
  entfernt wird (dann: `toadapt-change-control`). Neue Features ohne neuen
  Test sind ein Review-Smell.
- `ruff check .` und Frontend-Lint/tsc/build müssen sauber sein, bevor
  gepusht wird — CI läuft auf jedem Push auf main (Solo-Workflow, keine
  PR-Pflicht, d. h. rote CI landet sonst direkt "in Produktion").

### Alignment-Bar (für Judge-/Rubric-/Prompt-Änderungen, Stufe 4)

**ACHTUNG Scope-Differenz:** Es gibt ZWEI Baseline-Zahlensätze für dieselbe
Studie. Der Report (`docs/teacher_alignment_report_20260531_17submissions.md`;
Dateiname sagt 17, Scope sind 16 Submissions / **64** Frage-Zeilen) nennt
r 0.796 / MAE 2.711 / RMSE 3.897 / Mean Diff −2.07 — aber sein 64er-Filter
existiert NICHT als Skript im Repo (ad-hoc, nicht reproduzierbar). Die
unten stehende Pipeline rechnet über alle **67** gematchten Lehrer-Zeilen
und liefert für den UNVERÄNDERTEN Judge r 0.777 / MAE 2.784 / RMSE 3.921 /
Mean Diff −1.784 (am 2026-07-08 real reproduziert, siehe
`toadapt-judge-alignment-campaign` §2 — dort ist auch das exakte GATE).
**Maßgeblich für den Vergleich ist die reproduzierbare 67er-Skript-Baseline**;
wer die 64er-Report-Werte als Bar nimmt, lehnt eine neutrale Änderung
fälschlich als "Verschlechterung" ab. q4 ist in beiden Scopes deckungsgleich.

| Metrik | 67er-Skript-Baseline (kalibrierter Judge) | Bar für jede neue Judge-Version |
|---|---:|---|
| Pearson r (gesamt) | 0.777 | **≥ 0.78 halten** (Gate der Kampagne) — keine Verschlechterung akzeptieren |
| MAE (Punkte, gesamt) | 2.784 | **nicht verschlechtern** |
| RMSE (Punkte) | 3.921 | nicht verschlechtern (sekundär) |
| Mean Diff Judge−Teacher | −1.784 (Judge systematisch strenger) | nicht weiter ins Negative |
| q4 (Bloom 6): MAE | 4.969 (in beiden Scopes identisch), systematische Unterbewertung | Zielwerte und Vorgehen: `toadapt-judge-alignment-campaign` |

Pipeline, um die Metriken für eine geänderte Judge-Version zu erzeugen
(Details und Datenherkunft: `toadapt-run-and-operate`; NIE mit echten
Teilnehmerdaten im Repo arbeiten — die liegen unter `~/ToAdapt_sensitive_data/`
und bleiben dort):

```bash
# 1) Judge-Scores als Workbooks exportieren (liest Submissions/Events-JSON)
python scripts/export_review_workbooks.py \
  --submissions <submission_states.json> --events <experiment_events.json> \
  --cases-dir backend/cases/pool --output-dir <out> --prefix review

# 2) Gegen das ausgefüllte Lehrkraft-Blind-Workbook vergleichen
python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook <teacher.xlsx> --rubric-workbook <out>/review_*_rubric.xlsx \
  --output-dir <out>
# → Excel mit summary-Blatt (Pearson, MAE, RMSE, within_2pt, …) + CSV
```

Das Lehrer-Workbook ist der kanonische Scope: Zeilen, die nur der Judge
bewertet hat, werden by design ausgeschlossen (getestet in
`tests/test_compare_teacher_rubric_scores.py`).

Deploy einer Judge-Änderung OHNE diesen Durchlauf verstößt gegen die
Projekt-Doktrin — siehe `toadapt-change-control`.

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle Fakten am 2026-07-08 gegen das Repo verifiziert
(48/48 Tests lokal grün, ruff sauber, PYTHONPATH-Falle reproduziert).

Re-Verifikation drift-anfälliger Fakten (je ein Kommando, vom Repo-Root):

| Fakt | Kommando |
|---|---|
| Testanzahl (Baseline 48) | `.venv/bin/python -m pytest tests/ -q \| tail -1` |
| Test-Dateiliste | `ls tests/test_*.py` |
| CI-Schritte + PYTHONPATH-Env | `cat .github/workflows/ci.yml` |
| Golden Case einziger Pool-Inhalt | `ls backend/cases/pool/` |
| q1–q4 Bloom/Punkte des Golden Case | `python3 -c "import json;[print(q['question_id'],q['bloom_level'],q['max_points'],q['rubric_reference']) for q in json.load(open('backend/cases/pool/alpes-bank-genai-001.json'))['questions']]"` |
| Kalibrierungsanker noch hartkodiert q1–q4 | `grep -n '_format_calibration_notes' -A 5 backend/evaluator/rubric_evaluator.py` |
| Rubric-Schwellen | `grep -n 'threshold_pct\|score_floor_pct' backend/config/rubrics/*.json` |
| TP4-Guardrail-Lücke besteht noch | `grep -c forbidden_framework_names backend/config/tp_configs.py` (3 = Lücke besteht, 4 = geschlossen) |
| LLM-Mock-Signatur unverändert | `grep -n 'async def complete' -A 6 backend/llm.py` |
| Mongo-2s-Timeout | `grep -n serverSelectionTimeoutMS backend/db/mongo.py` |
| Alignment-Referenzmetriken | `grep -nE 'Pearson\|MAE' docs/teacher_alignment_report_20260531_17submissions.md` |
| Glossar weiterhin frontend-hartkodiert | `grep -n CASE_GLOSSARY "frontend/app/cases/[id]/page.tsx"` |
