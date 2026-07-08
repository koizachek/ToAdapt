---
name: toadapt-build-and-env
description: >
  Entwicklungsumgebung für das ToAdapt-Repo (FastAPI-Backend + Next.js-Frontend)
  von Null aufbauen. Lade diese Skill, wenn du (a) das Repo frisch geklont hast
  und Backend/Frontend zum Laufen bringen willst, (b) Symptome wie
  "ModuleNotFoundError: No module named 'backend'" bei pytest,
  "mongo_logger_unavailable" im Log, fehlende pytest/pytest-asyncio-Pakete oder
  eine leere/fehlende .env siehst, (c) wissen willst, welche Python-/Node-Version
  gilt, wie docker-compose lokal Mongo bereitstellt oder warum load_dotenv VOR
  den Imports stehen muss (E402-Ignores), oder (d) prüfen willst, ob die
  Umgebung "steht" (Tests grün, uvicorn bootet, /health antwortet).
  Keywords: setup, install, venv, pip, requirements.txt, npm ci, .env,
  .env.local, docker-compose, pytest, tsc, ruff, mypy, Python 3.11, Node 22.
---

# ToAdapt — Umgebung von Null aufbauen

## Wann diese Skill NICHT gilt

| Dein Anliegen | Richtige Skill |
|---|---|
| App lokal STARTEN und bedienen, Railway/Vercel-Deploy, Forschungs-Skripte fahren | `toadapt-run-and-operate` |
| Bedeutung/Wirkung einzelner Env-Variablen, Magic Numbers, TP_CONFIGS | `toadapt-config-and-flags` |
| Laufzeit-Fehler triagieren (401/503/429/404, CORS, guardrail_triggered …) | `toadapt-debugging-playbook` |
| Bevor du irgendetwas änderst/committest/deployst | `toadapt-change-control` |
| Tests ERGÄNZEN, Evidenz-Standards, CI-Gates inhaltlich | `toadapt-validation-and-qa` |
| "Warum ist das so gebaut?" (Architektur, tote Pfade) | `toadapt-architecture-contract`, `toadapt-failure-archaeology` |

Diese Skill deckt ausschließlich ab: Voraussetzungen installieren, Backend-venv,
Frontend-`node_modules`, Env-Dateien anlegen, lokales Mongo via Docker, und die
Verifikation, dass die Umgebung steht.

---

## 0. Kontext in drei Sätzen

ToAdapt ist ein Transfer-Trainer für den BWL-A-Kurs der Universität St.Gallen:
ein FastAPI-Backend (Python, deployt auf Railway) und ein Next.js-Frontend
(deployt auf Vercel) in EINEM Repo. Persistenz ist MongoDB, wenn konfiguriert;
ohne Mongo fällt alles auf In-Memory/Dateien zurück — für lokale Entwicklung
okay, in Produktion Datenverlust. Die Datei `CLAUDE.md` im Repo-Root beschreibt
eine VERWORFENE Gruppen-/WebSocket-Architektur — nicht als Setup-Anleitung
verwenden (Details: `toadapt-failure-archaeology`).

## 1. Voraussetzungen

| Werkzeug | Version | Anmerkung (Stand: 2026-07-08) |
|---|---|---|
| Python | 3.11+ | Produktion ist 3.11 (Dockerfile `python:3.11-slim`, CI `python-version: "3.11"`). Lokal läuft die Suite auch unter 3.13 (verifiziert: 3.13.9). `requires-python = ">=3.11"` in `pyproject.toml`. |
| Node.js | 22+ | CI pinnt Node 22 (`.github/workflows/ci.yml`). Lokal funktioniert auch 24. |
| npm | mit Node geliefert | `npm ci` braucht das eingecheckte `frontend/package-lock.json`. |
| Docker | optional | NUR für lokales MongoDB nötig (`docker-compose.yml`). Backend und Tests laufen auch ohne. |

Prüfe:

```bash
python3 --version   # >= 3.11
node --version      # >= 22
```

