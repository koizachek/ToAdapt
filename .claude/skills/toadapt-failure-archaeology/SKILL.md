---
name: toadapt-failure-archaeology
description: >
  Chronik aller geschlagenen Schlachten im ToAdapt-Repo (2026-04-06 bis
  2026-07-08): Symptom → Root Cause → Beleg-Commit → Status. Lade diese Skill,
  wenn du (a) verstehen willst, WARUM der Code so aussieht wie er aussieht
  (toter websocket_url, BUILD_MARKER, doppelte Commits, load_dotenv vor den
  Imports), (b) eine Änderung planst, die eine alte Wunde berühren könnte
  (WebSockets, CORS, Anthropic-SDK, dotenv/Nixpacks, Mongo-Env, Judge-JSON,
  Git-History), (c) auf CLAUDE.md oder dev-docs/ stößt und sie für aktuelle
  Doku hältst, (d) Fragen zu PII-Vorfall, git filter-repo, Force-Push,
  duplizierten Juni-Commits oder dem Branch security-hardening hast, oder
  (e) wissen willst, welche Dateien historisch am meisten Churn hatten und
  warum. Schlüsselwörter: git history, Commit-Archäologie, Regression,
  "warum ist das so", Pivot, Fossil, Railway-Kapitulation, History-Rewrite.
---

# ToAdapt Failure-Archaeology — Chronik der geschlagenen Schlachten

## Wann diese Skill NICHT gilt

| Du willst … | Lies stattdessen |
|---|---|
| ein AKTUELLES Symptom triagieren (Bug jetzt, Symptom→Ursache-Tabelle) | `toadapt-debugging-playbook` |
| wissen, wie Änderungen klassifiziert/gegated werden und welche Regeln unverhandelbar sind | `toadapt-change-control` |
| die tragenden Designentscheidungen und Invarianten des heutigen Systems | `toadapt-architecture-contract` |
| wissen, welche Dokumente Wahrheit vs. Fossil sind (vollständige Liste + Stil) | `toadapt-docs-and-writing` |
| am q4/Bloom-6-Judge-Alignment arbeiten (das härteste LEBENDE Problem) | `toadapt-judge-alignment-campaign` |
| Env-Variablen und Magic Numbers nachschlagen | `toadapt-config-and-flags` |

Diese Skill ist ein **Nachschlagewerk der Vergangenheit**: Sie existiert, damit
niemand eine bereits geschlagene Schlacht neu führt oder ein Relikt für einen
Bug hält.

## Orientierung in 60 Sekunden

- Repo: `/Users/dianakozachek/ToAdapt` (GitHub: koizachek/ToAdapt, **privat**, Solo-Autorin).
- Historie: **2026-04-06 bis 2026-07-08, 92 Commits auf `main`** (Stand: 2026-07-08).
  Die Historie wurde am 2026-07-08 per `git filter-repo` **umgeschrieben**
  (PII-Vorfall, s.u.) — Commit-Hashes aus älteren Notizen/Chats lösen daher
  ggf. nicht mehr auf.
- Jeden Hash hier verifizierst du mit:
  ```bash
  git -C /Users/dianakozachek/ToAdapt log -1 --format="%h | %ad | %s" --date=short <hash>
  ```
- "TP" = Touchpoint (einer von 4 Meilensteinen des BWL-A-Kurses).
  "Judge" = der LLM-Rubric-Evaluator, der Studierenden-Antworten bewertet.

## WARNUNG: Die Fossilien-Falle (wichtigster Eintrag)

**`CLAUDE.md` und `dev-docs/phase1/*.md` beschreiben ein System, das nicht
existiert.** Sie dokumentieren die verworfene Gruppen-Echtzeit-Architektur
(WebSocket-Gruppenchat, GroupMemory, RAG/ChromaDB, PostgreSQL/Redis,
6er-Gruppen-Login). Lies sie NIEMALS als Ist-Doku und implementiere NIEMALS
"fehlende" Komponenten daraus nach.

