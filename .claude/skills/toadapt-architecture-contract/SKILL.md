---
name: toadapt-architecture-contract
description: >
  Lade diese Skill, BEVOR du in ToAdapt eine Architektur-Entscheidung triffst,
  hinterfragst oder versehentlich rückgängig machst. Trigger: du willst
  WebSockets/Streaming einführen; du fragst dich, wo Chat-History oder
  Session-State liegt; du willst einen neuen Store/eine neue Collection bauen;
  du änderst Auth (X-API-Key, Student-Access-Code, Teacher-Cookie, Proxy);
  du änderst Guardrails oder wunderst dich, warum eine Agent-Antwort komplett
  ersetzt wurde; du fragst "warum ist das so gebaut?"; du suchst die Liste
  der Invarianten oder der bekannten offenen Schwachstellen (kein
  Gruppenkonzept, target_tp hartkodiert, Keyword-Routing, TP4-Lücke).
  Enthält: Ist-Architektur-Diagramm, die 3 Auth-Pfade, 6 tragende
  Entscheidungen mit WARUM+Commit-Beleg, harte Invarianten, ehrliche
  Schwachstellenliste.
---

# ToAdapt — Architecture Contract

Dieses Dokument ist der Vertrag über die tragenden Designentscheidungen des
Repos. Wer eine dieser Entscheidungen ändern will, geht über die Skill
`toadapt-change-control` — nicht an ihr vorbei.

**Begriffsklärung (einmalig):** ToAdapt ist ein Transfer-Trainer für den
BWL-A-Kurs der Uni St.Gallen: Studierende bearbeiten individuell AI-generierte
Mini-Business-Cases (Case lesen → Chat mit 4 Scaffolding-Agenten →
Freitext-Antworten → LLM-Judge bewertet → Teacher-Dashboard).
"Scaffolding" = Lernbegleitung durch Fragen statt Antworten. "TP" =
Touchpoint, eine von 4 Kursphasen. "Judge" = LLM-Rubric-Evaluator, der
Antworten bepunktet.

## Wann diese Skill NICHT gilt

| Du willst… | Nimm stattdessen |
|---|---|
| eine Änderung klassifizieren/freigeben | `toadapt-change-control` |
| einen konkreten Bug triagieren | `toadapt-debugging-playbook` |
| wissen, welcher Fehler schon mal passiert ist | `toadapt-failure-archaeology` |
| Env-Variablen/Magic Numbers nachschlagen | `toadapt-config-and-flags` |
| die Umgebung aufsetzen oder deployen | `toadapt-build-and-env`, `toadapt-run-and-operate` |
| BWL-Didaktik verstehen (Bloom, TPs, Canvas) | `bwl-scaffolding-reference` |
| das q4/Bloom-6-Judge-Problem angehen | `toadapt-judge-alignment-campaign` |
| Tests/Evidenz-Standards | `toadapt-validation-and-qa` |

**ACHTUNG Fossil:** Die `CLAUDE.md` im Repo-Root beschreibt eine verworfene
Gruppen-Echtzeit-Architektur (WebSocket-Gruppenchat, GroupMemory, RAG) —
verworfen am 2026-04-30 (Commit `8df4cfd`). Diese Skill beschreibt den
IST-Zustand. Bei Widerspruch gilt diese Skill bzw. der Code.

---

## 1. Ist-Architektur (Stand: 2026-07-08)

