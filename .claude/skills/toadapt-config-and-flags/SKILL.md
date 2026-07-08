---
name: toadapt-config-and-flags
description: >
  Katalog aller Env-Variablen (Backend + Frontend) und aller Magic Numbers
  im ToAdapt-Repo, plus TP_CONFIGS/TP_SCHEDULE-Anatomie und die Checkliste
  "Neue Config-Achse hinzufügen". Lade diese Skill, wenn du (a) eine
  Umgebungsvariable suchst, setzt, umbenennst oder ihre Wirkung verstehen
  musst (OPENROUTER_*, TOADAPT_API_KEY, STUDENT_ACCESS_CODE, MONGODB_*,
  ALLOWED_ORIGINS, WEB_CONCURRENCY, TEACHER_*, NEXT_PUBLIC_API_URL), (b) ein
  hardcodiertes Limit/Schwellwert änderst (max_tokens, Punktbänder,
  Wortlimits, Rate-Limits, Timeouts, Feedback-Schwellen), (c) Symptome wie
  "401/503 auf Teacher-Endpoints", "Session-404 bei mehreren Workern",
  "Studenten-API öffentlich erreichbar", "Warnung student_flow_open",
  "falsche TP-Phase" debuggst, oder (d) eine neue Konfigurationsachse
  einführen willst. Keywords: env, .env, Environment Variable, Flag, Config,
  Magic Number, Schwellwert, Threshold, TP_CONFIGS, TP_SCHEDULE, Railway
  Variables, Vercel Environment.
---

# ToAdapt — Config- und Flag-Katalog

Alle Fakten hier wurden am **2026-07-08** direkt gegen den Code verifiziert.
Zeilennummern driften — nutze die Re-Verifikations-Kommandos am Ende jedes
Abschnitts, bevor du dich auf eine Zeile verlässt.

Kontext in einem Satz: ToAdapt ist ein FastAPI-Backend (deployt auf Railway)
plus Next.js-Frontend (deployt auf Vercel); Studierende bearbeiten AI-generierte
Mini-Business-Cases, ein LLM-Judge bewertet die Antworten, Lehrkräfte sehen ein
Dashboard.

## Wann diese Skill NICHT gilt

- Umgebung von Null aufsetzen (venv, npm, Docker, bekannte Install-Fallen) → **toadapt-build-and-env**
- Lokal starten, Railway/Vercel-Deploy-Ablauf, wo Daten landen → **toadapt-run-and-operate**
- Ein Symptom triagieren ("es ist kaputt, warum?") → **toadapt-debugging-playbook**
- /health/diagnostics, Log-Events, Diagnose-Skripte → **toadapt-diagnostics-and-tooling**
- Ob/wie eine Config-Änderung überhaupt erlaubt ist (Gates, Unverhandelbares) → **toadapt-change-control**
- Warum die Architektur so ist, wie sie ist → **toadapt-architecture-contract**
- Didaktik hinter TPs, Bloom, Scaffolding, Canvas-Scoring → **bwl-scaffolding-reference**

---

## 1. Env-Variablen — Backend

Quelle der Wahrheit: `.env.example` (Repo-Root, aktuell gepflegt) plus
`grep -rn "os.environ" backend/`. Das Backend lädt `.env` via `load_dotenv()`
in `backend/main.py` **vor** den übrigen Imports (deshalb die absichtlichen
E402-Ignores in `pyproject.toml`). Auf Railway kommen die Werte aus den
Service-Variables, nicht aus einer Datei.

### LLM (OpenRouter)

Das Backend spricht **OpenRouter** über das OpenAI-SDK (`backend/llm.py`) —
NICHT das Anthropic-SDK, egal was ältere Doku sagt.

