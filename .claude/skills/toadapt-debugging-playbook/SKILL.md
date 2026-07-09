---
name: toadapt-debugging-playbook
description: >
  Symptom-zu-Ursache-Triage für die realen Failure-Modes des ToAdapt-Backends
  (FastAPI auf Railway) und -Frontends (Next.js auf Vercel). Lade diese Skill,
  wenn eines dieser Symptome auftritt: Deploy sieht Env-Variablen nicht /
  Konfiguration wirkt "leer"; MongoDB verbindet nicht oder Daten verschwinden
  nach Redeploy; HTTP 401 oder 503 auf Admin-/Dashboard-/Studenten-Endpunkten;
  HTTP 429 "Zu viele Anfragen"; Chat antwortet mit 404 "Session nicht
  gefunden"; der LLM-Judge liefert 0 Punkte mit evaluation_status
  "technical_fallback"; Submit schlägt komplett mit 503 fehl; 401 auf
  /dashboard/students trotz korrektem Tutor-Key (X-Research-Key nötig);
  429 "Denkanstoß-Limit erreicht"; Agent-Antworten werden scheinbar grundlos
  durch generische Fallback-Texte ersetzt (guardrail_triggered); CORS-Fehler
  im Browser; oder jemand will WebSockets (wieder) einführen. Schlüsselwörter:
  debugging, triage, 401, 503, 429, 404, CORS, Mongo, Railway, Nixpacks,
  dotenv, guardrail, technical_fallback, rate limit, WEB_CONCURRENCY,
  X-Research-Key, Denkanstoß.
---

# ToAdapt Debugging-Playbook

Dieses Playbook ordnet jedem beobachteten Symptom die wahrscheinlichen
Ursachen zu — mit einem **diskriminierenden Experiment** (ein Kommando, das
zwischen den Ursachen unterscheidet) statt Blind-Debugging. Jeder Failure-Mode
hier ist in diesem Projekt real aufgetreten.

## Wann diese Skill NICHT gilt

- **Umgebung von Null aufbauen / Installationsprobleme** → `toadapt-build-and-env`
- **App starten, deployen, Forschungs-Skripte bedienen** → `toadapt-run-and-operate`
- **Katalog aller Env-Variablen und Schwellwerte** → `toadapt-config-and-flags`
- **Diagnostics-Endpoint/Log-Events systematisch nutzen (Messen statt Schätzen)** → `toadapt-diagnostics-and-tooling`
- **Vollständige Chronik der historischen Vorfälle mit Commits** → `toadapt-failure-archaeology`
- **q4/Bloom-6-Judge bewertet systematisch zu streng (Alignment-Problem, kein technischer Defekt)** → `toadapt-judge-alignment-campaign`
- **Bevor du einen Fix committest** → `toadapt-change-control` (Klassifikation und Gates)

## Basis-Setup für alle Experimente

Kontext in einem Satz: ToAdapt ist ein FastAPI-Backend (Railway) + Next.js-
Frontend (Vercel); Studierende chatten mit 4 Scaffolding-Agenten über einen
Business-Case und reichen Freitext-Antworten ein, die ein LLM-Judge bewertet.

Führe alle lokalen Kommandos **vom Repo-Root** aus. Setze zuerst:

```bash
# Für Produktions-Diagnose: Railway-Backend-URL und den Shared-Secret-Key
export API_URL="http://localhost:8000"        # oder https://<railway-app>.up.railway.app
export TOADAPT_API_KEY="<wert-aus-railway-env>"
```

Die zwei wichtigsten Werkzeuge (Details in `toadapt-diagnostics-and-tooling`):

```bash
# 1. Lebt der Prozess überhaupt? (öffentlich, bewusst minimal)
curl -s "$API_URL/health"

# 2. Was sieht der Prozess wirklich? (API-Key-geschützt; zeigt Mongo-Status,
#    Env-Key-Namen mit Längen, TP-Phase, Build-Marker)
curl -s -H "X-API-Key: $TOADAPT_API_KEY" "$API_URL/health/diagnostics" | python3 -m json.tool
```

Log-Events sind structlog-Events (JSON, wenn `ENVIRONMENT=production`).
Auf Railway: `railway logs` (UNVERIFIZIERT, ob CLI im Projekt eingerichtet
ist — notfalls Railway-Web-UI → Deployments → Logs).

## Symptom→Triage-Tabelle