```
  Browser (Studierende + Lehrkraft)
      │
      ├── Studenten-Flow ────────────────────────────────┐
      │   fetch direkt an Railway (NEXT_PUBLIC_API_URL)  │
      │   Header: X-Student-Access-Code (optional)       │
      │                                                  ▼
      │                                    ┌──────────────────────────┐
  ┌───▼──────────────────────┐   HTTPS     │  FastAPI @ Railway       │
  │  Next.js 16 @ Vercel     │────────────▶│  backend/main.py         │
  │  frontend/               │             │  uvicorn --proxy-headers │
  │                          │             │                          │
  │  Teacher-Flow:           │             │  /sessions /chat         │
  │  /api/teacher/[...path]  │             │  /submissions /submit    │
  │  (same-origin Proxy,     │             │  /admin/*  /dashboard/*  │
  │   ergänzt X-API-Key      │             │  /health /health/diag..  │
  │   server-seitig)         │             └────┬────────────┬────────┘
  └──────────────────────────┘                  │            │
                                                │            │ OpenAI-SDK
                                 pymongo (sync, │            │ (AsyncOpenAI)
                                 2s Timeout,    │            ▼
                                 30s Backoff)   │   ┌──────────────────┐
                                                ▼   │  OpenRouter API  │
                                   ┌────────────────┤  Default-Modell: │
                                   │ MongoDB Atlas  │  anthropic/      │
                                   │ (OPTIONAL!)    │  claude-sonnet-  │
                                   │ 5 Collections  │  4.5             │
                                   └────────────────┘└──────────────────┘
                                   Fallback ohne Mongo:
                                   JSON-Dateien im Container-FS
                                   (Railway-FS ist EPHEMER → Datenverlust
                                    bei Redeploy — nur für Dev okay)
```

Kein RAG, kein Redis, kein Postgres, keine WebSockets. `docker-compose.yml`
enthält nur `api` + `mongo`. Chat-Streaming existiert nicht — jede
Agent-Antwort ist ein einzelner HTTP-POST-Roundtrip.

### Die drei Auth-Pfade

| # | Pfad | Mechanismus | Quelle | Verhalten ohne Config |
|---|---|---|---|---|
| 1 | Studenten-Flow (`/sessions`, `/submissions`, `/auth/student/verify`) | Header `X-Student-Access-Code`, Vergleich per `hmac.compare_digest` gegen Env `STUDENT_ACCESS_CODE`; Frontend hält den Code in `sessionStorage` | `backend/auth.py` (`require_student_access`, Router-Dependency in `backend/api/routes.py:38`), `frontend/lib/api.ts` | **OFFEN** (Dev-/Prolific-Modus); Startup loggt Warnung `student_flow_open` |
| 2 | Teacher-Browser-Session (`/admin/*`- und `/dashboard/*`-SEITEN) | Signiertes httpOnly-Cookie `teacher_session` (HMAC-SHA256 via Web Crypto, 12 h Ablauf, Secret `TEACHER_SESSION_SECRET`); Login: POST `/teacher-login` prüft `TEACHER_ACCESS_CODE` **fail-closed** (kein Code konfiguriert = kein Zugang); `frontend/middleware.ts` schützt `/admin/:path*` + `/dashboard/:path*` | `frontend/lib/teacherAuth.ts`, `frontend/app/teacher-login/route.ts` | Login unmöglich (fail-closed) |
| 3 | Backend-API-Key (alle `/dashboard/*`-Endpoints, schreibende `/admin`-Routen, `/health/diagnostics`) | Header `X-API-Key` = Env `TOADAPT_API_KEY`, `hmac.compare_digest`; **fail-closed: 503 wenn kein Key konfiguriert** | `backend/auth.py` (`require_api_key`), `backend/dashboard/routes.py:19` (Router-weit), `backend/admin/routes.py` (pro Route) | 503 auf allen geschützten Routen |

Pfad 2 und 3 sind verkettet: Der Browser spricht NIE direkt mit den
geschützten Backend-Routen. `frontend/app/api/teacher/[...path]/route.ts`
verifiziert das Cookie und ergänzt den `X-API-Key` **server-seitig** —
der Key gelangt nie ins Browser-Bundle.

**Bewusste Ausnahme:** `GET /admin/cases` und `GET /admin/cases/{case_id}`
sind ungeschützt (Lese-Routen) — der Studenten-Flow lädt approved Cases
direkt darüber (`frontend/app/cases/page.tsx`). Alle schreibenden/
kostenverursachenden Admin-Routen (generate, patch, regenerate, validate,
approve, reject, retire) verlangen den API-Key.

---

## 2. Tragende Entscheidungen — WARUM und Beleg

### D1: Chat per HTTP POST, nicht WebSocket

- **Was:** `POST /sessions/{id}/chat` (`backend/api/routes.py:177`). Ein
  Request = eine Agent-Antwort. Das Feld `websocket_url` in
  `SessionResponse` (`backend/models/session.py:37`) ist ein **totes Relikt**
  — es gibt keinen WS-Endpoint.
