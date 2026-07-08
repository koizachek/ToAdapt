# ToAdapt — Rollout-Plan (Stand 2026-07-08)

Ziel: Das Repo von der aktuellen Probeversion (Prolific-Experiment, einzelne Dutzend
sequentielle Teilnehmer) zu einem sicher und stabil betreibbaren System für mehrere
hundert gleichzeitige Studierende bringen.

---

## Ausgangslage (Ist-Zustand, verifiziert am 2026-07-08)

**Was das System heute ist:** Ein Single-User-Transfer-Trainer. Ein Teilnehmer wählt
einen AI-generierten Case, chattet per REST mit vier Scaffolding-Agenten
(`backend/agents/orchestrator.py`), schreibt Freitextantworten, die ein LLM-Rubric-
Evaluator bewertet (`backend/evaluator/`); ein Teacher-Dashboard aggregiert Scores.
Es gibt **keine Gruppen, keine WebSockets, kein RAG, kein Gruppengedächtnis, keine
TP-Progression** — die Zielarchitektur in CLAUDE.md ist zu großen Teilen nicht gebaut.

**Security (TODO.md-Review):** Durch Commit `44b4b84` weitgehend behoben — Backend-Auth
(`backend/auth.py`, `X-API-Key` fail-closed auf `/admin`-Schreibrouten und `/dashboard`),
Teacher-Session als signiertes httpOnly-Cookie ohne `0000`-Fallback, CORS auf
`ALLOWED_ORIGINS` eingeschränkt, `/health` minimiert, `.dockerignore`, Next.js 16.2.10.

**Noch offen aus dem Security-Review:**
- Echte Prolific-Teilnehmerdaten (PII) liegen weiterhin in der **Git-History**
  (`data/submission_states.json`, `data/experiment_events.json`,
  `backend/db/dashboard_seed/…` — Commits `e722310`, `00bbcc0`).
- `/chat` reicht Fehlerdetails an den Client durch (`backend/api/routes.py:171`).
- In-Memory-Session-Store (`backend/api/routes.py:38`).

**Betriebslücken für hunderte gleichzeitige Nutzer:**
- Persistenz primär Datei-basiert auf ephemerem Railway-Filesystem
  (`backend/db/runtime_submissions/`); MongoDB nur optionaler Sekundär-Store.
- Ein einziger uvicorn-Prozess (`railway.toml`), Dockerfile startet mit `--reload`.
- LLM-Client ohne Timeout, Retry, Rate-Limiting, Concurrency-Limit; pro Request neue
  Client-Instanz (`backend/llm.py`, `backend/api/routes.py`).
- Studenten-Endpoints (`/sessions`, `/chat`, `/submissions`) bewusst unauthentifiziert
  → jeder im Internet kann LLM-Kosten auslösen.
- Keine CI, kein Error-Tracking, structlog unkonfiguriert, `LOG_LEVEL` wirkungslos,
  Health-Check nicht in Railway verdrahtet.
- `docker-compose.yml` und `.env.example` beschreiben Postgres/Redis/Chroma, die der
  Code nicht nutzt.

---

## Grundsatzentscheidung (vor Phase 2 klären)

Das Repo ist ein anderes Produkt als CLAUDE.md beschreibt. Zwei Wege:

**A) Einzel-Trainer produktionsreif machen** (empfohlen als erster Schritt):
Der bestehende Flow (Case wählen → Chat-Scaffolding → Freitext-Abgabe → Evaluation →
Dashboard) wird für HSG-Studierende ausgerollt. Moderater Aufwand, Phasen 0–1 unten
reichen fast aus.

**B) Umbau zur CLAUDE.md-Zielarchitektur** (6er-Gruppen, WebSocket-Gruppenchat,
Gruppengedächtnis über 4 TPs, RAG auf ON-Case): Großprojekt (mehrere Wochen), setzt
Phase 0–1 ohnehin voraus.

Phasen 0 und 1 sind für beide Wege identisch und sollten sofort starten.

---

## Phase 0 — Sicherheit & Compliance (sofort, vor allem anderen)