| # | Symptom | Wahrscheinliche Ursache | Diskriminierendes Experiment | Fix-Verweis |
|---|---------|------------------------|------------------------------|-------------|
| A | Deploy verhält sich, als wären Env-Vars leer | Env-Var in Railway nicht gesetzt / Tippfehler im Namen; historisch: dotenv/Nixpacks-Konflikt | `GET /health/diagnostics` → `mongo_env_keys` + `*_len`-Felder; Startup-Log `toadapt_startup` | Abschnitt A |
| B | Mongo-Daten fehlen, `mongo_logging_enabled: false`, Daten weg nach Redeploy | URI nicht auflösbar ODER Verbindung schlägt fehl (2s-Timeout, dann 30s-Backoff) | `/health/diagnostics`: `mongo_has_uri` vs. `mongo_last_connection_failure` unterscheiden | Abschnitt B |
| C | 503 "Auth nicht konfiguriert" | `TOADAPT_API_KEY` im Backend leer (fail-closed by design) | Diagnostics-Call schlägt selbst mit 503 fehl → Key serverseitig nicht gesetzt | Abschnitt C |
| C | 401 auf Admin/Dashboard | Falscher/fehlender `X-API-Key` (Frontend-Proxy ≠ Backend-Key) | `curl` mit Key direkt gegen Backend; Frontend-`TOADAPT_API_KEY` vergleichen | Abschnitt C |
| C | 401 auf Studenten-Endpunkten | `STUDENT_ACCESS_CODE` gesetzt, Header fehlt/falsch | `POST /auth/student/verify` mit/ohne Header | Abschnitt C |
| C | 401 auf `/dashboard/students` & Co. MIT gültigem Tutor-Key | Endpunkt verlangt den Research-Key (`X-Research-Key`) — Tutor-Key reicht dort GEWOLLT nicht | Detail-Text lesen: "Ungültiger oder fehlender Forschungs-Key" (401) vs. "Forschungs-Zugang nicht konfiguriert" (503) | Abschnitt C |
| C | Teacher-Seiten werfen nach Stunden auf Login zurück | Teacher-Cookie läuft nach 12h ab (by design) | Cookie-Alter prüfen; erneut einloggen | Abschnitt C |
| D | Client bekommt 429 | Eigener In-Process-Rate-Limiter (pro Worker!) ODER Denkanstoß-Limit (2 pro Frage) | Detail-Text: "Zu viele Anfragen" + `Retry-After` = Limiter; "Denkanstoß-Limit für diese Frage erreicht" = Feedback-Kontingent | Abschnitt D |
| D | Chat gibt 503 "Assistent nicht erreichbar" | OpenRouter-Fehler (auch deren 429) nach SDK-Retries | Log `chat_error` mit `type=` prüfen | Abschnitt D |
| E | Chat: 404 "Session nicht gefunden" mitten im Gespräch | `WEB_CONCURRENCY > 1` ohne funktionierendes Mongo (Sessions nur im Worker-RAM) | Diagnostics: `mongo_logging_enabled` + Railway-Var `WEB_CONCURRENCY` prüfen | Abschnitt E |
| F | Score 0, `evaluation_status: "technical_fallback"` | Judge-JSON unparsebar (auch nach Repair) ODER valides JSON mit typ-ungültigen Zahlen | Logs `evaluation_json_parse_failed` / `evaluation_json_repair_failed` / `evaluation_payload_invalid_types` | Abschnitt F |
| F | Submit schlägt komplett mit 503 fehl ("Auswertung gerade nicht möglich") | Fragen werden PARALLEL bewertet; ein Fragen-Fehler bricht den ganzen Submit ab (Antworten bleiben gespeichert, Retry ok) | Log `evaluation_error` mit `type=` | Abschnitt F |
| G | Agent antwortet mit generischem Fallback-Text | Guardrail hat die echte Antwort KOMPLETT ersetzt | Log `guardrail_triggered` mit `reason=`; lokal `guardrail_check()` reproduzieren | Abschnitt G |
| H | Browser: CORS-Fehler | `ALLOWED_ORIGINS` falsch/leer in Prod — ODER ein 500 maskiert als CORS-Fehler | `curl -i` mit `Origin`-Header; Preflight prüfen | Abschnitt H |
| I | "Lass uns WebSockets nutzen" | Verlorene Schlacht gegen den Railway-Proxy | NICHT anfangen ohne neuen Beweis | Abschnitt I |

---

## A. Deploy sieht Env-Vars nicht

**Geschichte (Warnung):** Am 2026-04-30 überschrieb die dotenv/Nixpacks-
Kombination die Railway-Env-Vars — Commit `783bb5c` entfernte damals
python-dotenv komplett. Heute ist dotenv **wieder drin**, aber entschärft:

- `backend/main.py:14` ruft `load_dotenv(<repo-root>/.env)` **vor** allen
  Backend-Imports auf (deshalb die absichtlichen `E402`-Ignores in
  `pyproject.toml` für `backend/main.py` und `backend/db/submission_store.py`
  — nicht "aufräumen"!).
- `load_dotenv` läuft mit Default `override=False`: **echte Prozess-Env-Vars
  (Railway) gewinnen immer** über die `.env`-Datei. Auf Railway existiert
  ohnehin keine `.env` (nicht committed).

**Experiment 1 — was sieht der Prozess?**

```bash
curl -s -H "X-API-Key: $TOADAPT_API_KEY" "$API_URL/health/diagnostics" | python3 -m json.tool
```

Prüfe: `mongo_env_keys` (Liste der tatsächlich gesetzten `MONGODB_*`-Namen)
und die Längenfelder `mongodb_uri_len`, `mongodb_host_len`,
`mongodb_mas_name_len`, `mongodb_mas_key_len`. Länge 0 = Variable ist im
Prozess **nicht** angekommen (Tippfehler im Namen? Falscher Railway-Service?
Redeploy nach Variablen-Änderung vergessen?).

**Experiment 2 — Startup-Log:** Das Event `toadapt_startup` (in den
Railway-Logs direkt nach dem Start) loggt boolesche Konfigurationszustände:
`openrouter_api_key_configured`, `mongo_logging_enabled`,
`student_access_code_configured`, `sentry_enabled`. Bewusst keine Key-Werte.

**Fix:** Variable in Railway (richtiger Service!) setzen, Redeploy auslösen,
Experiment 1 wiederholen. Katalog aller Variablen: `toadapt-config-and-flags`.

## B. Mongo verbindet nicht

**Geschichte (Warnung):** Die Mongo-Saga vom 2026-05-14 (Commits `7367767` …
`dbc92f2`) war tagelanges Blind-Debugging gegen Railway per Deploy-Marker-Bumps
— das Relikt `BUILD_MARKER = "railway-mongo-env-diagnostics-2026-05-14-1809z"`
steht noch in `backend/main.py`. Der Lerneffekt daraus IST der heutige
`/health/diagnostics`-Endpoint. **Nutze ihn, bumpe keine Marker.**

**Verhalten der Stores (`backend/db/mongo.py`):**

- `MongoClient(..., serverSelectionTimeoutMS=2000)` — 2 Sekunden Timeout.
- Nach einem Verbindungsfehler: **30 Sekunden Backoff**, in denen
  `get_collection()` sofort `None` liefert (Log-Event
  `mongo_connection_failed`). Die App läuft weiter, schreibt aber nicht.
- Ohne Mongo: `session_store` hat **keinen** Datei-Fallback (Sessions nur im
  Prozess-RAM); `submission_store` fällt auf Dateien unter
  `backend/db/runtime_submissions/` zurück. Railway-Dateisystem ist
  **ephemer** — Datei-Fallback-Daten sind nach jedem Redeploy weg.

**Diskriminierendes Experiment:**

```bash
curl -s -H "X-API-Key: $TOADAPT_API_KEY" "$API_URL/health/diagnostics" | python3 -m json.tool
```

| Befund | Diagnose |
|--------|----------|
| `mongo_has_uri: false`, `mongo_env_keys` leer/lückenhaft | Konfigurationsproblem → Abschnitt A |
| `mongo_has_uri: true`, `mongo_last_connection_failure` gefüllt | Verbindungsproblem: Atlas-IP-Allowlist (Railway-Egress-IPs), falsche Credentials, falscher Host |
| `mongo_logging_enabled: true` und kein Failure | Mongo ok — Problem liegt woanders |

URI-Auflösung (`backend/db/mongo.py::resolve_uri`): `MONGODB_URI` gewinnt;
sonst wird aus `MONGODB_MAS_NAME` + `MONGODB_MAS_KEY` +
(`MONGODB_HOST`|`MONGODB_CLUSTER_HOST`|`MONGODB_CLUSTER`) eine
`mongodb+srv://`-URI gebaut. **Alle drei** MAS-Teile müssen gesetzt sein,
sonst ist die URI leer und Mongo gilt als "nicht konfiguriert".

Lokaler Schnelltest (vom Repo-Root, liest `.env`):

```bash
.venv/bin/python -c "from backend.db import mongo; print('enabled:', mongo.mongo_enabled()); print('uri set:', bool(mongo.resolve_uri()))"
```

## C. 401/503 — die vier Auth-Schichten

Es gibt **vier getrennte** Auth-Mechanismen. Verwechslung ist die häufigste
Fehlbedienung.

