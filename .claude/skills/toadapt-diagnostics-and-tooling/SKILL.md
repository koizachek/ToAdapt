---
name: toadapt-diagnostics-and-tooling
description: >-
  MESSEN statt schätzen im ToAdapt-Repo. Lade diese Skill, wenn du den
  Zustand einer laufenden Backend-Instanz prüfen willst (GET /health vs.
  GET /health/diagnostics mit X-API-Key), ein Log-Event interpretieren musst
  (toadapt_startup, student_flow_open, llm_call_completed, guardrail_triggered,
  chat_error, evaluation_json_parse_failed, mongo_*_failed, case_saved …),
  Railway-Logs nach Ereignissen filtern willst, Fragen über die Mongo-Collection
  experiment_events beantworten sollst ("wie viele Guardrail-Trigger pro Tag?",
  "Ø Turns pro Session?", "Agent-Verteilung?"), Token-Kosten kontrollieren
  willst, oder einen Smoke-Test gegen lokal/Railway fahren möchtest. Enthält
  drei getestete Skripte unter scripts/: smoke_backend.sh,
  summarize_dashboard_results.py, analyze_experiment_events.py.
---

# ToAdapt — Diagnostics & Tooling

Leitprinzip: **Messen statt schätzen.** Bevor du eine Hypothese über das
Systemverhalten aufstellst, hole dir Zahlen — über den Diagnostics-Endpoint,
die strukturierten Log-Events oder die Event-Collection in MongoDB.

Kontext in einem Satz: ToAdapt ist ein FastAPI-Backend (deployed auf Railway,
einer Container-Hosting-Plattform) + Next.js-Frontend (Vercel); Studierende
chatten mit 4 Scaffolding-Agenten über einen Business-Case und reichen
Freitext-Antworten ein, die ein LLM-Judge (LLM, das nach Rubric bewertet)
scored. Alle LLM-Calls laufen über OpenRouter (API-Aggregator).

## Wann diese Skill NICHT gilt

| Aufgabe | Stattdessen |
|---|---|
| Symptom → Ursache triagieren (401/503/429/404, CORS, Mongo weg, technical_fallback) | `toadapt-debugging-playbook` |
| Env-Variable suchen/setzen, Magic Numbers, TP_CONFIGS | `toadapt-config-and-flags` |
| Umgebung von Null aufbauen (venv, .env, pytest bootet nicht) | `toadapt-build-and-env` |
| Lokal starten, Railway/Vercel-Deploy, wo Daten landen, Forschungs-Skripte (`scripts/` im Repo-Root) bedienen | `toadapt-run-and-operate` |
| Tests schreiben, was als Evidenz zählt, CI-Gates | `toadapt-validation-and-qa` |
| q4/Bloom-6-Judge-Alignment untersuchen | `toadapt-judge-alignment-campaign` |
| Didaktik-Begriffe (Guardrail-Sinn, Bloom, Canvas-Scoring) verstehen | `bwl-scaffolding-reference` |
| Etwas ÄNDERN statt messen | erst `toadapt-change-control` |

---

## 1. Health-Endpoints

### GET /health (öffentlich)

Railway-Healthcheck (`railway.toml`: `healthcheckPath = "/health"`). Bewusst
minimal — keine Infrastruktur-Details auf einem öffentlichen Endpunkt:

```bash
curl -s http://localhost:8000/health
# → {"status":"ok","version":"0.2.0"}
```

### GET /health/diagnostics (X-API-Key)

Geschützt durch den Header `X-API-Key` (Shared Secret aus Env-Variable
`TOADAPT_API_KEY`; fail-closed: ohne konfigurierten Key antwortet der
Endpoint mit 503, mit falschem Key 401 — Code: `backend/auth.py`).

```bash
curl -s -H "X-API-Key: $TOADAPT_API_KEY" http://localhost:8000/health/diagnostics
```

Feldreferenz (Quelle: `backend/main.py` `health_diagnostics()` +
`backend/db/experiment_logger.py` `diagnostics`-Property; Stand: 2026-07-08):