> **Status 2026-07-08:** Punkte 1, 2 und 4 erledigt (Repo war bereits privat;
> History mit `git filter-repo` bereinigt und force-gepusht; lokale Rohdaten nach
> `~/ToAdapt_sensitive_data/` verschoben, dort auch das Backup-Bundle der alten
> History; `/chat`-Leak gefixt). **Offen:** Punkt 3 (Secrets-Rotation, nur über die
> externen Dashboards möglich), DSGVO-/Prolific-Meldepflicht-Klärung, sowie der
> alte GitHub-PR-Ref `refs/pull/1/head`, der noch auf die unbereinigte History
> zeigt → GitHub-Support um Löschung bitten oder PR #1 prüfen.

1. **Repo-Sichtbarkeit prüfen und ggf. auf privat stellen**, bis Punkt 2 erledigt ist.
2. **Git-History bereinigen** (`git filter-repo`) für `data/submission_states.json`,
   `data/experiment_events.json`, `data/prolific_runs/`,
   `backend/db/dashboard_seed/teacher_alignment_*.json`; danach Force-Push, alle
   Mitwirkenden clonen neu. Prolific-PIDs sind personenbezogene Daten: DSGVO-/
   Prolific-ToS-Meldepflicht prüfen (ggf. Datenschutzstelle HSG einbeziehen).
   Lokale Rohdaten aus dem Arbeitsverzeichnis in einen sicheren Speicher außerhalb
   des Repos verschieben.
3. **Secrets rotieren**: OpenRouter-Key, MongoDB-Passwort, `TOADAPT_API_KEY`,
   `TEACHER_ACCESS_CODE`, `TEACHER_SESSION_SECRET`.
4. **`/chat`-Fehlerleak schließen**: `backend/api/routes.py:171` gibt
   `f"{type(e).__name__}: {e}"` zurück → generische Meldung, Details nur ins Log.

Aufwand: 0,5–1 Tag (plus organisatorische Klärung Meldepflicht).

## Phase 1 — Betriebsfundament (deploybar & lastfest)

1. **Persistenz konsolidieren — MongoDB als primärer Store** (ist schon angebunden,
   geringster Umbauaufwand):
   - `_sessions`-Dict (`backend/api/routes.py:38`) → Mongo-Collection; Sessions
     überleben Restarts und funktionieren über mehrere Worker.
   - `runtime_submissions/`- und `db/submissions/`-JSONs → Mongo als Source of Truth;
     Datei-Fallback nur noch für lokale Entwicklung.
   - Case-Pool (`backend/cases/pool/`) kann vorerst dateibasiert bleiben (read-mostly,
     im Image), mittelfristig ebenfalls nach Mongo (nötig für Case-Generierung in Prod,
     da Railway-FS ephemer ist — **generierte Cases gehen heute bei Redeploy verloren!**).