## 2. Backend aufsetzen

Alle Kommandos vom Repo-Root (`ToAdapt/`) ausführen.

```bash
# 1) Virtuelle Umgebung ("venv" = isolierte Python-Umgebung im Projektordner)
python3 -m venv .venv

# 2) Laufzeit-Abhängigkeiten
.venv/bin/pip install -r requirements.txt

# 3) Test-Abhängigkeiten — dev-only, ABSICHTLICH NICHT in requirements.txt
#    (CI installiert sie ebenfalls separat; nicht in requirements.txt "nachtragen")
.venv/bin/pip install pytest pytest-asyncio

# 4) Env-Datei anlegen (Variablen-Katalog: Skill toadapt-config-and-flags)
cp .env.example .env
```

Hinweise zur `.env`:

- **Für Tests und den reinen Boot-Check ist KEIN Secret nötig** — die CI läuft
  ohne jegliche Secrets (nur `PYTHONPATH=.`). `OPENROUTER_API_KEY` brauchst du
  erst, wenn du echte Chat-/Evaluator-Aufrufe machen willst.
- `.env` ist gitignored (Zeilen `.env` und `.env.local` in `.gitignore`).
  **Niemals committen** — die Datei enthält im echten Betrieb Secrets.
- `pytest`-Konfiguration liegt in `pyproject.toml`
  (`asyncio_mode = "auto"`, `testpaths = ["tests"]`).

### Tests laufen lassen — IMMER vom Repo-Root

```bash
.venv/bin/python -m pytest tests/ -q
```

Erwartet (Stand: 2026-07-08): `48 passed` in wenigen Sekunden.

**cwd-Falle:** Das `backend`-Paket liegt im Repo-Root und wird über das
Arbeitsverzeichnis importierbar. Startest du pytest aus `tests/` (oder irgendwo
anders), scheitert die Collection mit
`ModuleNotFoundError: No module named 'backend'` (8 Collection-Errors). In CI
wird deshalb `PYTHONPATH=.` gesetzt (`.github/workflows/ci.yml`, Job `backend`).

### Backend-Boot-Check

```bash
.venv/bin/python -m uvicorn backend.main:app --port 8000
```

Erwartete Log-Zeile beim Start (structlog, Console-Renderer in development):

```
toadapt_startup  environment=development llm_provider=openrouter ... tp_phase=1
```

Ohne gesetzten `STUDENT_ACCESS_CODE` folgt zusätzlich die Warnung
`student_flow_open` — im Dev-Betrieb normal, in Produktion ein Alarmsignal
(siehe `toadapt-config-and-flags`). Dann in zweitem Terminal:

```bash
curl -s http://localhost:8000/health
# → {"status":"ok","version":"0.2.0"}
```

(`/health` ist bewusst minimal; der detailreiche, API-Key-geschützte Endpunkt
`/health/diagnostics` gehört zu `toadapt-diagnostics-and-tooling`.)

## 3. Frontend aufsetzen

```bash
cd frontend
npm ci
```

### frontend/.env.local

Es gibt **kein** `.env.local.example` im Repo (Stand: 2026-07-08) — Datei von
Hand anlegen. Variablen (alle Verwendungen im Code verifiziert):

| Variable | Sichtbarkeit | Zweck | Quelle im Code |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Browser (public) | Basis-URL des Backends für den Studenten-Flow; Default `http://localhost:8000` | `frontend/lib/api.ts:1` |
| `BACKEND_API_URL` | nur Server | Backend-URL für den Teacher-Proxy; Fallback auf `NEXT_PUBLIC_API_URL` | `frontend/app/api/teacher/[...path]/route.ts` |
| `TOADAPT_API_KEY` | nur Server | Shared Secret; der Proxy hängt es server-seitig als `X-API-Key` an — MUSS identisch mit Backend-`TOADAPT_API_KEY` sein | dito |
| `TEACHER_ACCESS_CODE` | nur Server | Login-Code für das Teacher-Dashboard | `frontend/app/teacher-login/route.ts:9` |
| `TEACHER_SESSION_SECRET` | nur Server | HMAC-Secret fürs Teacher-Session-Cookie; Teacher-Login wirft ohne dieses Secret einen Fehler | `frontend/lib/teacherAuth.ts:44` |