| Feld | Bedeutung |
|---|---|
| `status`, `version` | Wie /health ("ok", "0.2.0") |
| `tp_phase` | Aktuelle Touchpoint-Phase (1–4) aus `current_tp_phase()` — Zeitplan HARTKODIERT in `backend/config/tp_configs.py::TP_SCHEDULE`; die Env-Variablen `TP1_START`…`TP4_DEADLINE` aus `.env.example` sind TOT, kein Code liest sie (siehe `toadapt-config-and-flags`). Falsche `tp_phase` also NIE über Railway-Variablen "fixen" — nur per Code-Änderung an `TP_SCHEDULE` |
| `build_marker` | Fester String `railway-mongo-env-diagnostics-2026-05-14-1809z` — Relikt einer Mongo-Debugging-Kampagne; nützlich um zu prüfen, WELCHER Build tatsächlich läuft |
| `mongo_logging_enabled` | `true` = Mongo-URI auflösbar UND pymongo installiert. `false` = alles läuft nur auf Datei-Fallback (auf Railway: Daten weg beim Redeploy!) |
| `mongo_connection_mode` | `"uri"` = `MONGODB_URI` gesetzt; `"mas_credentials"` = URI aus `MONGODB_MAS_NAME`+`MONGODB_MAS_KEY`+`MONGODB_HOST` zusammengebaut; `"disabled"` = keins von beidem → kein Mongo |
| `mongo_database` / `mongo_collection` | Effektive Namen (Default `toadapt` / `experiment_events`) |
| `mongo_has_uri` | Ob eine URI auflösbar war (Konfiguration, NICHT Erreichbarkeit) |
| `mongo_env_keys` | Sortierte NAMEN aller gesetzten `MONGODB_*`-Env-Variablen (keine Werte) — verrät, was Railway wirklich in den Prozess injiziert |
| `mongodb_host_len`, `mongodb_mas_name_len`, `mongodb_mas_key_len`, `mongodb_uri_len` | LÄNGEN der jeweiligen Env-Werte (0 = leer/nicht gesetzt) — erkennt Copy-Paste-Fehler ohne Secrets preiszugeben |
| `mongo_last_connection_failure` | `time.monotonic()`-Wert des letzten fehlgeschlagenen Verbindungsversuchs. **Kein Epoch-Timestamp!** `0.0` = seit Prozessstart nie fehlgeschlagen. Nach einem Fehler gilt 30 s Backoff, in dem gar nicht neu verbunden wird |

Wichtig: `mongo_logging_enabled: true` heißt nur "konfiguriert". Ob die
Verbindung tatsächlich klappt, siehst du an `mongo_last_connection_failure`
(bleibt 0.0) bzw. am Fehlen von `mongo_log_connection_failed`-Logs.

---

## 2. Log-Event-Lexikon

Das Backend loggt mit structlog (strukturiertes Logging: Event-Name +
Key-Value-Felder). Bei `ENVIRONMENT=production` (Railway) sind es
JSON-Zeilen mit dem Event-Namen im Feld `"event"`; lokal Console-Format.

### Startup & Betrieb (`backend/main.py`)

| Event | Level | Felder / Interpretation |
|---|---|---|
| `toadapt_startup` | info | Konfigurations-Snapshot beim Boot: `tp_phase`, `llm_model`, `openrouter_api_key_configured` (bool), `mongo_logging_enabled`, `mongo_connection_mode`, `student_access_code_configured`, `sentry_enabled`, `environment`. **Erste Anlaufstelle nach jedem Deploy**: stimmen die Flags? |
| `student_flow_open` | **warning** | `STUDENT_ACCESS_CODE` ist nicht gesetzt — Sessions/Chat/Submissions sind ÖFFENTLICH erreichbar, jeder im Internet kann LLM-Kosten auslösen. In Produktion ein Alarmsignal. |
| `toadapt_shutdown` | info | Sauberer Shutdown |
| `unhandled_exception` | error | Global Exception Handler: `error`, `path`. Sollte selten sein — jede Zeile ist ein Bug-Kandidat |