- `CLAUDE.md` ist seit Commit `4bd0d7b` (2026-04-07, "Remove CLAUDE.md from
  repo, add to .gitignore") **gitignored und untracked** — eine lokale Datei,
  die den Stand vor dem Pivot einfriert (`.gitignore` Zeile 8).
- `dev-docs/phase1/schritt1-backend-skeleton.md`, `schritt2-base-agent.md`,
  `schritt3-orchestrator.md` sind getrackte Fossile derselben toten Architektur.
- `TODO.md` ist ein eingefrorenes Security-Review-Transkript; die Punkte sind
  großteils behoben.
- **Dokument der Wahrheit für Status/Roadmap ist `ROLLOUT_PLAN.md`** (Stand:
  2026-07-08). Details zur Doku-Landkarte: Skill `toadapt-docs-and-writing`.

## Chronik-Übersicht

| # | Schlacht | Zeitraum | Status |
|---|---|---|---|
| 1 | Gruppen-System-Pivot | 2026-04-07 → 2026-04-30 | gelöst (Fossile bleiben) |
| 2 | WebSocket vs. Railway | 2026-04-30 | **umgangen** — Kapitulation zu HTTP |
| 3 | CORS-500er | 2026-04-30 → 2026-07-07 | gelöst (`ALLOWED_ORIGINS`) |
| 4 | Anthropic-SDK / Event-Loop | 2026-04-30 → 2026-05-08 | gelöst (Wechsel zu OpenRouter) |
| 5 | Nixpacks/Env-Saga | 2026-04-30 | gelöst (dotenv später kontrolliert zurück) |
| 6 | Mongo-Diagnostik-Kampagne | 2026-05-12 → 2026-05-14 | gelöst (Relikt `BUILD_MARKER`) |
| 7 | Judge-JSON-Fragilität | 2026-05-14 → laufend | umgangen (Fallback-Kette); Kern offen |
| 8 | Guardrail-Nachjustierung nach Test 1 | 2026-05-17 | gelöst |
| 9 | Teacher-Alignment / q4-Schwäche | 2026-05-31 → offen | **offen** → Campaign-Skill |
| 10 | PII-Vorfall + History-Rewrite | bis 2026-07-08 | umgangen; **Restrisiko offen** |
| 11 | Duplizierte Juni-Historie (Rebase-Unfall) | 2026-06-18 / 2026-07-08 | gelöst; Branch-Cleanup offen |
| 12 | Lasttest traf Produktions-Mongo (find_dotenv-Falle) | 2026-07-10 | behoben (Daten bereinigt), dokumentiert |

---

## 1. Der Gruppen-System-Pivot (das Erdbeben)

- **Symptom:** Repo-Struktur, CLAUDE.md und dev-docs passen nicht zum Code;
  `backend/realtime/`, `GroupMemory`, RAG existieren nicht (mehr).
- **Root Cause:** Das Projekt startete als Gruppen-Echtzeit-Scaffolding-System
  (WebSocket-Gruppenchat für 6er-Gruppen). Am 2026-04-30 wurde es am selben
  Tag, an dem der erste Deploy-Versuch lief, zum **individuellen
  Transfer-Trainer** umgebaut: Studierende bearbeiten einzeln AI-generierte
  Mini-Cases zur Vorbereitung auf die Gruppenarbeit.
- **Beleg:**
  - `dc5a2b4` (2026-04-07, "skeleton") — Gruppen-Skeleton mit
    `backend/realtime/{websocket,presence,broadcast}.py`, `models/group.py`,
    aufgeblähter `requirements.txt` (chromadb, asyncpg, redis …).
  - `8df4cfd` (2026-04-30, "refactor: individual transfer trainer
    architecture") — entfernt Group/GroupMemory/Presence, führt User/Case/
    Submission, CaseGenerator, RubricEvaluator, AgentOrchestrator ein.
  - `e57ed3f` (2026-04-30) zog nur das README nach; CLAUDE.md/dev-docs nie.
  - `825f656` (2026-04-30) strippte die requirements auf reale Dependencies.
- **Status:** gelöst (der Pivot IST das heutige System). Die Fossile bleiben
  als Falle liegen — siehe Warnung oben.
- **Nicht neu schlagen:** Baue keine Gruppen-Features "nach CLAUDE.md" nach.
  Gruppen existieren fachlich als Assessment-Einheit (Tutor beurteilt
  Gruppenabgaben in Präsenz), aber im Code gibt es derzeit **kein
  Gruppenkonzept** — nur `matrikelnummer` pro Person. Ob ein Gruppen-Umbau
  kommt, ist eine offene Grundsatzentscheidung (`ROLLOUT_PLAN.md`;
  Kontext: `toadapt-architecture-contract`).

## 2. WebSocket vs. Railway (die Kapitulation)

- **Symptom (damals):** Chat-Verbindungen brachen auf Railway (Backend-Host,
  Nixpacks-Build hinter Railway-Proxy) ständig ab; Session-Recovery-Versuche
  und readyState-Handler halfen nicht.
- **Root Cause:** WebSocket-Verbindungen über den Railway-Proxy waren mit dem
  damaligen Setup nicht zuverlässig zu betreiben.
- **Beleg (alle 2026-04-30, in dieser Reihenfolge):**
  1. `17323ad` "fix: WebSocket session recovery after Railway restart"
  2. `304af9b` "fix: WebSocket readyState check + onopen/onerror handlers"
  3. `e2cc925` "fix: replace WebSocket with HTTP POST chat (Railway WS
     compatibility)" — die Kapitulation.
- **Status:** umgangen. Der Chat läuft seither über `POST /sessions/{id}/chat`.
  **Relikt:** `SessionResponse.websocket_url` (`backend/models/session.py:37`,
  befüllt in `backend/api/routes.py:161` mit `/ws/{session_id}`) ist **tot** —
  es gibt keinen WS-Endpoint. Das README erwähnte den toten Endpoint zeitweise
  ebenfalls.
- **Nicht neu schlagen:** Führe KEINE WebSockets über Railway wieder ein, ohne
  vorher mit einem minimalen Spike zu beweisen, dass sie dort stabil laufen.
  Der tote `websocket_url` ist kein Bug-Report, sondern ein Grabstein.

## 3. CORS-500er

- **Symptom (damals):** Browser-Requests scheiterten an CORS; zusätzlich
  fehlten CORS-Header auf 500er-Antworten, sodass der Client echte
  Server-Fehler nicht sehen konnte (sah wie ein CORS-Problem aus, war ein
  Backend-Fehler).
- **Root Cause:** Zwei verschränkte Probleme: (a) Origin-Konfiguration der
  FastAPI-CORS-Middleware, (b) unbehandelte Exceptions liefern Antworten OHNE
  CORS-Header — der Browser blockt sie, der echte Fehler bleibt unsichtbar.
- **Beleg:**
  - `7bb936e` (2026-04-30) "fix: allow all CORS origins (wildcard not
    supported by FastAPI middleware)" — Wildcard-Workaround, öffnete alles.
  - `dca2da5` (2026-04-30) "fix: global exception handler with CORS headers
    on 500 errors".
  - Aufgeräumt erst in der Security-Härtung `8b21fc1`/`15d6b14` (2026-07-07):
    Origins kommen jetzt aus der Env-Variable `ALLOWED_ORIGINS`
    (kommagetrennt; leer = nur localhost; siehe `backend/main.py`,
    `_allowed_origins()` um Zeile 93–107, Stand: 2026-07-08).