| Variable | Zweck | Default | Prod-Pflicht? | Gefahr wenn falsch |
|---|---|---|---|---|
| `OPENROUTER_API_KEY` | API-Key für alle LLM-Calls (Agenten, Evaluator, Case-Generierung) | leer | **JA** | Ohne Key wirft `OpenRouterClient.__init__` `ValueError` → Chat/Evaluation/Generierung schlagen fehl. Startup loggt `openrouter_api_key_configured=false`. |
| `OPENROUTER_MODEL` | Modell-ID für alle Calls | `anthropic/claude-sonnet-4.5` | nein | Anderes Modell = andere Judge-Kalibrierung. Modellwechsel erfordert Alignment-Recheck (→ toadapt-change-control). |
| `OPENROUTER_BASE_URL` | API-Endpoint | `https://openrouter.ai/api/v1` | nein | Nur für Tests/Proxies ändern. |
| `OPENROUTER_HTTP_REFERER` | `HTTP-Referer`-Header (OpenRouter-Attribution) | `http://localhost:3000` | nein | Kosmetisch. |
| `OPENROUTER_APP_TITLE` | `X-Title`-Header | `ToAdapt` | nein | Kosmetisch. |
| `LLM_TIMEOUT_SECONDS` | Timeout pro LLM-Call | `60` | nein | Zu klein → Evaluator-Fehlschläge (technical_fallback); zu groß → hängende Requests unter Last. |
| `LLM_MAX_RETRIES` | SDK-Retries (429/5xx, exponentielles Backoff) | `2` | nein | Zu hoch → Kostenmultiplikator bei Ausfällen. |
| `LLM_MAX_CONCURRENCY` | Globales Semaphor pro Event-Loop | `16` | nein | Zu hoch → OpenRouter-Rate-Limits; zu niedrig → Warteschlangen unter Peak-Last. |

### Auth & Zugriff

| Variable | Zweck | Default | Prod-Pflicht? | Gefahr wenn falsch |
|---|---|---|---|---|
| `TOADAPT_API_KEY` | Shared Secret; Backend verlangt es als Header `X-API-Key` auf allen `/dashboard/*`-Routen, schreibenden `/admin`-Routen und `/health/diagnostics` (`backend/auth.py`, `require_api_key`) | leer | **JA** | Fail-closed: ohne konfigurierten Key antworten geschützte Endpunkte mit **503** ("Auth nicht konfiguriert"). **MUSS identisch** als `TOADAPT_API_KEY` in Vercel (Frontend, server-only) gesetzt sein, sonst 401 auf allen Teacher-API-Calls. Erzeugen: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `STUDENT_ACCESS_CODE` | Kohorten-Zugangscode für den Studierenden-Flow (Sessions/Chat/Submissions); Header `X-Student-Access-Code` (`backend/auth.py`, `require_student_access`) | leer | **JA** (im Kursbetrieb) | **Leer = Studenten-API öffentlich** — jeder im Internet kann LLM-Kosten auslösen. Das Backend loggt beim Start die Warnung `student_flow_open` (`backend/main.py`, lifespan). Leer ist nur für Dev/anonyme Prolific-Experimente gedacht. Das Frontend hängt den Code aus `sessionStorage['student_access_code']` an (`frontend/lib/api.ts`). |
| `ALLOWED_ORIGINS` | Kommagetrennte CORS-Origin-Liste | leer → `http://localhost:3000`, `http://127.0.0.1:3000` | **JA** | Falsche/fehlende Origin → Browser blockt alle Frontend→Backend-Requests (CORS-Fehler). Wildcard ist mit `allow_credentials=True` unzulässig. |
| `SECRET_KEY` | **TOT.** Historischer Rest in alten `.env`-Dateien | — | nein | Wird nirgends im Code gelesen (`grep -rn SECRET_KEY backend/ frontend/` → keine Treffer). Nicht neu setzen, kann aus Envs entfernt werden. |

### MongoDB (primärer Store)

Ohne Mongo fällt alles auf In-Memory + Dateien zurück (`backend/db/runtime_submissions/`,
`backend/db/submissions/`) — auf Railway ist das Dateisystem **ephemer**, Daten
sind beim Redeploy weg. Verbindungs-Auflösung (`backend/db/mongo.py::resolve_uri`):
`MONGODB_URI` gewinnt; sonst wird aus `MONGODB_MAS_NAME` + `MONGODB_MAS_KEY` +
Host eine URI gebaut.