### LLM & Kosten (`backend/llm.py`)

| Event | Level | Felder / Interpretation |
|---|---|---|
| `llm_call_completed` | info | `model`, `prompt_tokens`, `completion_tokens`, `total_tokens` — pro OpenRouter-Call, **egal ob Agent-Chat, Judge-Evaluation oder Case-Generierung** (gemeinsamer Client). Für Kostenkontrolle über einen Zeitraum: `total_tokens` aufsummieren und mit den OpenRouter-Preisen des Modells multiplizieren |

### Chat & Guardrails (`backend/agents/orchestrator.py`, `backend/api/routes.py`)

| Event | Level | Felder / Interpretation |
|---|---|---|
| `agent_response` | info | `agent` (metacognitive/strategic/conceptual/procedural), `tp`, `msg_count`, `language` — ein Chat-Turn wurde beantwortet |
| `guardrail_triggered` | **warning** | `reason`, `agent`. Die Agent-Antwort verletzte eine Regel und wurde KOMPLETT durch einen festen Fallback-Text ersetzt (Guardrail = Filter, der Lehrdesign-Verstöße wie Framework-Namen oder direkte Antworten abfängt). Enthält KEINE session_id — Session-Zuordnung nur indirekt möglich (siehe §4-Skript) |
| `chat_error` | error | `error`, `type` — der Orchestrator-Call ist geworfen (meist OpenRouter-Timeout/Quota); Client bekam 503 |

`reason`-Codes von `guardrail_check()` (Reihenfolge = Prüfreihenfolge):

| reason | Bedeutung |
|---|---|
| `framework_name_dropped: <name>` | TP-spezifisch verbotener Framework-Name aus `TP_CONFIGS[tp]["forbidden_framework_names"]` im Text (Achtung: TP4 hat diesen Key nicht → dort greift nur der Rest) |
| `direct_answer_pattern: <pattern>` | Globales Muster aus `FORBIDDEN_PATTERNS`: direkte Antwort ("die lösung lautet", "the answer is" …) oder harter Modellname (porter, five forces, rbv, vrio, 4p, tce, preiselastizität …) |
| `style_contains_slang` | Treffer in `SLANG_PATTERNS` |
| `style_contains_emoji` | Emoji (Unicode-Kategorie So) in der Antwort |
| `direct_recommendation_or_template` | Empfehlungs-/Textbaustein-Muster (`RECOMMENDATION_PATTERNS` + Regexe) |
| `case_speculation_outside_context` | Agent spekuliert über Fakten außerhalb des Case-Materials (`CASE_SPECULATION_PATTERNS`) |

### Evaluator / Judge (`backend/evaluator/rubric_evaluator.py`, `backend/api/routes.py`)

| Event | Level | Felder / Interpretation |
|---|---|---|
| `evaluation_json_parse_failed` | warning | `submission_id`, `question_id`, `raw_preview` (erste 500 Zeichen der Judge-Antwort). Judge-JSON war unparsebar → es folgt EIN Repair-LLM-Call |
| `evaluation_json_repair_failed` | error | Auch der Repair-Call scheiterte → Frage bekommt `_fallback_payload`: 0 Punkte, `evaluation_status="technical_fallback"`, `needs_human_review=true`. Häufung hier = Judge-Prompt/Modell-Problem |
| `submission_evaluated` | info | `submission_id`, `total`, `max`, `pct`, `canvas_alignment_pct`, `rubric_fit_pct`, `canvas_exemplar_candidate` — Evaluation abgeschlossen |
| `evaluation_error` | error | Kompletter `evaluate_submission`-Aufruf geworfen; Client bekam 503, Antworten blieben gespeichert |

### Persistenz (`backend/db/*.py`)