- **Warum:** WebSockets brachen wiederholt am Railway-Proxy. Kapitulation
  nach mehreren Fix-Versuchen: Commit `e2cc925` "fix: replace WebSocket with
  HTTP POST chat (Railway WS compatibility)" (2026-04-30).
- **Konsequenz:** Führe KEINE WebSockets/SSE über Railway wieder ein ohne
  vorherigen Beweis (Spike gegen die echte Railway-Umgebung, nicht lokal).

### D2: Chat-History liegt CLIENTSEITIG

- **Was:** Das Frontend hält den Verlauf in `historyRef`
  (`frontend/app/cases/[id]/page.tsx:653`) und schickt pro Chat-Request die
  **letzten 10 Einträge** mit (`historyRef.current.slice(-10)`, Zeile 761).
  Das Backend nimmt `ChatRequest.history: list[dict]` entgegen und speichert
  KEINEN Dialogverlauf — die Server-`Session` zählt nur `message_count` und
  `metacognitive_phase_complete`.
- **Warum:** Server bleibt bzgl. Verlauf zustandslos → Chat funktioniert nach
  Backend-Neustart/Redeploy weiter, kein Mongo nötig für den Dialog, Requests
  sind unabhängig retry-bar.
- **Konsequenz:** Wer "der Agent vergisst Kontext" debuggt, schaut ins
  Frontend, nicht in eine Server-DB. Wer serverseitige History einführt,
  bricht die Zustandslosigkeit → Change-Control. (Vollständige Verläufe
  landen als Forschungslog in `experiment_events`, Event
  `chat_turn_completed` — das ist Logging, keine Laufzeitquelle.)

### D3: Mongo primär, Datei-Fallback, App bootet ohne beides

- **Was:** 5 Persistenz-Pfade, alle nach demselben Muster: Mongo-Verbindung
  mit `serverSelectionTimeoutMS=2000`; nach einem Verbindungsfehler 30 s
  Backoff, in dem sofort der Fallback greift (`backend/db/mongo.py`,
  eigenständige Kopien der Logik in `submission_store.py` und
  `experiment_logger.py`).

| Store | Datei | Mongo-Collection (Env-Default) | Fallback ohne Mongo |
|---|---|---|---|
| Sessions | `backend/db/session_store.py` | `sessions` | **kein Datei-Fallback** — nur prozesslokaler Dict-Cache in `api/routes.py` |
| Laufende Submissions | `backend/db/submission_store.py` | `submission_states` | JSON in `backend/db/runtime_submissions/` (wird IMMER geschrieben, write-through) |
| Dashboard-Ergebnisse | `backend/db/dashboard_store.py` | `dashboard_results` | JSON in `backend/db/submissions/` (write-through) |
| Case-Pool | `backend/cases/manager.py` | `cases` | JSON in `backend/cases/pool/` (write-through; Mongo gewinnt bei gleicher case_id) |
| Forschungs-Events | `backend/db/experiment_logger.py` | `experiment_events` | **keiner** — Events werden ohne Mongo verworfen (nur Warn-Log) |

- **Warum:** Das Railway-Dateisystem ist ephemer — bei jedem Redeploy weg.
  Mongo ist die einzige überlebende Quelle in Produktion; die Dateiablage
  existiert für lokale Entwicklung und als Notnagel. Vorher gingen
  Dashboard-Daten bei jedem Deploy verloren (siehe Docstring in
  `dashboard_store.py`).
- **Konsequenz:** Jeder neue Store MUSS dieses Muster kopieren (Timeout,
  Backoff, Fallback, Fehler nur loggen — nie den Request crashen). Und:
  `WEB_CONCURRENCY > 1` ist ohne verifiziertes Mongo VERBOTEN — Sessions
  lägen nur im Worker-Speicher, ein zweiter Worker beantwortet laufende
  Chats mit 404 (dokumentiert in `railway.toml`).

### D4: Guardrails als Post-hoc-Filter mit Komplett-Ersetzung