2. **LLM-Layer härten** (`backend/llm.py`):
   - Einen gemeinsamen `AsyncOpenAI`-Client in `app.state` (Connection-Reuse).
   - Timeout (~60 s), Retry mit Exponential Backoff auf 429/5xx (2–3 Versuche),
     globales Concurrency-Limit (Semaphore, z.B. 20–30 parallele Calls).
   - Verständliche Fehlermeldung an die UI („Der Assistent ist gerade ausgelastet,
     bitte erneut senden") statt 500.
3. **Studenten-Zugang absichern** (Endpoints sind heute offen):
   - Minimalvariante gemäß PoC-Entscheidung in CLAUDE.md: Zugangscode pro
     Übungsgruppe/Kohorte + signiertes Session-Token (analog `teacherAuth.ts`,
     serverseitig geprüft via FastAPI-Dependency auf `/sessions`, `/chat`,
     `/submissions`).
   - Zusätzlich **Rate-Limiting** (z.B. `slowapi`): pro Session/IP begrenzte
     Chat-Frequenz; schützt Kosten und OpenRouter-Quota.
4. **Deployment fixen**:
   - `railway.toml`: `healthcheckPath = "/health"`, Start mit mehreren Workern
     (uvicorn `--workers 2–4`; Voraussetzung ist Punkt 1, sonst bricht der
     Session-State).
   - Dockerfile: `--reload` entfernen, Non-Root-User, Prod-CMD.
   - `docker-compose.yml` bereinigen (Postgres/Redis/Chroma raus, Mongo lokal rein);
     `.env.example` auf tatsächlich genutzte Variablen reduzieren.
5. **Observability**:
   - `structlog.configure()` mit JSON-Renderer + `LOG_LEVEL`-Anwendung.
   - Sentry (Backend + Frontend) für Error-Tracking.
   - OpenRouter-Kosten-Monitoring: Token-Verbrauch pro Request loggen, Budget-Alarm.

Aufwand: ~1–2 Wochen. Danach ist das System für einige hundert gleichzeitige
Einzelnutzer sicher betreibbar.

## Phase 2 — Feature-Vervollständigung für den Rollout

1. **Interaktive Case-Generierung mit Freigabe-Workflow** (heute nur One-Shot:
   4 Parameter → ein Draft → Approve/Reject in `frontend/app/admin/page.tsx`):
   - Iterativer Editor: einzelne Felder/Sections bearbeiten und gezielt regenerieren
     (LLM-Call mit Feld-Kontext), Vorschau im Studierenden-Layout.
   - Draft-Versionierung + Review-Notizen; Statusfluss Draft → In Review → Approved.
   - Validierungs-Checks vor Approve (Guardrails: keine Framework-Namen, Wortlimits,
     Fragen-Vollständigkeit — automatisch prüfen statt nur manuell lesen).
2. **HSG-Betriebsmodus statt Prolific-Modus**: Prolific-Spezifika (Completion-Code,
   `goodbye/`, `PROLIFIC_PID`-Handling) hinter ein Feature-Flag; Studierenden-Login
   mit Matrikelnummer/Gruppencode; `results/`-Seite in den Standard-Flow.
3. **TP-Progression aktivieren**: `TP_SCHEDULE`/`current_tp_phase()`
   (`backend/config/tp_configs.py`) tatsächlich nutzen statt hardcoded `target_tp: 1`;
   Fortschritt pro Nutzer persistieren; Dashboard nach TP filtern.
4. **Dashboard ausbauen**: neben Scores auch „Wo hängen Studierende?" (häufige
   Guardrail-Trigger, lange Sessions), Aktivität über Zeit.
5. **Nur bei Weg B**: Gruppen-Datenmodell, WebSocket-Gruppenchat, Gruppengedächtnis,
   RAG — als eigenes Projekt planen, nicht in den Rollout des Ist-Systems mischen.

Aufwand: ~2–4 Wochen (ohne Weg B).

## Phase 3 — Qualitätssicherung & gestufter Rollout

1. **CI einrichten** (GitHub Actions): ruff + mypy + pytest (Backend),
   eslint + `next build` (Frontend); Pflicht vor Merge auf `main`.
2. **Tests für die LLM-Pfade** (mit gemocktem Client): Chat-Routing, Guardrail-Fallbacks,
   Evaluator-Fehlerpfade, Auth auf allen Endpoints. Heute testen nur deterministische
   Helfer (`tests/`).
3. **Lasttest** (z.B. locust): 200–300 gleichzeitige Sessions gegen Staging;
   LLM-Calls gemockt für Infrastruktur-Test, kleine Stichprobe real für Quota-Test.
4. **Staging-Umgebung** (zweites Railway-Environment + Vercel-Preview) mit eigenem
   Mongo und eigenem OpenRouter-Key mit Budget-Limit.
5. **Gestufter Rollout**: 1–2 Übungsgruppen als Pilot → Feedback + Kosten-/Lastdaten →
   breiter Rollout. Betriebs-Runbook (Wer reagiert bei Ausfall? Wie rotiert man Keys?
   Wie liest man Sentry/Logs?).

Aufwand: ~1–2 Wochen, teils parallel zu Phase 2.

---

## Reihenfolge / Abhängigkeiten

```
Phase 0 (sofort) ──► Phase 1 ──► Phase 2 ──► Phase 3 (Pilot ► Rollout)
                        │
                        └── Grundsatzentscheidung A/B vor Phase 2
```

Kritischer Pfad für „sicher deploybar": Phase 0 komplett + Phase 1 Punkte 1–4.
Kritischer Pfad für „breit ausrollbar": zusätzlich Phase 1 Punkt 5, Phase 2 Punkte 1–2,
Phase 3 komplett.