Alle warning-Level; Muster: Mongo-Operation fehlgeschlagen, Code weicht auf
Datei-Fallback / prozesslokalen Cache aus (still, kein Nutzerfehler):

| Event | Quelle |
|---|---|
| `mongo_connection_failed` | `db/mongo.py` — gemeinsamer Client für sessions/submissions/dashboard/cases baut nicht auf (30-s-Backoff) |
| `mongo_log_connection_failed`, `mongo_log_failed`, `mongo_logger_unavailable` | `db/experiment_logger.py` — Event-Logging nach `experiment_events` (Events gehen dann VERLOREN, kein Datei-Fallback für Events!) |
| `session_store_save_failed` / `session_store_load_failed` | `db/session_store.py` |
| `submission_store_save_failed` / `_load_failed` / `_file_load_failed` / `_connection_failed` | `db/submission_store.py` (Datei-Fallback: `backend/db/runtime_submissions/`) |
| `dashboard_store_save_failed` / `dashboard_store_load_failed` | `db/dashboard_store.py` (Datei-Fallback: `backend/db/submissions/`) |

### Case-Verwaltung (`backend/cases/manager.py`, `generator.py`, `backend/admin/routes.py`)

| Event | Level | Bedeutung |
|---|---|---|
| `case_generation_started` / `case_generation_complete` / `case_generation_failed` | info/error | Case-Generierung (LLM-Kosten!) |
| `case_regenerate_started` / `_complete` / `_failed` | info/error | Teil-Regenerierung eines Case |
| `case_saved`, `case_edited`, `case_approved`, `case_rejected`, `case_retired` | info | Audit-Spur des Case-Lebenszyklus. `case_approved` hat `reviewer` und `forced` (=Approve trotz Validator-Beanstandung — nachverfolgen!) |
| `case_file_save_failed`, `case_mongo_save_failed`, `case_mongo_load_failed`, `case_mongo_list_failed`, `case_mongo_doc_invalid`, `case_load_error` | warning | Persistenz-Probleme des Case-Pools |

### Railway-Logs nach Events filtern

In Produktion (`ENVIRONMENT=production`) sind Logzeilen JSON mit
`"event": "<name>"`. Im Railway-Dashboard (Service → Logs) einfach nach dem
Event-Namen suchen, z.B. `guardrail_triggered` oder `"event": "chat_error"`.
UNVERIFIZIERT (CLI hier nicht installiert): mit der Railway-CLI sollte
`railway logs | grep guardrail_triggered` funktionieren.

---

## 3. experiment_events in MongoDB

Zusätzlich zu den (flüchtigen) Logs schreibt der Studenten-Flow
Forschungs-Events nach Mongo. Collection: `experiment_events` (Env
`MONGODB_COLLECTION`), Datenbank `toadapt` (Env `MONGODB_DATABASE`).
Schreiber: `MongoExperimentLogger.log_event()` in
`backend/db/experiment_logger.py`, aufgerufen fire-and-forget aus
`backend/api/routes.py` (`_log_experiment_event`).

Dokumentschema:

```json
{ "event_type": "<typ>", "created_at": ISODate(...), "payload": { ... } }
```

Event-Typen (alle Call-Sites in `backend/api/routes.py`; Stand: 2026-07-08):

| event_type | Wann | Wichtige payload-Felder |
|---|---|---|
| `session_created` | POST /sessions | `session` (kompletter Session-Dump inkl. `session_id`, `case_id`, `tp_phase`), `experiment` |
| `chat_turn_completed` | POST /sessions/{id}/chat | `session_id`, `case_id`, `user_id`, `message_count`, `history_length`, `agent_type`, **`user_message` und `assistant_message` im Klartext** |
| `submission_created` | POST /submissions | `submission` (Dump) |
| `submission_answer_saved` | POST /submissions/{id}/answer | `submission_id`, `question_id`, **`answer_text` im Klartext**, `answer_word_count`, `participant_id` |
| `submission_submitted` | POST /submissions/{id}/submit (vor Evaluation) | `submission` (Dump inkl. aller Antworten) |
| `submission_evaluated` | nach erfolgreicher Evaluation | `submission` + `result` (alle Scores, Feedback) |
| `canvas_exemplar_candidate` | nur wenn Result als Exemplar-Kandidat markiert | `submission_id`, `percentage`, `canvas_alignment_pct`, `scores` |