| Schicht | Header/Mechanismus | Schützt | Wenn unkonfiguriert | Wenn falsch |
|---------|-------------------|---------|---------------------|-------------|
| API-Key (`backend/auth.py::require_api_key`) | `X-API-Key` = `TOADAPT_API_KEY` | Alle `/dashboard/*`, schreibende `/admin/*`, `/health/diagnostics` | **503** "Auth nicht konfiguriert" (fail-closed, absichtlich!) | **401** "Ungültiger oder fehlender API-Key" |
| Research-Key (`backend/auth.py::require_research_key`) | `X-Research-Key` = `RESEARCH_API_KEY` | ZUSÄTZLICH zum API-Key: `/dashboard/students`, `/dashboard/student/{m}`, `/dashboard/difficulties` (Einzelpersonen-Daten) | **503** "Forschungs-Zugang nicht konfiguriert" (fail-closed) | **401** "Ungültiger oder fehlender Forschungs-Key" |
| Studenten-Code (`require_student_access`) | `X-Student-Access-Code` = `STUDENT_ACCESS_CODE` | ALLE Studenten-Routen (`/sessions`, `/submissions`, …) | Flow ist **offen** (Dev-/Prolific-Modus; Startup-Log warnt mit `student_flow_open`) | **401** "Ungültiger oder fehlender Zugangscode" |
| Teacher-Cookie (`frontend/lib/teacherAuth.ts`) | Signiertes httpOnly-Cookie, HMAC-SHA256 mit `TEACHER_SESSION_SECRET` | Teacher-Frontend-Seiten | Login unmöglich | Redirect zum Login; Cookie läuft nach **12 h** ab (`MAX_AGE_SECONDS = 12 * 60 * 60`) |

**Merksatz: 503 auf einer geschützten Route heißt "Server-Env kaputt"
(Key fehlt serverseitig), 401 heißt "Client schickt den falschen Wert".**

**Kein Bug, sondern Design (seit 2026-07-09):** 401 auf den
Einzelpersonen-Endpunkten trotz korrektem `TOADAPT_API_KEY` ist **gewollt**.
Der Teacher-Proxy des Frontends kennt nur `TOADAPT_API_KEY` — Tutor:innen
erreichen Einzelprofile damit auch technisch nicht und sehen nur
Gruppen-Aggregate (`/dashboard/groups`, `/dashboard/groups/{code}`, nur
API-Key). Der Research-Key ist bewusst ein anderer Key und wird nur
Forschenden gegeben. Nichts "reparieren".

Diskriminierende Experimente:

```bash
# 503? -> TOADAPT_API_KEY ist im BACKEND nicht gesetzt.
# 401? -> Dein Key stimmt nicht mit dem Backend-Key überein.
# 200? -> Auth ok.
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: $TOADAPT_API_KEY" "$API_URL/health/diagnostics"

# Studenten-Code prüfen (nur relevant, wenn STUDENT_ACCESS_CODE gesetzt ist):
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$API_URL/auth/student/verify" \
  -H "X-Student-Access-Code: <code>"
```

Sonderfall Teacher-Dashboard zeigt 401/503, obwohl dein direkter `curl`
funktioniert: Der Browser spricht das Backend **nie direkt** an — Teacher-
API-Calls laufen über den Next.js-Proxy
`frontend/app/api/teacher/[...path]/route.ts`, der server-seitig
`X-API-Key` aus der **Frontend**-Env-Var `TOADAPT_API_KEY` ergänzt und
`BACKEND_API_URL` als Ziel nutzt. Prüfe also: Ist `TOADAPT_API_KEY` in
Vercel identisch mit dem in Railway? Zeigt `BACKEND_API_URL` auf das
richtige Backend?

Frontend-Detail Studenten-Flow: Der Code wird aus
`sessionStorage.getItem('student_access_code')` gelesen
(`frontend/lib/api.ts`) — neuer Tab/Browser = Code erneut eingeben.

## D. 429 — eigener Rate-Limiter vs. Denkanstoß-Limit vs. OpenRouter

**Entscheidungsregel: Ein 429, das der Client sieht, kommt IMMER aus dem
eigenen Backend — entweder vom Rate-Limiter oder (seit 2026-07-09) vom
Denkanstoß-Limit. Der Detail-Text unterscheidet:**