| Variable | Zweck | Default | Prod-Pflicht? | Gefahr wenn falsch |
|---|---|---|---|---|
| `MONGODB_URI` | Komplette Connection-URI (gewinnt gegen alles andere) | leer | JA (oder MAS-Trio) | Ohne Mongo: Datenverlust bei Redeploy, `WEB_CONCURRENCY` muss 1 bleiben. |
| `MONGODB_MAS_NAME` / `MONGODB_MAS_KEY` | Username/Passwort für den URI-Bau | leer | alternativ zu URI | Beide nötig, sonst kein Verbindungsaufbau über diesen Pfad. |
| `MONGODB_HOST` | Cluster-Host; Fallback-Kette: `MONGODB_HOST` → `MONGODB_CLUSTER_HOST` → `MONGODB_CLUSTER` | leer | alternativ zu URI | Die drei Alias-Namen sind ein Relikt der Mongo-Debugging-Saga (2026-05-14). |
| `MONGODB_SCHEME` | URI-Schema | `mongodb+srv` | nein | Für lokales Docker-Mongo `mongodb` nötig (docker-compose setzt direkt `MONGODB_URI=mongodb://mongo:27017`). |
| `MONGODB_OPTIONS` | URI-Query-Optionen | `retryWrites=true&w=majority` | nein | — |
| `MONGODB_DATABASE` | DB-Name | `toadapt` | nein | — |
| `MONGODB_COLLECTION` | Event-Log-Collection | `experiment_events` | nein | Forschungs-Skripte erwarten die Default-Namen. |
| `MONGODB_SUBMISSIONS_COLLECTION` | Submission-States | `submission_states` | nein | — |
| `MONGODB_SESSIONS_COLLECTION` | Chat-Sessions | `sessions` | nein | — |
| `MONGODB_DASHBOARD_COLLECTION` | Dashboard-Ergebnisse | `dashboard_results` | nein | — |

### Betrieb / Observability

| Variable | Zweck | Default | Prod-Pflicht? | Gefahr wenn falsch |
|---|---|---|---|---|
| `ENVIRONMENT` | `development` \| `production`; `production` schaltet structlog auf JSON-Renderer | `development` | JA | Ohne JSON-Logs sind Railway-Logs schlecht maschinell auswertbar; steuert auch Sentry-Environment-Tag. |
| `LOG_LEVEL` | structlog-Level | `INFO` | nein | `DEBUG` in Prod = Log-Flut. |
| `SENTRY_DSN` | Error-Tracking (leer = deaktiviert); `send_default_pii=False` ist hart gesetzt | leer | nein | — |
| `SENTRY_TRACES_SAMPLE_RATE` | Sentry-Tracing-Quote | `0` | nein | >0 = Kosten. |
| `WEB_CONCURRENCY` | Uvicorn-Worker-Zahl (nur via `railway.toml` startCommand: `--workers ${WEB_CONCURRENCY:-1}`) | `1` | nein | **>1 NUR mit verifiziert laufendem Mongo.** Ohne Mongo liegen Sessions nur im Worker-RAM; ein zweiter Worker beantwortet laufende Chats mit **404**. Kommentar dazu steht in `railway.toml`. |
| `PORT` | Von Railway injiziert, im startCommand verwendet | — | (Railway setzt) | — |

### TP-Zeitplan-Variablen: TOT (Falle!)

`.env.example` enthält `TP1_START` … `TP4_DEADLINE` — **kein Code liest sie**
(Stand 2026-07-08). Der reale Zeitplan ist **hartkodiert** in
`backend/config/tp_configs.py::TP_SCHEDULE` (siehe Abschnitt 3). Wer den
Zeitplan ändern will, muss den Code ändern, nicht die Env.

**Re-Verifikation Abschnitt 1:**

```bash
grep -rn "os.environ\|os.getenv" backend/ --include="*.py" | grep -v __pycache__
grep -rn "TP1_START" backend/ --include="*.py"   # leer = TP-Env-Vars weiterhin tot
grep -rn "SECRET_KEY" backend/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx" | grep -v node_modules
```

---

## 2. Env-Variablen — Frontend (`frontend/.env.local` lokal, Vercel-Env in Prod)

Es gibt **keine** `frontend/.env.example` (Stand 2026-07-08) — diese Tabelle
ist die Referenz.