Jedes payload enthält zusätzlich `experiment_context_present` (bool) und ggf.
`experiment_context_missing: true`.

**DATENSCHUTZ:** `chat_turn_completed` / `submission_*` enthalten
Klartext-Antworten und Teilnehmer-IDs (`matrikelnummer` bzw. Prolific-PID).
Exporte dieser Collection sind Teilnehmerdaten: Ablage NUR unter
`~/ToAdapt_sensitive_data/`, NIEMALS ins Repo committen, nicht in Fixtures
oder Skills. Für Skript-Tests synthetische Daten verwenden.

### Read-only-Beispiel-Queries

mongosh (Mongo-Shell; URI aus Railway-Env bzw. `.env`, nie ins Repo):

```javascript
// Event-Typ-Verteilung
db.experiment_events.aggregate([
  { $group: { _id: "$event_type", n: { $sum: 1 } } }, { $sort: { n: -1 } }
])

// Chat-Turns pro Tag
db.experiment_events.aggregate([
  { $match: { event_type: "chat_turn_completed" } },
  { $group: { _id: { $dateToString: { format: "%Y-%m-%d", date: "$created_at" } },
              n: { $sum: 1 } } },
  { $sort: { _id: 1 } }
])

// Agent-Verteilung
db.experiment_events.aggregate([
  { $match: { event_type: "chat_turn_completed" } },
  { $group: { _id: "$payload.agent_type", n: { $sum: 1 } } }
])

// Durchschnittliche Turns pro Session
db.experiment_events.aggregate([
  { $match: { event_type: "chat_turn_completed" } },
  { $group: { _id: "$payload.session_id", turns: { $sum: 1 } } },
  { $group: { _id: null, avg_turns: { $avg: "$turns" }, sessions: { $sum: 1 } } }
])
```

pymongo (read-only), z.B. mit `.venv/bin/python`:

```python
import os
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000)
col = client["toadapt"]["experiment_events"]
for row in col.aggregate([
    {"$group": {"_id": "$event_type", "n": {"$sum": 1}}},
    {"$sort": {"n": -1}},
]):
    print(row)
```

Export für die Offline-Analyse (Standard-Tool `mongoexport`; Output in
`~/ToAdapt_sensitive_data/`, siehe Datenschutz oben):

```bash
mongoexport --uri "$MONGODB_URI" --collection experiment_events \
  --jsonArray --out ~/ToAdapt_sensitive_data/events_export.json
```

**Guardrail-Trigger pro Tag:** Die Mongo-Events enthalten den
Guardrail-Grund NICHT (der steht nur im Log-Event `guardrail_triggered`).
Zwei Wege: (a) Railway-Logs nach `guardrail_triggered` filtern (reason-Codes
inklusive), oder (b) aus einem Events-Export inferieren — ein getriggerter
Guardrail ersetzt die Antwort durch einen von 6 festen Fallback-Texten, und
`scripts/analyze_experiment_events.py` (unten) matcht genau diese Texte.

---

## 4. Mitgelieferte Skripte

Liegen in `.claude/skills/toadapt-diagnostics-and-tooling/scripts/`. Alle
drei wurden am 2026-07-08 getestet (Smoke-Test gegen lokal gestartetes
Backend, Analyse-Skripte gegen synthetische Minimaldaten — nie gegen echte
Teilnehmerdaten). Die Python-Skripte brauchen nur die Standardbibliothek
(Python 3.10+, wegen `X | None`-Typannotationen) und schreiben nichts.

### a) `smoke_backend.sh` — Ist die Instanz gesund und korrekt abgesichert?