Minimal für lokalen Studenten-Flow reicht:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Teacher-Bereich lokal testen? Dann zusätzlich `TOADAPT_API_KEY` (identisch zur
Backend-`.env`), `TEACHER_ACCESS_CODE` und `TEACHER_SESSION_SECRET` setzen.

### Frontend-Kommandos (alle in `frontend/`)

| Kommando | Zweck | Erwartung (Stand: 2026-07-08) |
|---|---|---|
| `npm run dev` | Dev-Server auf Port 3000 | Backend parallel auf Port 8000 laufen lassen |
| `npx tsc --noEmit` | TypeScript-Check ohne Build-Output | keine Fehler |
| `npm run lint` | ESLint | 0 Errors, 1 bekannte Warning (`no-page-custom-font` in `app/layout.tsx`) |
| `npm run build` | Produktions-Build | läuft in CI bei jedem Push |

## 4. Docker Compose: API + lokales MongoDB

`docker-compose.yml` (Stand: 2026-07-08) definiert genau **zwei** Services:
`api` (Build aus dem Dockerfile, Port 8000, `env_file: .env`, `MONGODB_URI`
fest auf `mongodb://mongo:27017`) und `mongo` (Image `mongo:7`, Port 27017,
Volume `mongodata`). **Postgres, Redis und ChromaDB wurden entfernt** — der
Code nutzt sie nicht. Ältere Anleitungen (CLAUDE.md, dev-docs/), die sie
erwähnen, sind Fossile.

```bash
# Voraussetzung: .env existiert im Repo-Root (env_file-Referenz)
docker compose up
```

Für reine Backend-Entwicklung ohne Mongo brauchst du Docker nicht — der
Datei-/In-Memory-Fallback greift automatisch (Fallback-Verzeichnisse:
`backend/db/runtime_submissions/`, `backend/db/submissions/`,
`backend/cases/pool/`). UNVERIFIZIERT am 2026-07-08: ein voller
`docker compose up`-Durchlauf (nur `docker compose config --quiet` geprüft —
Datei parst fehlerfrei).

## 5. Bekannte Fallen

| Falle | Symptom | Erklärung / Abhilfe |
|---|---|---|
| pytest aus falschem Verzeichnis | `ModuleNotFoundError: No module named 'backend'` | Vom Repo-Root starten; in CI/Skripten `PYTHONPATH=.` setzen. |
| pytest/pytest-asyncio fehlen | `No module named pytest` | Dev-only, bewusst NICHT in `requirements.txt` — separat installieren (Abschnitt 2). |
| pymongo fehlt im venv | App bootet normal, aber Mongo ist stumm deaktiviert; Log-Warnung `mongo_logger_unavailable` mit `reason=pymongo_not_installed` | pymongo wird in `backend/db/experiment_logger.py` (und `mongo.py`, `submission_store.py`) **optional** importiert — Import-Fehler crashen nicht. `pymongo` steht in `requirements.txt`; bei diesem Symptom ist das venv unvollständig → `pip install -r requirements.txt` erneut. |
| `load_dotenv` vs. Import-Reihenfolge | ruff meldet E402, oder Env-Variablen wirken "leer" | `load_dotenv(...)` MUSS in `backend/main.py` und `backend/db/submission_store.py` VOR den Backend-Imports laufen (Module lesen Env beim Import). Deshalb die absichtlichen `E402`-per-file-ignores in `pyproject.toml` — **nicht "aufräumen"**. Hintergrund (Nixpacks-Saga): `toadapt-failure-archaeology`. |
| ruff nicht im venv | `.venv/bin/ruff: No such file or directory` | ruff ist nicht in `requirements.txt`; CI installiert es ad hoc. Lokal global installiertes ruff nutzen oder `.venv/bin/pip install ruff`. Konfiguration in `pyproject.toml`: `line-length = 100`, `target-version = "py311"`. Kommando: `ruff check .` |
| mypy | Fehlerflut bei `mypy .` | `[tool.mypy] strict = true` ist in `pyproject.toml` konfiguriert, aber mypy läuft NICHT in CI und die Codebase gilt als nicht mypy-clean (UNVERIFIZIERT am 2026-07-08 — mypy ist lokal nicht installiert). Nicht ohne Absprache in CI aufnehmen. |
| `.env` committen | Secrets im Git | `.env`/`.env.local` sind gitignored — so lassen. Vor jedem Commit: `git status` darf keine Env-Dateien zeigen. Historischer PII-Vorfall: `toadapt-failure-archaeology`. |
| `WEB_CONCURRENCY > 1` ohne Mongo | Chat antwortet sporadisch 404 "Session nicht gefunden" | Sessions liegen ohne Mongo nur im Worker-Speicher. Lokal bei 1 Worker bleiben (Details: `toadapt-config-and-flags`). |
| Frontend-Env vergessen | Teacher-Login wirft `TEACHER_SESSION_SECRET nicht konfiguriert`; API-Calls gehen ins Leere | `frontend/.env.local` anlegen (Abschnitt 3); nach Änderung Dev-Server neu starten. |