| Variable | Zweck | Default | Prod-Pflicht? | Gefahr wenn falsch |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend-Basis-URL für Browser-Calls (Studenten-Flow geht direkt Browser→Railway; `frontend/lib/api.ts`) | `http://localhost:8000` | **JA** | Falsch → alle Studenten-API-Calls scheitern. `NEXT_PUBLIC_` = wird ins Client-Bundle eingebacken, Änderung erfordert Re-Build/Redeploy. |
| `BACKEND_API_URL` | Backend-URL für den server-seitigen Teacher-Proxy (`frontend/app/api/teacher/[...path]/route.ts`); Fallback-Kette: `BACKEND_API_URL` → `NEXT_PUBLIC_API_URL` → `http://localhost:8000` | leer | nein (Fallback greift) | Nur nötig, wenn Server-zu-Server-URL von der Browser-URL abweicht (z.B. internes Railway-Netz). |
| `TOADAPT_API_KEY` | Der Teacher-Proxy hängt ihn server-seitig als `X-API-Key` an — der Browser sieht den Key **nie** | leer | **JA** | **Muss byte-identisch mit dem Backend-Wert in Railway sein.** Abweichung → 401 auf allen `/api/teacher/*`-Calls (Dashboard/Admin leer). |
| `TEACHER_ACCESS_CODE` | Login-Code für Lehrkräfte (`frontend/app/teacher-login/route.ts`) | leer | **JA** | Fail-closed: ohne konfigurierten Code ist **kein** Teacher-Login möglich (kein "0000"-Fallback — die README-Zeile dazu ist veraltet). |
| `TEACHER_SESSION_SECRET` | HMAC-SHA256-Secret für das signierte, httpOnly Teacher-Session-Cookie (`frontend/lib/teacherAuth.ts`) | leer | **JA** | Fehlt es, wirft `signTeacherSession()` beim Login; `verifyTeacherSession()` gibt `false` zurück → Middleware (`frontend/middleware.ts`, matcher `/admin/*`, `/dashboard/*`) redirectet dauerhaft auf die Login-Seite. Rotation invalidiert alle laufenden Teacher-Sessions. |

**Re-Verifikation Abschnitt 2:**

```bash
grep -rn "process.env" frontend --include="*.ts" --include="*.tsx" | grep -v node_modules
```

---

## 3. TP_CONFIGS, TP_SCHEDULE und current_tp_phase()

"TP" = Touchpoint, eine von vier Kursphasen (TP1 Analyse → TP2 Entscheidung →
TP3 Umsetzung → TP4 Integration) des BWL-A-Kurses. Alles lebt in
`backend/config/tp_configs.py`.

### TP_SCHEDULE (hartkodiert!)

```python
TP_SCHEDULE = {
    1: {"start": date(2026, 9, 14),  "deadline": date(2026, 10, 5)},
    2: {"start": date(2026, 10, 6),  "deadline": date(2026, 10, 26)},
    3: {"start": date(2026, 10, 27), "deadline": date(2026, 11, 16)},
    4: {"start": date(2026, 11, 17), "deadline": date(2026, 12, 7)},
}
```

`current_tp_phase(today=None)`-Verhalten:
- Datum innerhalb eines Fensters → diese TP.
- **Vor Kursbeginn (< 2026-09-14) → 1.**
- **Nach Kursende (> 2026-12-07) und in Lücken danach → 4.**

Konsumenten: `backend/main.py` (Startup-Log `tp_phase`, `/health/diagnostics`)
und `backend/api/routes.py` Zeile ~137: `tp = case.target_tp or current_tp_phase()`
— d.h. nur Cases mit `target_tp == 0` ("FULL") fallen auf die Kalenderphase
zurück.

**Bekannte Lücke:** Das Frontend sendet beim Submission-POST hart
`target_tp: 1` (`frontend/app/cases/[id]/page.tsx`, Suche nach `target_tp`).
Die TP-Progression ist also faktisch nicht aktiv; `TP_SCHEDULE` läuft leer mit.

### TP_CONFIGS-Anatomie (dict, Keys 1–4)