| Detail-Text | Quelle | Charakter |
|-------------|--------|-----------|
| `"Zu viele Anfragen — bitte einen Moment warten."` + `Retry-After`-Header | `backend/ratelimit.py` (Sliding Window) | Transient — kurz warten |
| `"Denkanstoß-Limit für diese Frage erreicht — nutzt den Lernchat für offene Fragen."` (kein `Retry-After`) | `POST /submissions/{id}/questions/{qid}/feedback`: max. **2 Denkanstöße pro Frage** (`MAX_FEEDBACK_PER_QUESTION` in `backend/evaluator/formative_feedback.py`) | Kontingent aufgebraucht — by design, warten hilft NICHT |

OpenRouter-429er werden vom OpenAI-SDK intern retried
(`LLM_MAX_RETRIES`, Default 2, `backend/llm.py`); bleibt der Fehler, fängt
der Chat-Endpunkt die Exception und antwortet mit **503** "Der Assistent ist
gerade nicht erreichbar…" (`backend/api/routes.py`, Log-Event `chat_error`
mit `type=<ExceptionKlasse>`, z. B. `RateLimitError`). Analog beim
Denkanstoß-Endpunkt: LLM-Fehler → **503** "Der Denkanstoß ist gerade nicht
verfügbar…" (Log-Event `formative_feedback_error`).

Erkennungsmerkmale des eigenen Limiters (`backend/ratelimit.py`):
Detail-Text `"Zu viele Anfragen — bitte einen Moment warten."` und ein
`Retry-After`-Header.

Limits (definiert als Dependencies in `backend/api/routes.py`, Stand 2026-07-09):

| Endpoint | Limit | Schlüssel |
|----------|-------|-----------|
| `POST /auth/student/verify` | 10/min | Client-IP |
| `POST /sessions` | 20/min | Client-IP |
| `POST /sessions/{id}/chat` | 15/min | `session_id` |
| `POST /submissions` | 20/min | Client-IP |
| `POST /submissions/{id}/answer` | 60/min | `submission_id` |
| `POST /submissions/{id}/questions/{qid}/coverage` | 30/min | `submission_id` |
| `POST /submissions/{id}/questions/{qid}/feedback` | 5/min (plus 2-pro-Frage-Kontingent, s.o.) | `submission_id` |
| `POST /submissions/{id}/submit` | 5/min | `submission_id` |

**Zwei eingebaute Fallen:**

1. **Pro Worker, nicht global:** Sliding-Window im Prozess-Speicher. Bei
   `WEB_CONCURRENCY=N` ist das effektive Limit bis zu N-mal höher — bewusst
   akzeptiert (Kostenbremse, keine exakte Quote).
2. **IP-basierte Limits + Campus-NAT:** Viele Studierende hinter einer IP
   teilen sich die IP-Limits (`/sessions`!). Die per-Ressource-Limits
   (`session_id`/`submission_id`) sind davon nicht betroffen. IP-Erkennung
   setzt `--proxy-headers` voraus (steht im `railway.toml`-startCommand).

Reproduktion lokal (16. Chat-Call in einer Minute muss 429 liefern):

```bash
for i in $(seq 1 16); do curl -s -o /dev/null -w "%{http_code} " -X POST \
  "$API_URL/sessions/<session_id>/chat" -H 'Content-Type: application/json' \
  -d '{"content":"test","history":[]}'; done; echo
```

## E. Chat-404 "Session nicht gefunden"

**Symptom:** Session erstellen funktioniert, aber ein späterer
`POST /sessions/{id}/chat` liefert 404 — oft nur sporadisch.

**Ursache:** Sessions liegen in einem **prozesslokalen Dict**
(`_sessions` in `backend/api/routes.py`); persistiert wird nur nach Mongo
(`backend/db/session_store.py` — **kein** Datei-Fallback). Ohne
funktionierendes Mongo und mit `WEB_CONCURRENCY > 1` landet der Chat-Request
per Load-Balancing bei einem Worker, der die Session nie gesehen hat → 404.
Genau davor warnt der Kommentar in `railway.toml`:

> WEB_CONCURRENCY > 1 erst setzen, wenn MongoDB in der Umgebung verifiziert läuft.

**Diskriminierendes Experiment:**

```bash
# 1. Ist Mongo wirklich aktiv?
curl -s -H "X-API-Key: $TOADAPT_API_KEY" "$API_URL/health/diagnostics" | python3 -c "import json,sys; d=json.load(sys.stdin); print('mongo:', d['mongo_logging_enabled'], '| last_failure:', d['mongo_last_connection_failure'])"
# 2. Wie viele Worker? -> Railway-Env-Var WEB_CONCURRENCY prüfen (Default 1).
```

`mongo: False` (oder ein Failure) **und** `WEB_CONCURRENCY > 1` = Diagnose
bestätigt.