- **Status:** gelöst.
- **Nicht neu schlagen:** Wenn der Browser "CORS-Fehler" meldet, prüfe ZUERST,
  ob das Backend in Wahrheit 500 wirft (Details: `toadapt-debugging-playbook`).
  Öffne niemals wieder Wildcard-Origins als "Fix".

## 4. Anthropic-SDK / Event-Loop → OpenRouter-Wechsel

- **Symptom (damals):** Chat hing/blockierte unter Last; danach
  SDK-Inkompatibilität (`httpx`-`proxies`-Argument) beim Upgrade.
- **Root Cause:** (a) Synchroner Anthropic-Client blockierte den
  asyncio-Event-Loop von FastAPI; (b) Versionskonflikt anthropic-SDK ↔ httpx.
- **Beleg:**
  - `c494357` (2026-04-30) "fix: switch all Anthropic clients to
    AsyncAnthropic (fixes event loop blocking)" — betraf orchestrator,
    generator UND rubric_evaluator gleichzeitig.
  - `b048b56` (2026-04-30) "debug: show real error message in chat" —
    Blind-Debugging-Zwischenschritt.
  - `08c5389` (2026-04-30) "fix: upgrade anthropic to >=0.40.0 (httpx proxies
    compatibility)".
  - `1fb727e` (2026-05-08) "Switch backend LLM integration to OpenRouter" —
    kompletter Provider-Wechsel.