- **Was:** `guardrail_check(text, tp)` in `backend/agents/orchestrator.py:113`
  prüft die fertige LLM-Antwort der Reihe nach: TP-spezifische
  `forbidden_framework_names` aus `TP_CONFIGS` → globale `FORBIDDEN_PATTERNS`
  (direkte Antworten + Framework-Namen wie porter, vrio, rbv, 4p) →
  `SLANG_PATTERNS` → Emoji (Unicode-Kategorie `So`) →
  `RECOMMENDATION_PATTERNS` + 7 Regexe → `CASE_SPECULATION_PATTERNS`.
  Bei IRGENDEINEM Treffer wird die Antwort **komplett** durch einen festen,
  je Agent-Typ und Sprache vordefinierten Fallback-Text ersetzt
  (`_guardrail_fallback`), geloggt als `guardrail_triggered` (Level warning).
- **Warum Ersetzung statt Umformulierung:** Der Fallback ist deterministisch
  und kann selbst keine Guardrail verletzen. Eine LLM-Umformulierung wäre ein
  zweiter Call (Kosten, Latenz) und könnte erneut leaken.
- **Konsequenz:** Ein "komischer, generischer" Agent-Text im Chat ist meist
  ein ausgelöster Guardrail — prüfe die Logs auf `guardrail_triggered`,
  bevor du am Prompt drehst.

### D5: Fail-closed Shared-Secret + same-origin Teacher-Proxy

- **Was:** Siehe Auth-Tabelle oben. Kernpunkte: `require_api_key` liefert
  **503 statt Durchlass**, wenn `TOADAPT_API_KEY` fehlt; Cookie-Login liefert
  Redirect mit Fehler, wenn `TEACHER_ACCESS_CODE` fehlt; alle Vergleiche
  timing-sicher (`hmac.compare_digest` bzw. eigene `timingSafeEqual`).
- **Warum:** Das frühere statische Cookie `teacher_access=true` konnte jeder
  selbst setzen (dokumentiert in `frontend/lib/teacherAuth.ts`); Dashboards
  enthalten PII (Matrikelnummern + Scores). Fail-closed verhindert, dass eine
  vergessene Env-Variable die Daten öffnet.
- **Konsequenz:** Ein 503 "Auth nicht konfiguriert" ist KEIN Bug, sondern
  fehlende Env-Variable. Der `X-API-Key` darf niemals in Client-Code,
  `NEXT_PUBLIC_*`-Variablen oder Browser-Requests auftauchen.

### D6: Ein geteilter LLM-Client mit Semaphore/Retry/Timeout

- **Was:** `backend/llm.py` — ein `AsyncOpenAI`-Client pro API-Key
  (Connection-Reuse), `timeout=LLM_TIMEOUT_SECONDS` (Default 60),
  `max_retries=LLM_MAX_RETRIES` (Default 2, SDK-Backoff bei 429/5xx),
  globale `asyncio.Semaphore` pro Event-Loop mit `LLM_MAX_CONCURRENCY`
  (Default 16), Token-Verbrauch wird pro Call geloggt
  (`llm_call_completed`). Provider ist **OpenRouter** über das OpenAI-SDK —
  NICHT das Anthropic-SDK (die README-Zeile "Anthropic API" ist falsch).
- **Warum:** Client-pro-Request und ungebremste Parallelität hatten unter
  Last keine Chance (Event-Loop-Blocking-Historie mit dem früheren
  Anthropic-SDK, Wechsel zu OpenRouter in Commit `1fb727e`).
- **Konsequenz:** JEDER neue LLM-Call läuft über `OpenRouterClient.complete`
  — keine eigenen HTTP-Clients, keine eigenen Retry-Schleifen.

---

## 3. Invarianten — müssen IMMER gelten

Prüfe bei jeder Änderung, ob eine davon verletzt wird. Verletzung = Stopp +
`toadapt-change-control`.

1. **Kein studierendensichtbarer Framework-Name, keine Musterlösung, keine
   direkte Empfehlung.** Durchgesetzt an drei Stellen: (a) Guardrail-Filter
   auf Chat-Antworten (D4), (b) Case-Validator beim Approve
   (`backend/cases/validator.py`, 422 mit force-Override), (c)
   Feedback-Sanitizing im Evaluator (`DISALLOWED_FEEDBACK_PATTERNS` in
   `backend/evaluator/rubric_evaluator.py`). Gilt auch in Tests und
   Experimenten. Ebenso tabu: Bezüge auf die kurs-reservierten Cases
   ON Running und NORDIC HOME sowie echte Teilnehmerdaten im Repo.