**Fix:** Entweder `WEB_CONCURRENCY=1` setzen ODER Mongo reparieren
(Abschnitt B) — erst danach wieder hochskalieren. Dieselbe Regel gilt bei
Neustarts: ohne Mongo verliert auch ein einzelner Worker beim Redeploy alle
laufenden Sessions.

## F. Judge liefert technical_fallback

**Symptom:** Eine Frage bekommt 0 Punkte, `evaluation_status:
"technical_fallback"`, `needs_human_review: true`, `score_band: "unscored"`.
Das ist **kein** inhaltliches Urteil — die Antwort wurde nie bewertet.

**Mechanik** (`backend/evaluator/rubric_evaluator.py`, historisch die
instabilste Komponente — Härtung in Commit `4dd79da`):

1. Judge-Call (max_tokens 1200, Konstante `EVALUATOR_MAX_TOKENS`) muss
   reines JSON liefern.
2. Parsing versucht 3 Kandidaten: Rohtext → ohne Code-Fences → Substring vom
   ersten `{` bis zum letzten `}` (Modul-Funktionen
   `extract_json_candidates`/`parse_evaluation_payload`).
3. Scheitern alle drei: **ein** Repair-LLM-Call (`REPAIR_PROMPT`), erneutes
   Parsing.
4. Scheitert auch das: `_fallback_payload` mit 0 Punkten.
5. NEU (2026-07-09): Auch **valides JSON mit typ-ungültigen Zahlen**
   (z. B. `awarded_points: "acht"` → `TypeError`/`ValueError` beim Casten)
   landet im technical_fallback statt in einem 500 (Log-Event
   `evaluation_payload_invalid_types`, error).

**Log-Kette (Reihenfolge = Diagnose):**

```
evaluation_json_parse_failed      (warning, mit raw_preview der ersten 500 Zeichen)
evaluation_json_repair_failed     (error — erst jetzt entsteht der Fallback)
evaluation_payload_invalid_types  (error — JSON ok, Typen unbrauchbar → Fallback)
```

Nur das erste Event ohne das zweite = Repair hat gegriffen, kein Fallback.
Prüfe `raw_preview`: abgeschnittenes JSON (Token-Limit?), Prosa statt JSON
(Modellwechsel via `OPENROUTER_MODEL`?), leere Antwort (Provider-Störung?).

**Verwandtes Symptom — Submit schlägt komplett mit 503 fehl:** Seit
2026-07-09 bewertet `evaluate_submission` alle Fragen **parallel**
(`asyncio.gather`, Reihenfolge stabil). Wirft die Bewertung **einer** Frage
eine Exception (z. B. OpenRouter-Ausfall), bricht der ganze Submit ab und
der Endpunkt antwortet 503 "Die Auswertung ist gerade nicht möglich. Eure
Antworten sind gespeichert…" (Log-Event `evaluation_error` mit `type=`).
Die Antworten sind gespeichert — **erneutes Submitten ist der Fix**, nichts
geht verloren. Nicht mit technical_fallback verwechseln: Beim Fallback kommt
der Submit durch (mit 0-Punkte-Frage), beim 503 kommt er gar nicht durch.

**Nachträglich reparieren** — es gibt ein Skript, das gezielt NUR die
technical_fallback-Scores neu bewertet (echte LLM-Calls, kostet Geld;
Alignment-Regeln beachten → `toadapt-change-control`):

```bash
# Erst trocken:
PYTHONPATH=. .venv/bin/python scripts/retry_technical_fallback_scores.py --dry-run
# Dann gezielt:
PYTHONPATH=. .venv/bin/python scripts/retry_technical_fallback_scores.py --submission-id <id>
```

Default-Quelle sind die Dashboard-JSONs unter `backend/db/submissions/`
(überschreibbar mit `--dashboard-dir`). `PYTHONPATH=.` ist nötig, sonst
`ModuleNotFoundError: No module named 'backend'`.

## G. Guardrail ersetzt Antworten scheinbar grundlos

**Symptom:** Der Agent antwortet mit einem immer gleichen, generischen Text
("Ich bleibe hier lieber bei der Denkstruktur…"). Das ist der
Guardrail-Fallback: Bei einem Treffer wird die LLM-Antwort **komplett**
durch einen festen Text ersetzt (`_guardrail_fallback` in
`backend/agents/orchestrator.py`), nicht umformuliert. Dasselbe Muster gilt
seit 2026-07-09 für den Denkanstoß: `generate_formative_feedback`
(`backend/evaluator/formative_feedback.py`) prüft die LLM-Antwort mit
demselben `guardrail_check` und fällt bei Verstoß auf eine feste Frage
zurück. (Pädagogische Qualitätsbewertung der Tutor-Antworten →
`toadapt-tutor-response-evaluation`.)