Felder pro TP (nicht alle TPs haben alle Felder):

| Feld | Typ | Konsument |
|---|---|---|
| `name`, `format`, `bloom_levels` | Metadaten | Prompts/Anzeige |
| `allowed_frameworks` | list[str] | dokumentarisch (Denkprinzipien, die Agenten implizit hervorrufen dürfen) |
| `forbidden_framework_names` | list[str] | **`guardrail_check()` in `backend/agents/orchestrator.py`** — Agent-Antworten, die einen dieser Namen enthalten, werden komplett durch einen Fallback-Text ersetzt |
| `case_chapters`, `key_questions`, `rubric_reference` | — | Prompt-Bau / Rubric-Verkettung |
| `requires_tp1_reference` u.ä. | bool | dokumentarisch |
| `individual_component` | dict | dokumentarisch |

**Die TP4-Lücke:** `TP_CONFIGS[4]` hat **keinen** Key
`forbidden_framework_names`. `guardrail_check()` liest ihn mit
`.get("forbidden_framework_names", [])` — in TP4 greifen also nur die
globalen `FORBIDDEN_PATTERNS` (porter, five forces, rbv, vrio, 4p, tce,
preiselastizität …), nicht die TP-spezifische Liste. Vermutlich
unbeabsichtigt; wer es fixt: Lehrdesign-Constraint, also über
toadapt-change-control gaten.

**Re-Verifikation Abschnitt 3:**

```bash
grep -n "forbidden_framework_names" backend/config/tp_configs.py   # TP4 fehlt weiterhin?
grep -rn "current_tp_phase\|TP_SCHEDULE" backend/ --include="*.py" | grep -v __pycache__
grep -n "target_tp" "frontend/app/cases/[id]/page.tsx"
```

---

## 4. Magic-Numbers-Katalog (mit Fundort)

Zeilennummern: Stand 2026-07-08, driften. Immer per grep bestätigen.

### Agenten & Guardrails (`backend/agents/orchestrator.py`)

| Wert | Bedeutung | Fundort |
|---|---|---|
| `max_tokens=220` (CONCEPTUAL) / `320` (alle anderen Agenten) | Antwortlänge pro Agent-Call | ~Z. 410, `grep -n "max_tokens" backend/agents/orchestrator.py` |
| `session.message_count >= 1` | Metacognitive-First-Phase gilt nach **einer** metakognitiven Antwort als beendet | ~Z. 420, `grep -n "message_count >= 1"` |
| `history.slice(-10)` | Chat-Verlauf wird CLIENT-seitig gehalten; nur die letzten 10 Einträge gehen pro Request mit (Server hält keinen Verlauf) | `frontend/app/cases/[id]/page.tsx` ~Z. 761, `grep -n "slice(-10)"` |

### Rubric-Evaluator (`backend/evaluator/rubric_evaluator.py` + `rubric_loader.py`)

"Judge" = der LLM-Call, der eine Studierenden-Antwort gegen die Rubric bewertet.

| Wert | Bedeutung | Fundort |
|---|---|---|
| `max_tokens=1200` | Judge-Call UND JSON-Repair-Call | ~Z. 276 u. 316 |
| `mid = max_points × 0.55`, `low = × 0.25` | Punktband-Anker im Judge-Prompt | ~Z. 295–296 |
| `rubric_fit_pct = pct×0.7 + canvas_pct×0.3` | Gewichtung Rubric-Score vs. Canvas-Alignment | ~Z. 409 |
| `score_floor_pct=75.0`, `exemplar_threshold_pct=80.0` | Exemplar-Kandidat, wenn `percentage ≥ 75` UND `canvas_alignment_pct ≥ 80` — Defaults als Pydantic-Felder in `rubric_loader.py::QuestionRubric`, überschreibbar pro Rubric-JSON; Evaluator nimmt bei mehreren Rubrics jeweils das `min()` | `_canvas_exemplar_candidate`, ~Z. 183–193 |
| `80 / 60 / 40` | Schwellen fürs Overall-Feedback-Wording | ~Z. 461–465; Canvas-Zusatzhinweis ab `canvas_alignment_pct >= 40` (~Z. 474) |
| `judge_confidence == "low"` → `needs_human_review = True` | erzwungen, unabhängig vom Judge-Flag | ~Z. 353 |
| 3 JSON-Extraktions-Kandidaten → 1 Repair-Call → technical_fallback (0 Punkte, `needs_human_review=True`) | Robustheits-Kaskade | `_extract_json_candidates` / `_fallback_payload` |
| Kalibrierungsanker pro `question_id` q1–q4 | HARTKODIERT (Ergebnis der Teacher-Alignment-Studie); Änderung = Alignment-Recheck-Pflicht | `_format_calibration_notes` |