```bash
# Lokal (Backend läuft auf Port 8000):
.claude/skills/toadapt-diagnostics-and-tooling/scripts/smoke_backend.sh http://localhost:8000 "$TOADAPT_API_KEY"

# Railway (Studenten-Zugangscode aktiv):
.claude/skills/toadapt-diagnostics-and-tooling/scripts/smoke_backend.sh \
  https://<app>.up.railway.app "$TOADAPT_API_KEY" "$STUDENT_ACCESS_CODE"
```

Prüft (nur GETs + zwei bewusst abgewiesene Requests, KEINE Daten, KEINE
LLM-Kosten): `/health` → 200; `/health/diagnostics` und
`/dashboard/overview` ohne Key → 401/503; `GET /admin/cases` → 200 (bewusst
öffentlich lesbar); `PATCH /admin/cases/...` ohne Key → 401/503;
`POST /sessions` auf nicht existenten Case → 404 (bzw. 401 bei aktivem
Access-Code ohne Code); mit Key: Diagnostics + Dashboard → 200 und Ausgabe
des Diagnostics-Payloads. Exit-Code 0 = alles grün. Verifizierter Lauf
(lokal, 2026-07-08): 8 PASS, 0 FAIL.

### b) `summarize_dashboard_results.py` — Submissions-Überblick ohne Mongo

```bash
# Datei-Fallback des Dashboards (lokale Entwicklung):
python3 .claude/skills/toadapt-diagnostics-and-tooling/scripts/summarize_dashboard_results.py backend/db/submissions/

# Oder ein Mongo-Export der Collection dashboard_results (JSON-Array):
python3 .claude/skills/toadapt-diagnostics-and-tooling/scripts/summarize_dashboard_results.py ~/ToAdapt_sensitive_data/dashboard_export.json
```

Liest die Result-JSONs, die `POST /submissions/{id}/submit` schreibt
(`backend/api/routes.py` → `dashboard_store.save_result`), und berichtet:
Anzahl Submissions, Ø `percentage` / `canvas_alignment_pct` /
`rubric_fit_pct`, Exemplar-Kandidaten, needs_human_review-Quote und
technical_fallback-Quote (gesamt und pro `question_id`). Testlauf mit 2
synthetischen Results (2026-07-08): korrekt 50 % review-Quote, 25 %
technical_fallback, q1/q4-Aufschlüsselung.

### c) `analyze_experiment_events.py` — Events-Export auswerten

```bash
python3 .claude/skills/toadapt-diagnostics-and-tooling/scripts/analyze_experiment_events.py \
  ~/ToAdapt_sensitive_data/events_export.json   # JSON-Array oder JSON-Lines
```

Berichtet: Event-Typ-Verteilung, Events pro Tag, Agent-Verteilung über
`chat_turn_completed`, Turns pro Session (Ø/Median/Max) und
**Guardrail-Trigger pro Tag** (inferiert über exakten Match der
`assistant_message` gegen die 6 eingebetteten Fallback-Texte aus
`backend/agents/orchestrator.py`). Achtung: ändern sich die Fallback-Texte
im Orchestrator, muss die Liste im Skript nachgezogen werden (das Skript
meldet 0 Treffer und weist selbst darauf hin). Testlauf mit 6 synthetischen
Events (2026-07-08): erkennt 1/3 Chat-Turns als Guardrail-Fallback,
verarbeitet ISO-Strings und Mongo-Extended-JSON (`$date`, `$numberLong`).

---

## 5. Frage → Werkzeug → Kommando