**Prüfreihenfolge von `guardrail_check(text, tp)`** (erste Verletzung
gewinnt; `reason` steht im Log-Event `guardrail_triggered`, Level warning):

| Reihenfolge | Prüfung | `reason`-Präfix |
|---|---|---|
| 1 | TP-spezifische `forbidden_framework_names` aus `TP_CONFIGS[tp]` | `framework_name_dropped: <name>` |
| 2 | `FORBIDDEN_PATTERNS` (direkte Antworten + harte Namen: porter, five forces, rbv, vrio, 4p, tce, preiselastizität, …) | `direct_answer_pattern: <pattern>` |
| 3 | `SLANG_PATTERNS` (haha, diggi, …) | `style_contains_slang` |
| 4 | Emoji (jedes Zeichen mit Unicode-Kategorie `So`) | `style_contains_emoji` |
| 5 | `RECOMMENDATION_PATTERNS` + 7 Regexe (direkte Empfehlungen) | `direct_recommendation_or_template` |
| 6 | `CASE_SPECULATION_PATTERNS` (finma, microsoft, azure switzerland, …) | `case_speculation_outside_context` |

**Bekannte Überraschungen:**

- Alles sind **Substring-Matches auf lowercase** — kurze Patterns wie `4p`
  oder `tce` können in harmlosen Wörtern zünden.
- `microsoft` in Punkt 6 feuert, sobald das LLM den Anbieter auch nur
  erwähnt — gewollt (Anti-Spekulation), wirkt aber "grundlos".
- **TP4 hat keinen `forbidden_framework_names`-Key** in
  `backend/config/tp_configs.py` (Zugriff via `.get(..., [])`) — dort greifen
  nur die globalen Patterns. Bekannte, vermutlich unbeabsichtigte Lücke,
  weiterhin offen (re-verifiziert 2026-07-09).

**Diskriminierendes Experiment 1 — Logs:** Suche `guardrail_triggered` in
den Backend-Logs; das Feld `reason` benennt Prüfung und Pattern exakt.

**Diskriminierendes Experiment 2 — lokal reproduzieren** (vom Repo-Root,
kein LLM-Call, reine Textprüfung):

```bash
.venv/bin/python -c "
from backend.agents.orchestrator import guardrail_check
print(guardrail_check('<verdächtiger Antworttext hier>', 1))  # (True,'') = ok
"
```

**Fix-Hinweis:** Pattern-Änderungen sind Lehrdesign-relevant (Anti-Answer-
Giving ist ein hartes Constraint) → vor jeder Lockerung
`toadapt-change-control` lesen. Ein zu scharfes Pattern entschärfen ist ok;
Guardrails abschalten ist es nie.

## H. CORS-Fehler

**Symptom:** Browser-Konsole meldet "blocked by CORS policy"; `curl` gegen
dieselbe URL funktioniert.

**Konfiguration** (`backend/main.py::_allowed_origins`): `ALLOWED_ORIGINS`
(kommagetrennt, exakte Origins mit Schema, ohne trailing slash). Leer →
Fallback NUR `http://localhost:3000` und `http://127.0.0.1:3000`. Wegen
`allow_credentials=True` ist Wildcard `*` unzulässig — die Prod-Frontend-
Domain MUSS explizit drinstehen.

**Zwei Ursachen auseinanderhalten:**

1. **Echtes CORS-Problem:** Origin fehlt in `ALLOWED_ORIGINS` (typisch nach
   Vercel-Domain-Wechsel oder bei Preview-Deployments mit eigener Domain).
2. **Maskierter Serverfehler:** Historisch tauchten 500er als CORS-Fehler
   auf, weil Fehlerantworten ohne CORS-Header rausgingen (Commits `7bb936e`,
   `dca2da5`); heute fängt ein globaler Exception-Handler das ab. Trotzdem:
   Bei "CORS-Fehler" immer auch den **Status-Code** im Network-Tab prüfen.

**Diskriminierendes Experiment:**

```bash
# Preflight simulieren — steht die Frontend-Domain im Response-Header?
curl -si -X OPTIONS "$API_URL/sessions" \
  -H "Origin: https://<frontend-domain>" \
  -H "Access-Control-Request-Method: POST" | grep -i "access-control\|HTTP/"
```

Kein `access-control-allow-origin` in der Antwort → Ursache 1: Origin in
Railway-Var `ALLOWED_ORIGINS` ergänzen, Redeploy. Header vorhanden, Fehler
bleibt → Ursache 2: eigentlichen Fehler (Status/Logs) jagen.