2. **Jede Judge-Ausgabe ist validiert-oder-technical_fallback — nie Crash,
   nie stilles Raten.** Pipeline in `rubric_evaluator.py`: 3
   JSON-Extraktions-Kandidaten (roh / ohne Code-Fences / erstes-`{`-bis-
   letztes-`}`) → bei Fehlschlag genau EIN Repair-LLM-Call → danach
   `_fallback_payload`: 0 Punkte, `needs_human_review=True`,
   `evaluation_status="technical_fallback"`, `judge_confidence="low"`.
   Zusätzlich erzwingt `judge_confidence=="low"` immer
   `needs_human_review=True`.
3. **Studenten-Endpoints sind retry-tolerant.** Antwort-Speichern ist ein
   Overwrite pro `question_id` (beliebig wiederholbar); `/submit` kann nach
   einem 503 erneut aufgerufen werden (re-evaluiert und überschreibt);
   Chat-Fehler geben 503 mit "bitte gleich noch einmal" statt den Zustand zu
   korrumpieren. Einschränkung: `POST /sessions` und `POST /submissions`
   erzeugen bei Retry NEUE IDs (nicht strikt idempotent) — akzeptiert, weil
   verwaiste Objekte harmlos sind. Neue Endpoints müssen dieses Niveau halten.
4. **Mongo ist optional — die App MUSS ohne booten und funktionieren.**
   Kein Import, keine Route darf beim Fehlen von Mongo crashen; Stores
   degradieren leise (D3). Kehrseite: ohne Mongo nur 1 Worker und
   Datenverlust bei Redeploy — das ist ein Betriebs-, kein Code-Problem.