### Wortlimits (NUR Frontend, nach Frage-INDEX, nicht question_id!)

`frontend/app/cases/[id]/page.tsx` ~Z. 311–313:

| Frage-Index (0-basiert) | minWords | maxWords |
|---|---|---|
| 0–1 (Fragen 1–2) | 50 | 200 |
| 2–3 (Fragen 3–4) | 100 | 200 |
| ab 4 | 150 | 200 |

Das Backend validiert Wortzahlen NICHT (loggt nur `answer_word_count` in
`backend/api/routes.py`). Cases mit anderer Fragen-Reihenfolge bekommen
falsche Limits — bekannte Schwäche.

### Rate-Limits (`backend/ratelimit.py`, angewandt in `backend/api/routes.py`)

In-Process Sliding Window, **pro Worker-Prozess** (bei N Workern effektiv
bis zu N-faches Limit). Key = Client-IP (braucht `--proxy-headers`, steht im
railway.toml-startCommand) oder Pfad-Parameter.

| Endpoint | Limit | Schlüssel |
|---|---|---|
| `POST /auth/student/verify` | 10 / 60 s | IP |
| `POST /sessions` | 20 / 60 s | IP |
| `POST /sessions/{id}/chat` | 15 / 60 s | session_id |
| `POST /submissions` | 20 / 60 s | IP |
| `POST /submissions/{id}/answer` | 60 / 60 s | submission_id |
| `POST /submissions/{id}/submit` | 5 / 60 s | submission_id |
| Map-Größenschutz | `_MAX_TRACKED_KEYS = 10_000` | `backend/ratelimit.py` |

### Timeouts & Sessions

| Wert | Bedeutung | Fundort |
|---|---|---|
| `serverSelectionTimeoutMS=2000` | Mongo-Verbindungsversuch (2 s) | `backend/db/mongo.py`, `experiment_logger.py`, `submission_store.py` |
| 30 s | Backoff nach fehlgeschlagener Mongo-Verbindung, bevor erneut versucht wird | dieselben drei Dateien, `grep -n "< 30"` |
| `LLM_TIMEOUT_SECONDS=60`, `LLM_MAX_RETRIES=2`, `LLM_MAX_CONCURRENCY=16` | LLM-Client-Defaults (env-überschreibbar, s. Abschnitt 1) | `backend/llm.py` Z. 24–26 |
| `12 * 60 * 60` (12 h) | Teacher-Session-Cookie-Lebensdauer | `frontend/lib/teacherAuth.ts` Z. 8 |

**Re-Verifikation Abschnitt 4:**

```bash
grep -n "max_tokens" backend/agents/orchestrator.py backend/evaluator/rubric_evaluator.py
grep -n "0.55\|0.25\|0.7)\|0.3)" backend/evaluator/rubric_evaluator.py
grep -n "exemplar_threshold_pct\|score_floor_pct" backend/evaluator/rubric_loader.py
grep -n "minWords" "frontend/app/cases/[id]/page.tsx"
grep -n "rate_limit(" backend/api/routes.py
grep -rn "serverSelectionTimeoutMS\|< 30" backend/db/*.py
grep -n "MAX_AGE_SECONDS" frontend/lib/teacherAuth.ts
```

---

## 5. Checkliste: Neue Config-Achse hinzufügen

Ziel: Ein neuer Wert soll per Env steuerbar sein statt hartkodiert.

1. **Change-Control prüfen:** Betrifft der Wert Judge/Prompts/Guardrails/
   Lehrdesign? → zuerst **toadapt-change-control** lesen (Alignment-Recheck-
   bzw. Gate-Pflicht).