## I. FALLE: WebSockets über Railway — nicht wieder anfangen

Das Chat-Interface lief ursprünglich über WebSockets und wurde nach einer
verlorenen Schlacht gegen den Railway-Proxy auf HTTP POST umgestellt
(Commits `17323ad` → `304af9b` → Kapitulation `e2cc925` "replace WebSocket
with HTTP POST chat (Railway WS compatibility)", 2026-04-30). Details der
Schlacht: `toadapt-failure-archaeology`.

- Das Feld `websocket_url` in `SessionResponse`
  (`backend/models/session.py`, befüllt in `backend/api/routes.py`) ist ein
  **totes Relikt** — es gibt keinen
  `/ws/…`-Endpunkt. Nicht darauf bauen, nicht "reparieren".
- Wer Echtzeit-Features will, braucht zuerst einen dokumentierten Beweis,
  dass WS über den aktuellen Railway-Proxy stabil läuft (Spike außerhalb des
  Produkts), und dann den Weg über `toadapt-change-control`. Bis dahin:
  HTTP POST ist die Architekturentscheidung (`toadapt-architecture-contract`).

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle Pfade, Kommandos, Limits und Log-Event-Namen wurden
am 2026-07-08 gegen den Repo-Stand auf main verifiziert; die lokalen
Python-Repro-Kommandos wurden ausgeführt.

Update 2026-07-09 (HEAD 64b62f9): Vierte Auth-Schicht Research-Key
(X-Research-Key/RESEARCH_API_KEY, Einzelpersonen-Dashboards, Tutor-401
gewollt); 429-Quelle Denkanstoß-Limit (MAX_FEEDBACK_PER_QUESTION=2) plus
neue Rate-Limits coverage 30/min + feedback 5/min; technical_fallback auch
bei typ-ungültigen Zahlen (evaluation_payload_invalid_types); Submit
bewertet parallel, ein Fragen-Fehler → 503 (evaluation_error);
Guardrail-Fallback auch im Denkanstoß; TP4-Guardrail-Lücke re-verifiziert
(weiterhin offen). Testbestand: 90 pytest-Tests grün (2026-07-09).

Re-Verifikation drift-anfälliger Fakten:

| Fakt | Re-Verifikations-Kommando (vom Repo-Root) |
|------|-------------------------------------------|
| Rate-Limits pro Endpoint | `grep -n "rate_limit(" backend/api/routes.py` |
| Research-Key-Endpunkte + 503/401-Texte | `grep -n "require_research_key" backend/dashboard/routes.py && grep -n "Forschungs" backend/auth.py` |
| Denkanstoß-Limit 2/Frage + 429-Text | `grep -n "MAX_FEEDBACK_PER_QUESTION\|Denkanstoß-Limit" backend/api/routes.py backend/evaluator/formative_feedback.py` |
| Parallel-Submit + Typ-Fallback | `grep -n "asyncio.gather\|evaluation_payload_invalid_types" backend/evaluator/rubric_evaluator.py` |
| Mongo-Timeout 2s / Backoff 30s | `grep -n "serverSelectionTimeoutMS\|< 30" backend/db/mongo.py` |
| 503-fail-closed / 401-Texte | `grep -n "503\|401\|HTTPException" backend/auth.py` |
| Teacher-Cookie 12h | `grep -n "MAX_AGE_SECONDS" frontend/lib/teacherAuth.ts` |
| Guardrail-Prüfreihenfolge | `sed -n '113,133p' backend/agents/orchestrator.py` |
| TP4 ohne forbidden_framework_names | `grep -n "forbidden_framework_names" backend/config/tp_configs.py` |
| Judge-Fallback-Kette | `grep -n "evaluation_json_parse_failed\|evaluation_json_repair_failed\|technical_fallback" backend/evaluator/rubric_evaluator.py` |
| Retry-Skript-Flags | `PYTHONPATH=. .venv/bin/python scripts/retry_technical_fallback_scores.py --help` |
| dotenv-Ladereihenfolge + E402 | `sed -n '1,20p' backend/main.py && grep -n "E402" pyproject.toml` |
| Diagnostics-Felder | `sed -n '148,167p' backend/main.py` |
| WEB_CONCURRENCY-Warnung | `cat railway.toml` |
| Historische Commits (A, F, I) | `git log --oneline --all \| grep -E "783bb5c\|e2cc925\|4dd79da\|dbc92f2"` |
| Kein /ws-Endpunkt | `grep -rn "websocket" backend/ --include='*.py'` |