| Frage | Werkzeug | Kommando |
|---|---|---|
| Läuft die Instanz? Welcher Build? | /health + Diagnostics | `curl -s $BASE/health`; `build_marker` in Diagnostics |
| Ist Mongo konfiguriert/verbunden? | Diagnostics | `curl -s -H "X-API-Key: $KEY" $BASE/health/diagnostics` → `mongo_connection_mode`, `mongo_last_connection_failure` |
| Welche Env-Variablen sieht der Prozess wirklich? | Diagnostics + Startup-Log | `mongo_env_keys` / `*_len`-Felder; `toadapt_startup` im Log |
| Ist der Studenten-Flow offen? | Startup-Log / Diagnostics | Warnung `student_flow_open`; `student_access_code_configured` in `toadapt_startup` |
| Ist alles korrekt abgesichert (Auth, Statuscodes)? | Smoke-Test | `scripts/smoke_backend.sh $BASE $KEY` |
| Wie viele Tokens/Kosten verbrauchen wir? | Railway-Logs | Nach `llm_call_completed` filtern, `total_tokens` summieren |
| Warum wurde eine Agent-Antwort ersetzt? | Railway-Logs | Nach `guardrail_triggered` filtern → `reason`-Code (Tabelle in §2) |
| Wie viele Guardrail-Trigger pro Tag? | Logs oder Events-Export | Logs: `guardrail_triggered` zählen; offline: `scripts/analyze_experiment_events.py <export>` |
| Agent-Verteilung / Ø Turns pro Session? | Events-Export oder mongosh | `scripts/analyze_experiment_events.py <export>` bzw. Aggregations-Queries in §3 |
| Wie viele Submissions, Ø-Score, Review-/Fallback-Quote? | Result-JSONs | `scripts/summarize_dashboard_results.py backend/db/submissions/` |
| Scheitert der Judge am JSON? | Railway-Logs | `evaluation_json_parse_failed` / `evaluation_json_repair_failed` zählen; Quote via Skript (b) |
| Gehen Events verloren? | Railway-Logs | `mongo_log_connection_failed` / `mongo_log_failed` — Events haben KEINEN Datei-Fallback |
| Wer hat welchen Case freigegeben (und mit force)? | Railway-Logs | `case_approved` → Felder `reviewer`, `forced` |

Hinweis zu Dashboards: Die aggregierten Sichten gibt es auch als API —
`GET /dashboard/overview`, `/dashboard/students`,
`/dashboard/student/{matrikelnummer}`, `/dashboard/difficulties` (alle
X-API-Key; `backend/dashboard/routes.py`). Ohne Mongo und ohne lokale
Result-Dateien fällt das Dashboard auf einen Seed-Datensatz zurück
(`backend/db/dashboard_seed/…` — Pfad existiert im Working Tree derzeit
nicht, dann liefert es leere Listen).

---

## Provenance und Wartung

Erstellt: 2026-07-08 gegen Commit-Stand `141bb63` (main, HEAD nach dem
filter-repo-Rewrite vom 2026-07-08). Alle Pfade,
Felder, Event-Namen und Statuscodes am 2026-07-08 gegen den Code verifiziert;
Skripte am selben Tag mit synthetischen Daten bzw. lokalem Backend getestet.

Re-Verifikation drift-anfälliger Fakten (je ein Kommando, vom Repo-Root):

- Diagnostics-Felder: `grep -n 'mongo_' backend/main.py backend/db/experiment_logger.py`
- Log-Event-Inventar: `grep -rn 'logger\.\(info\|warning\|error\)(' backend --include='*.py' -A1 | grep '"'`
- Guardrail-reason-Codes: `grep -n 'return False' backend/agents/orchestrator.py`
- Guardrail-Fallback-Texte (müssen mit `scripts/analyze_experiment_events.py` übereinstimmen): `grep -n '_guardrail_fallback' -A 40 backend/agents/orchestrator.py`
- experiment_events-Event-Typen: `grep -n '_log_experiment_event(' backend/api/routes.py`
- Dashboard-Result-Schema (Input für Skript b): `grep -n 'out = {' -A 20 backend/api/routes.py`
- Endpoint-/Auth-Landkarte für den Smoke-Test: `grep -n '@router\|@app\.\|dependencies' backend/main.py backend/api/routes.py backend/admin/routes.py backend/dashboard/routes.py`
- Mongo-Collection-Namen: `grep -rn 'MONGODB_.*COLLECTION' backend/db/`