- **Status:** gelöst durch Architekturwechsel. Heute läuft ALLES über das
  **OpenAI-SDK gegen OpenRouter** (`backend/llm.py`: `AsyncOpenAI`,
  `OPENROUTER_BASE_URL` default `https://openrouter.ai/api/v1`, Modell via
  `OPENROUTER_MODEL`, default `anthropic/claude-sonnet-4.5`; Stand:
  2026-07-08). Das Anthropic-SDK ist NICHT mehr im Einsatz — README-Zeilen,
  die es behaupten, sind falsch.
- **Nicht neu schlagen:** Keine synchronen LLM-Clients in async-Routen.
  Kein Rückwechsel des SDKs "nebenbei" — das ist ein gegateter Eingriff
  (`toadapt-change-control`).

## 5. Nixpacks/Env-Saga

- **Symptom (damals):** Auf Railway gesetzte Env-Variablen (API-Key!) kamen
  im Prozess nicht an; lokal funktionierte alles.
- **Root Cause:** Eine ins Image gelangte `.env`-Datei + `python-dotenv`
  überschrieb im Nixpacks-Build die von Railway injizierten Variablen.
- **Beleg:**
  - `c19097f`, `0627491` (beide 2026-04-30) — Blind-Debugging: Logging von
    Key-Präsenz und ALLEN `ANTHROPIC*`-Env-Keys.
  - `783bb5c` (2026-04-30) "fix: remove .env.example and python-dotenv
    (nixpacks was overriding Railway vars)".
- **Status:** gelöst — mit kontrolliertem Rückbau: dotenv ist heute wieder da
  (`load_dotenv(...)` in `backend/main.py` Zeile 12–14, **vor** den
  Backend-Imports, weil deren Konfiguration env-abhängig ist). Genau deshalb
  existieren die absichtlichen `E402`-Ruff-Ignores für `backend/main.py` und
  `backend/db/submission_store.py` in `pyproject.toml` (Zeile 19–22, Stand:
  2026-07-08). `.env.example` existiert wieder und ist aktuell.
- **Nicht neu schlagen:** "Repariere" die E402-Ignores nicht durch
  Import-Umsortierung — `load_dotenv` MUSS vor den Imports laufen. Und lasse
  keine echte `.env` ins Deploy-Artefakt gelangen.

## 6. Mongo-Diagnostik-Kampagne (Blind-Debugging gegen Railway)

- **Symptom (damals):** Experiment-Events aus Prolific-Läufen (Prolific =
  Plattform zur Teilnehmer-Rekrutierung) landeten nicht in MongoDB; unklar,
  ob Env-Vars, Init-Reihenfolge oder Kontext-Verlust schuld waren. Railway
  bot keinen direkten Einblick in den laufenden Prozess.
- **Root Cause:** Mehrere kleine Fehler in Initialisierung und
  Kontext-Weitergabe des Experiment-Loggings; erschwerend: keinerlei
  Introspektionsmöglichkeit im Deployment → tagelanges Deploy-and-Pray.