2. **Lesen im Code:** `os.environ.get("MEIN_FLAG", "<default>")` an EINER
   Stelle (Modul-Konstante), nicht verstreut. Frontend: `process.env.MEIN_FLAG`;
   browser-sichtbare Werte brauchen Prefix `NEXT_PUBLIC_` und einen Re-Build.
3. **`.env.example` ergänzen** (Repo-Root) — mit Kommentar: Zweck, Default,
   Prod-Pflicht. Für Frontend-Vars: es gibt keine `frontend/.env.example`;
   dokumentiere in Abschnitt 2 dieser Skill UND in der Betriebs-Doku.
4. **Startup-Log ergänzen, falls sicherheits-/kostenrelevant:** In
   `backend/main.py` im `lifespan`-Block als **boolescher Status** loggen
   (Muster: `student_access_code_configured=...`). NIEMALS Key-Material oder
   Env-Key-Namen loggen — der Kommentar dort ist Absicht.
5. **Diagnostics erwägen:** Wenn der Wert Betriebszustand beschreibt, in
   `/health/diagnostics` aufnehmen (API-Key-geschützt), nie in `/health`.
6. **Test ergänzen** für das Verhalten mit/ohne gesetzter Variable
   (`tests/`, Muster: monkeypatch von `os.environ`). → toadapt-validation-and-qa.
7. **Setzen in beiden Deployments:** Railway-Service-Variables (Backend) und
   Vercel-Environment (Frontend). Shared Secrets (Muster `TOADAPT_API_KEY`)
   müssen auf beiden Seiten identisch sein. Achtung: Nixpacks/dotenv hat
   historisch Railway-Vars überschrieben — `.env` gehört nicht ins
   Deploy-Image (`.dockerignore` prüfen).
8. **Diese Skill aktualisieren** (Tabelle in Abschnitt 1 oder 2) und
   Datumsstempel setzen.

---

## Provenance und Wartung

Erstellt: 2026-07-08, verifiziert gegen den damaligen `main`-Stand
(HEAD `141bb63`, nach dem filter-repo-Rewrite vom 2026-07-08).
Zeilennummern sind Momentaufnahmen.

Re-Verifikation pro drift-anfälligem Fakt (vom Repo-Root):

| Fakt | Kommando |
|---|---|
| Env-Katalog Backend vollständig | `grep -rn "os.environ" backend/ --include="*.py" \| grep -v __pycache__` |
| Env-Katalog Frontend vollständig | `grep -rn "process.env" frontend --include="*.ts" --include="*.tsx" \| grep -v node_modules` |
| `.env.example` unverändert | `git log -1 --format=%ci -- .env.example` |
| TP-Env-Vars weiterhin tot | `grep -rn "TP1_START" backend/ --include="*.py"` (leer = tot) |
| SECRET_KEY weiterhin unbenutzt | `grep -rn "SECRET_KEY" backend/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx" \| grep -v node_modules` |
| TP4 ohne forbidden_framework_names | `grep -n "forbidden_framework_names" backend/config/tp_configs.py` |
| target_tp:1 im Frontend hartkodiert | `grep -n "target_tp" "frontend/app/cases/[id]/page.tsx"` |
| Agent-max_tokens 220/320 | `grep -n "max_tokens" backend/agents/orchestrator.py` |
| Evaluator-Zahlen (0.55/0.25/0.7/0.3/1200) | `grep -n "0.55\|0.25\|1200\|rubric_fit_pct" backend/evaluator/rubric_evaluator.py` |
| Exemplar-Defaults 80/75 | `grep -n "_pct" backend/evaluator/rubric_loader.py` |
| Rate-Limits | `grep -n "rate_limit(" backend/api/routes.py` |
| Mongo 2 s / 30 s | `grep -rn "serverSelectionTimeoutMS\|< 30" backend/db/*.py` |
| Teacher-Cookie 12 h | `grep -n "MAX_AGE_SECONDS" frontend/lib/teacherAuth.ts` |
| WEB_CONCURRENCY-Mechanik | `grep -n "WEB_CONCURRENCY" railway.toml` |