## 6. Verifikation: "Umgebung steht"

Führe die Sequenz vom Repo-Root aus; jede Zeile nennt den erwarteten Output
(alle am 2026-07-08 so beobachtet):

```bash
# 1) Backend-Tests
.venv/bin/python -m pytest tests/ -q
# → "48 passed"

# 2) Backend bootet
.venv/bin/python -m uvicorn backend.main:app --port 8000
# → Log-Zeile "toadapt_startup" (plus ggf. Warnung "student_flow_open")

# 3) Health-Endpoint (zweites Terminal)
curl -s http://localhost:8000/health
# → {"status":"ok","version":"0.2.0"}

# 4) Frontend-Typen und Lint
cd frontend && npx tsc --noEmit && npm run lint
# → tsc still (keine Fehler); eslint: 0 Errors, 1 bekannte Warning

# 5) Frontend startet
npm run dev
# → Next.js Dev-Server auf http://localhost:3000
```

Alle fünf grün? Umgebung steht. Weiter mit `toadapt-run-and-operate`
(App bedienen, Deploy, Skripte) — und VOR jeder Änderung
`toadapt-change-control` laden.

## Provenance und Wartung

Erstellt: 2026-07-08. Jede Zeile gegen das Repo verifiziert (Tests, uvicorn-Boot,
curl, tsc, eslint am 2026-07-08 real ausgeführt). Drift-anfällige Fakten und
ihr Re-Verifikations-Kommando:

| Fakt | Re-Verifikation |
|---|---|
| "48 passed" | `.venv/bin/python -m pytest tests/ -q` |
| Version "0.2.0" in /health | `grep -n '"version"\|version=' backend/main.py \| head` |
| requirements.txt-Inhalt (kein pytest, pymongo drin) | `cat requirements.txt` |
| CI: Python 3.11, Node 22, PYTHONPATH=. | `grep -nE 'python-version|node-version|PYTHONPATH' .github/workflows/ci.yml` |
| Compose: nur api+mongo | `grep -nE '^  [a-z]+:' docker-compose.yml` |
| E402-Ignores + Zieldateien | `grep -n -A3 per-file-ignores pyproject.toml` |
| Frontend-Env-Variablen | `grep -rn 'process.env.' frontend/lib frontend/app/api frontend/app/teacher-login` |
| Kein frontend/.env.local.example | `ls frontend/.env*` |
| pymongo-Optional-Import-Symptom | `grep -rn mongo_logger_unavailable backend/db/` |
| Node-Pin / Next-Version | `grep -nE '"next"|"react"' frontend/package.json` |