- **Beleg (Kampagne in 6 Commits):** `7367767` (2026-05-12, "Add Mongo
  experiment logging for Prolific runs") → `f7850a3` → `12b3475` → `dd107fd`
  → `464bbca` ("Expose Mongo env diagnostics") → `dbc92f2` (2026-05-14,
  "Bump Railway Mongo diagnostic marker").
- **Status:** gelöst. **Relikt:** `BUILD_MARKER =
  "railway-mongo-env-diagnostics-2026-05-14-1809z"` in `backend/main.py:55`
  (ausgegeben in `/health/diagnostics`, Zeile 147; Stand: 2026-07-08) — ein
  Fossil dieser Kampagne, damit man sehen konnte, WELCHER Build gerade lief.
- **Nicht neu schlagen:** Für Mongo-/Env-Fragen im Deployment existiert heute
  `GET /health/diagnostics` (X-API-Key-geschützt). MESSEN statt
  Marker-Bumping — Werkzeuge: `toadapt-diagnostics-and-tooling`.

## 7. Judge-JSON-Fragilität (der chronische Patient)

- **Symptom:** Der LLM-Judge (bewertet Freitext-Antworten gegen Rubrics)
  liefert gelegentlich kein parsebares JSON → Bewertungen scheiterten.
- **Root Cause:** LLM-Ausgaben sind nie garantiert schema-konform; anfangs
  gab es keinen Reparatur-/Fallback-Pfad.
- **Beleg:** `4dd79da` (2026-05-14) "Harden rubric evaluator JSON parsing".
  `backend/evaluator/rubric_evaluator.py` wurde in **12 Commits** geändert —
  die chronisch instabilste Backend-Komponente (siehe Churn-Tabelle).
- **Status:** umgangen mit einer Fallback-Kette (Stand: 2026-07-08):
  3 Extraktions-Kandidaten (raw / ohne Code-Fences / erstes-`{`-bis-letztes-`}`)
  → EIN Repair-LLM-Call → `technical_fallback` (0 Punkte,
  `needs_human_review=True`, `evaluation_status="technical_fallback"`).
  Nachträgliche Reparatur: `scripts/retry_technical_fallback_scores.py`
  (macht ECHTE LLM-Calls — nur bewusst ausführen).
- **Nicht neu schlagen:** Die Fragilität ist per Fallback eingehegt, nicht
  beseitigt. Jede Änderung an Judge-Prompts/Kalibrierung erfordert einen
  Alignment-Recheck gegen Teacher-Scores VOR Deploy (`toadapt-change-control`);
  das inhaltliche Kernproblem (q4) lebt in `toadapt-judge-alignment-campaign`.

## 8. Guardrail-Nachjustierung nach Test 1

- **Symptom:** Erster realer Testlauf zeigte Guardrail-Lücken/Fehltreffer im
  Agenten-Output (Guardrails = Filter, die direkte Antworten, Framework-Namen
  etc. aus Agenten-Antworten fernhalten).
- **Beleg:** `9d2567b` (2026-05-17) "guardrail update after test1".
- **Status:** gelöst (für damals). Merke: Guardrail-Patterns sind empirisch
  nachjustiert worden und werden es wieder — bekannte offene Lücke: in
  `TP_CONFIGS[4]` fehlt der `forbidden_framework_names`-Key (Triage dazu:
  `toadapt-debugging-playbook`).

## 9. Teacher-Alignment-Studie und die q4-Wunde

- **Symptom:** Judge-Scores wichen systematisch von Lehrkraft-Scores ab.
- **Beleg:** `9a8077f` (2026-05-31) "human alignment with teacher scores";
  Report: `docs/teacher_alignment_report_20260531_17submissions.md`
  (**Achtung:** Dateiname sagt "17submissions", tatsächlicher Scope sind
  16 Submissions / 64 Frage-Zeilen).
- **Status/Ergebnis (Stand: 2026-07-08):** Kalibrierung verbesserte
  Pearson r 0.631→0.796, machte den Judge aber systematisch STRENGER
  (Unterbewertung in 48/64 Fällen). **q4 (Bloom-Level 6, Integration,
  30 Punkte) bleibt die Schwachstelle (MAE ~4.97) — das härteste lebende
  Problem.** Kalibrierungsanker sind hartkodiert pro `question_id` in
  `rubric_evaluator.py` (`_format_calibration_notes`).
- **Nicht neu schlagen:** Erfinde keine eigene Vergleichsmethodik — die
  Blind-Review-Pipeline existiert (`scripts/export_review_workbooks.py`,
  `scripts/compare_teacher_rubric_scores.py`). Aktive Arbeit an q4:
  `toadapt-judge-alignment-campaign`.

## 10. PII-Vorfall + History-Rewrite (2026-07-08)

- **Symptom:** Echte Prolific-Teilnehmerdaten (Prolific-IDs + Freitext-
  Antworten) lagen in Commits eines zeitweise öffentlichen Repos.
- **Root Cause:** Forschungsdaten wurden direkt ins Repo committet, bevor
  eine Datenhygiene-Regel existierte.
- **Maßnahmen (2026-07-08):**
  - `git filter-repo` über alle Branches + **Force-Push** → die GESAMTE
    Historie wurde umgeschrieben. Alle Commit-Hashes änderten sich; alte
    Hashes (z.B. `e722310`, der Commit, mit dem die Daten ursprünglich
    hereinkamen, oder `44b4b84` aus älteren Notizen) lösen im heutigen Repo
    **nicht mehr auf** — das ist erwartet, kein Korruptions-Zeichen.
  - Daten + Backup-Bundle der ALTEN History verschoben nach
    `~/ToAdapt_sensitive_data/` (enthält u.a.
    `ToAdapt_backup_pre_filter_2026-07-08.bundle`, `backend/`, `data/`).
    **NIEMALS von dort zurückkopieren oder committen.**
  - `.gitignore` blockt `data/prolific_runs/**` (nur `README.md` getrackt).
- **Restrisiko (offen):**
  - Die GitHub-PR-Ref `refs/pull/1/head` zeigt noch auf die alte History
    (Objekt `56eeb70…`; lokal nicht vorhanden, remote via
    `git ls-remote origin 'refs/pull/*'` sichtbar). Nur für Collaborators
    sichtbar; Repo ist privat und bleibt es, bis die PII-Fragen final geklärt
    sind.
  - DSGVO-/Prolific-Meldepflicht-Klärung ist organisatorisch offen.
- **Status:** umgangen (Working Tree und erreichbare History sind sauber),
  Restrisiko dokumentiert offen.
- **Nicht neu schlagen:** Echte Teilnehmerdaten kommen NIE wieder ins Repo —
  nicht in Fixtures, nicht in Tests, nicht in Skills. Synthetische Daten
  verwenden. Regel-Rationale und Gating: `toadapt-change-control`.

## 11. Duplizierte Juni-Historie (Rebase-Unfall)

- **Symptom:** `git log` auf `main` zeigt Commits vom 2026-06-18 **doppelt** —
  gleiche Message, gleicher Tag, verschiedene Hashes, nahezu identischer Diff:
  - "en version teacher": `33c17b2` (main-Seite) / `1ddec46` (Branch-Seite)
  - "persistent mode teacher student divide": `134913d` / `7259efa`
  - "changing glossary": `8db2f07` / `ebb0e69`
  - "Security-Härtung …" (2026-07-07): `8b21fc1` (main-Seite, Message
    "…Secrets-/PII-Hygiene…") / `15d6b14` (Branch-Seite, "…Secrets-Hygiene…")
- **Root Cause:** Rebase-Unfall — dieselben Änderungen existierten auf `main`
  und auf dem Branch `security-hardening` mit unterschiedlichen Hashes; der
  spätere Merge brachte beide Seiten in die Historie.
- **Beleg:** Merge-Commit `764e89a` ("Merge branch 'main' into
  security-hardening") + `0a705fb` ("Merge pull request #2 from
  koizachek/security-hardening"), beide 2026-07-08.
- **Status:** gelöst — der Merge hat den Zustand konsolidiert; der Working
  Tree ist eindeutig. Die Duplikate in der Historie sind kosmetisch und
  bleiben (nach dem filter-repo-Force-Push wird die History nicht noch einmal
  umgeschrieben, nur um Kosmetik zu fixen).
  **Aufräum-Kandidat (offen, Stand: 2026-07-08):** Der Branch
  `security-hardening` (lokal + origin) ist vollständig gemergt
  (`git log main..security-hardening` ist leer) und redundant — Löschung ist
  ein Kandidat, aber eine mutierende Git-Operation: nicht nebenbei erledigen,
  sondern über den normalen Change-Prozess (`toadapt-change-control`).
- **Nicht neu schlagen:** Wenn du doppelte Commits siehst: NICHT rebasen,
  NICHT force-pushen, NICHT "History reparieren". Es ist bekannt und erklärt.

---

## 12. Lasttest gegen die Produktions-Mongo (die find_dotenv-Falle, 2026-07-10)

- **Symptom:** Ein "isoliert" gestarteter Lasttest-Probelauf (Backend aus
  fremdem Arbeitsverzeichnis, LLM auf Stub, keine Mongo-Variablen gesetzt)
  zeigte 26-s-Latenzen und Timeouts schon bei 60 simulierten Studierenden —
  und schrieb dabei 643 Testdatensätze in die ECHTE Atlas-Datenbank.
- **Root Cause:** `load_dotenv()` in `backend/main.py` sucht die `.env` per
  `find_dotenv` vom **Modulpfad** aus, nicht vom Arbeitsverzeichnis — ein
  Start außerhalb des Repos lädt trotzdem die Repo-.env mit den
  MAS-Credentials. Explizit gesetzte Env-Variablen gewinnen zwar
  (LLM-Stub griff), aber die NICHT gesetzten Mongo-Variablen kamen aus der
  .env. Die Latenz war der zweite Lerneffekt: synchrone pymongo-Writes pro
  Request über eine Transatlantik-Strecke sättigen den Default-Threadpool
  (`asyncio.to_thread`) — Backend und Atlas MÜSSEN in derselben Region
  liegen, sonst misst ein Lasttest nur das Netz.
- **Bereinigung:** Gleiche Session, chirurgisch per eindeutig synthetischer
  Kennungen (`lasttest-NNNN`/`probe`, Matrikel `00-NNN-000`): 64 sessions,
  43 submission_states, 43 dashboard_results, 491 experiment_events,
  2 group_uploads gelöscht; Restbestände verifiziert (17 dashboard_results,
  1.466 events unangetastet). Wiederholungslauf mit Mongo aus: alle
  W1-Gates PASS (Chat p95 1,6 s statt 56 s).
- **Beleg:** Commit `324d937` (Warnung + Env-Overrides im Docstring von
  `scripts/load_test.py`); ROLLOUT_CHECKLIST.md W1.
- **Status:** Behoben/dokumentiert. Regel daraus: Vor jedem Test-Start mit
  echtem Backend-Code IMMER `mongo_connection_mode` im Startup-Log prüfen —
  `mas_credentials` heißt: du redest mit der Produktion.

## Churn-Hotspot-Tabelle (Stand: 2026-07-08)

Erzeugt mit:
```bash
git -C /Users/dianakozachek/ToAdapt log --name-only --format= | sort | uniq -c | sort -rn | head -12
```

| Änderungen | Datei | Interpretation |
|---:|---|---|
| 23 | `frontend/app/cases/[id]/page.tsx` | DAS umkämpfte File: gesamter Studenten-Flow (Case-Ansicht, Glossar-Chips, Chat, Antworten) in einer Datei; Glossar + Canvas-Blöcke dort HARTKODIERT pro Case |
| 17 | `backend/main.py` | Deploy-Schmerz kondensiert: CORS, dotenv, Diagnostics, BUILD_MARKER — fast jede Infrastruktur-Schlacht (Nr. 3, 5, 6) hinterließ hier Spuren |
| 15 | `backend/api/routes.py` | Studenten-Flow-API; wuchs mit jedem Feature (Sessions, Chat, Submissions, Auth, Rate-Limits) |
| 14 | `frontend/app/page.tsx` | Landing/Login; mehrfach umgebaut (Prolific-Copy, Studien-Landing, Matrikel-Login) |
| 13 | `.gitignore` | Spiegel der Datenhygiene-Lernkurve (CLAUDE.md, prolific_runs, Secrets) |
| 12 | `backend/evaluator/rubric_evaluator.py` | Chronisch instabilste Backend-Komponente (Schlachten Nr. 7 + 9) |
| 11 | `README.md` | Oft nachgezogen, trotzdem teils falsch (Anthropic-SDK-Zeile) |
| 10 | `backend/evaluator/__pycache__/rubric_evaluator.cpython-313.pyc` | Historisch wurden `.pyc`-Dateien mitcommittet (frühe Hygiene-Lücke); heute nicht mehr im Tree |

Lesart: Hoher Churn = hohes Regressionsrisiko. Änderungen an den Top-3-Dateien
verdienen besondere Sorgfalt und Tests (`toadapt-validation-and-qa`).

## Kleinere Scharmützel (ein Satz pro Eintrag)

| Commit | Datum | Was |
|---|---|---|
| `c60d6ac` | 2026-04-30 | Railway expandierte `$PORT` nicht wie erwartet → Shell-Wrapper als Fix |
| `10df9bf` | 2026-04-30 | Fehlender `case_manager`-Import crashte `api/routes.py` beim Start |
| `9e85bca` | 2026-05-12 | Vercel-Deploy-Problem des Frontends ("solving vercel issue") |
| `dbc92f2` | 2026-05-14 | Letzter "Marker-Bump" der Mongo-Kampagne — Symbol des Blind-Debuggings |
| `141bb63` | 2026-07-08 | CI-pytest scheiterte, weil das `backend`-Paket im Repo-Root liegt → `PYTHONPATH=.` in `.github/workflows/ci.yml` |

## Provenance und Wartung

Update 2026-07-11: Eintrag 12 (Lasttest gegen Produktions-Mongo /
find_dotenv-Falle, 2026-07-10) ergänzt.

Erstellt: 2026-07-08, gegen den damaligen Stand von `main` (92 Commits,
HEAD `141bb63`) verifiziert. Alle Kommandos vom Repo-Root
`/Users/dianakozachek/ToAdapt` ausführen.

Re-Verifikation drift-anfälliger Fakten (je 1 Zeile):

- Commit-Hashes/Daten dieser Chronik: `git log -1 --format="%h | %ad | %s" --date=short <hash>`
- Historien-Umfang (92 Commits, 2026-04-06…): `git rev-list --count main && git log --format=%ad --date=short | tail -1`
- CLAUDE.md noch gitignored/untracked: `git check-ignore -v CLAUDE.md`
- dev-docs-Fossile noch vorhanden: `ls dev-docs/phase1/`
- Toter `websocket_url` noch im Code: `grep -rn "websocket_url" backend/`
- BUILD_MARKER-Relikt: `grep -n "BUILD_MARKER" backend/main.py`
- E402-Ignores + dotenv-Grund: `grep -n -B1 "E402" pyproject.toml && grep -n "load_dotenv" backend/main.py`
- OpenRouter statt Anthropic-SDK: `grep -n "OPENROUTER\|AsyncOpenAI" backend/llm.py`
- Churn-Tabelle neu erzeugen: `git log --name-only --format= | sort | uniq -c | sort -rn | head -12`
- rubric_evaluator-Churn: `git log --oneline -- backend/evaluator/rubric_evaluator.py | wc -l`
- Branch `security-hardening` noch da / noch redundant: `git branch -a && git log main..security-hardening --oneline`
- Restrisiko-Ref `refs/pull/1/head`: `git ls-remote origin 'refs/pull/*'`
- Sensible Daten außerhalb des Repos: `ls ~/ToAdapt_sensitive_data/`
- prolific_runs weiterhin gitignored: `git check-ignore -v data/prolific_runs/x 2>/dev/null; grep -n prolific .gitignore`