5. **Metacognitive-First pro Session.** Die erste Agent-Antwort einer Session
   kommt vom metakognitiven Agenten, solange
   `session.metacognitive_phase_complete` False ist (`_select_agent` in
   `orchestrator.py`; einzige Ausnahme: explizite Begriffs-Fragen routen
   sofort zu CONCEPTUAL). Empirische Grundlage: CompEd-Publikation
   (Cohen's d = 0.44) — siehe `bwl-scaffolding-reference`.

---

## 4. Offene Schwachstellen (ehrlich, Stand: 2026-07-08)

Diese Lücken sind BEKANNT und AKZEPTIERT-bis-auf-Weiteres. Nicht heimlich
"mitfixen" — jede davon ist entweder ein bewusster Trade-off oder wartet auf
eine Grundsatzentscheidung (siehe `toadapt-change-control` /
`ROLLOUT_PLAN.md`).

| Schwachstelle | Detail / Fundort | Status |
|---|---|---|
| **Kein Gruppenkonzept trotz Gruppen-Assessment** | Im Code existiert nur `matrikelnummer` pro Person. Ownerin bestätigte 2026-07-08: Gruppen bleiben die Assessment-Einheit (Tutor beurteilt Gruppenabgaben in Präsenz), die Tool-Arbeit ist individuelle Vorbereitung. Folge: Tutor-Dashboard kann nicht nach Gruppen aggregieren. | Größte konzeptionelle Lücke; Grundsatzentscheidung offen |
| **`target_tp: 1` hartkodiert** | `frontend/app/cases/[id]/page.tsx` (Submission-POST, Zeile ~717). `TP_SCHEDULE`/`current_tp_phase()` existieren in `backend/config/tp_configs.py`, greifen für Sessions aber nur, wenn `case.target_tp == 0` (FULL). | Offen (TP-Progression = Rollout-Phase 2) |
| **Keyword-basiertes Agent-Routing** | `_select_agent` in `orchestrator.py:265`: Substring-Listen, keine Intent-Klassifikation. "warum" in irgendeinem Kontext → STRATEGIC. | Bewusst simpel; Kandidat für spätere Verbesserung |
| **Metacognitive-First endet nach 1 Antwort** | `metacognitive_phase_complete = True` sobald `message_count >= 1` (`orchestrator.py:420`) — keine echte Readiness-Messung. | Rudimentär vs. ursprünglicher Vision |
| **Glossar + Canvas-Blöcke im Frontend hartkodiert** | `CASE_GLOSSARY` (pro case_id) und `BUSINESS_MODEL_CANVAS_BLOCKS` in `frontend/app/cases/[id]/page.tsx` (Zeilen ~86/~190). Neue Cases bekommen KEIN Glossar ohne Frontend-Änderung. | Offen |
| **TP4 ohne `forbidden_framework_names`** | `TP_CONFIGS[4]` hat den Key nicht (`tp_configs.py`; `grep` findet ihn nur 3× für TP1–TP3). `guardrail_check` nutzt `.get(..., [])` → in TP4 greifen nur die globalen `FORBIDDEN_PATTERNS`. Vermutlich unbeabsichtigt. | Offen; Fix wäre klein, braucht aber Guardrail-Regressionstest |
| **Rate-Limits pro Worker, nicht global** | `backend/ratelimit.py` ist ein In-Process-Sliding-Window; bei N Workern effektiv bis zu N-faches Limit. Bewusster Trade-off (Kostenbremse, keine exakte Quote; kein Redis). | Akzeptiert |
| **In-Memory-Caches können stale sein** | `_sessions`/`_submissions`-Dicts in `api/routes.py` cachen neben dem Mongo-Store; bei mehreren Workern kann ein Worker veralteten Zustand haben (Mongo macht es korrekt-genug, nicht konsistent). | Akzeptiert für aktuelle Größenordnung |
| **README teils falsch** | "Anthropic API"-Zeile (tatsächlich OpenRouter via OpenAI-SDK) und totes `websocket_url`. | Doku-Schuld, siehe `toadapt-docs-and-writing` |
| **Kein Frontend-Error-Tracking** | Sentry nur im Backend (optional via `SENTRY_DSN`). | Offen |

---

## Provenance und Wartung

Erstellt: 2026-07-08, gegen den damaligen Stand von `main` verifiziert
(HEAD `141bb63`, nach dem filter-repo-Rewrite vom 2026-07-08; die
Security-Härtung heißt post-rewrite `8b21fc1`). Alle Zeilenangaben sind
zirka-Werte und drift-anfällig. Re-Verifikation pro Fakt (vom Repo-Root):

| Fakt | Re-Verifikations-Kommando |
|---|---|
| Kein WebSocket-Endpoint, Chat = HTTP POST | `grep -rn "websocket\|@router.post(\s*\"/sessions/{session_id}/chat" backend/ --include="*.py"` |
| History clientseitig, letzte 10 | `grep -n "slice(-10)\|historyRef" "frontend/app/cases/[id]/page.tsx"` |
| 2s-Timeout / 30s-Backoff im Mongo-Muster | `grep -rn "serverSelectionTimeoutMS\|< 30" backend/db/ backend/cases/manager.py` |
| Guardrail = Komplett-Ersetzung | `grep -n "_guardrail_fallback\|guardrail_triggered" backend/agents/orchestrator.py` |
| require_api_key fail-closed (503) | `grep -n "503\|SERVICE_UNAVAILABLE" backend/auth.py` |
| Teacher-Proxy ergänzt Key server-seitig | `grep -n "X-API-Key" "frontend/app/api/teacher/[...path]/route.ts"` |
| LLM-Client-Defaults (60s/2/16) | `grep -n "LLM_TIMEOUT_SECONDS\|LLM_MAX_RETRIES\|LLM_MAX_CONCURRENCY" backend/llm.py` |
| TP4 weiterhin ohne forbidden_framework_names | `grep -n "forbidden_framework_names" backend/config/tp_configs.py` (3 Treffer = Lücke besteht) |
| target_tp noch hartkodiert | `grep -n "target_tp: 1" "frontend/app/cases/[id]/page.tsx"` |
| Judge-Fallback intakt | `grep -n "technical_fallback" backend/evaluator/rubric_evaluator.py` |
| WEB_CONCURRENCY-Warnung | `grep -n "WEB_CONCURRENCY" railway.toml` |
| Commit-Belege existieren | `git log --oneline --all \| grep -E "e2cc925\|8df4cfd\|1fb727e"` |
