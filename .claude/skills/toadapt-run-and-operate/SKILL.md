---
name: toadapt-run-and-operate
description: >
  Betriebs-Runbook für ToAdapt: lokal starten (uvicorn-Backend, Next.js-Frontend,
  docker compose), Smoke-Test per curl (health, /auth/student/verify,
  Teacher-Login), Deploy-Anatomie Railway (Nixpacks, railway.toml) + Vercel,
  Scharf-Schalten-Checkliste für Produktion (Env-Reihenfolge, WEB_CONCURRENCY),
  wo Daten landen (Mongo-Collections vs. Datei-Fallbacks, ephemeres Railway-FS),
  Bedienung der 5 Forschungs-Skripte in scripts/ (import → export → compare →
  retry → publish) und Secrets-Ablage. Lade diese Skill bei Aufgaben wie:
  "starte das System lokal", "deploye", "geht der Server?", "wo liegen die
  Submissions?", "Daten nach Redeploy weg", "Review-Workbooks exportieren",
  "Prolific-Daten importieren", "Teacher-Alignment-Vergleich rechnen",
  "welches Secret gehört wohin?", "STUDENT_ACCESS_CODE scharf schalten".
---

# ToAdapt — Run & Operate

## Wann diese Skill NICHT gilt

| Frage | Richtige Skill |
|---|---|
| Etwas ist kaputt (401/503/429/404, CORS, technical_fallback, Guardrail-Fallbacks) | `toadapt-debugging-playbook` |
| Bedeutung/Wirkung einzelner Env-Variablen und Magic Numbers | `toadapt-config-and-flags` |
| Umgebung von Null aufbauen (venv, npm install, bekannte Fallen) | `toadapt-build-and-env` |
| Darf ich das ändern/pushen/deployen? Gates, Unverhandelbares | `toadapt-change-control` |
| Diagnose-Endpoint/Log-Events im Detail, Messen statt Schätzen | `toadapt-diagnostics-and-tooling` |
| Tests ausführen/ergänzen, Evidenz-Standards, CI-Gates | `toadapt-validation-and-qa` |
| Warum die Architektur so ist (Auth-Pfade, Stores, kein WebSocket) | `toadapt-architecture-contract` |
| BWL-Fachbegriffe (TP, Bloom, Canvas, Judge) | `bwl-scaffolding-reference` |

## 30-Sekunden-Kontext

ToAdapt ist ein Transfer-Trainer für den BWL-A-Kurs: Studierende bearbeiten
einzeln AI-generierte Mini-Business-Cases, chatten mit Scaffolding-Agenten
(Agenten, die Denkfragen stellen statt Antworten zu geben) und werden von
einem LLM-Judge (LLM, das Freitextantworten nach Rubric bewertet) gescored.
Betriebstopologie:

- **Backend:** FastAPI (Python), deployt auf **Railway** (PaaS), LLM-Calls via OpenRouter.
- **Frontend:** Next.js (App Router), deployt auf **Vercel**.
- **Persistenz:** MongoDB primär; ohne Mongo Datei-/In-Memory-Fallbacks (nur Dev-tauglich).
- Es gibt **keine WebSockets** — Chat läuft über HTTP POST (das `websocket_url`-Feld in der Session-Response ist ein totes Relikt).

---

## 1. Lokal starten

Voraussetzungen (Details: `toadapt-build-and-env`): Python-venv unter `.venv/`,
Root-`.env` (Vorlage: `.env.example`), `frontend/node_modules` installiert.

### Backend (Port 8000)

Führe im Repo-Root aus:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --port 8000
```

`backend/main.py` lädt die Root-`.env` selbst via `load_dotenv` (Zeile 14) —
kein manuelles Sourcen nötig. Prüfe im Startup-Log (structlog, in Dev als
Console-Renderer):

- Event `toadapt_startup` mit `openrouter_api_key_configured=True` (sonst schlägt jeder Chat/Submit fehl),
- `mongo_logging_enabled` / `mongo_connection_mode` (ohne Mongo: `disabled`),
- Warnung `student_flow_open`, falls `STUDENT_ACCESS_CODE` leer ist — dann sind Sessions/Chat/Submissions ohne Code erreichbar.

### Frontend (Port 3000)

```bash
cd frontend && npm run dev
```

`frontend/.env.local` braucht mindestens `TEACHER_ACCESS_CODE`,
`TEACHER_SESSION_SECRET` und `TOADAPT_API_KEY` (identisch zum Backend-Wert),
sonst liefert der Teacher-Bereich 503/Redirects. `NEXT_PUBLIC_API_URL` ist
optional — Default ist `http://localhost:8000` (`frontend/lib/api.ts:1`).

### Alternative: Docker (API + lokale MongoDB)

```bash
docker compose up
```

`docker-compose.yml` startet `api` (Port 8000, liest Root-`.env`, setzt
`MONGODB_URI=mongodb://mongo:27017`) und `mongo` (mongo:7, Volume
`mongodata`). Das `Dockerfile` ist NUR für lokalen Betrieb — Railway baut
per Nixpacks und ignoriert es (siehe §3).

---

## 2. Smoke-Sequenz (curl)

Alle erwarteten Antworten am 2026-07-08 gegen den lokalen Server verifiziert.
`$API` = `http://localhost:8000` (lokal) bzw. die Railway-URL.

### 2.1 Health

```bash
curl -s $API/health
# → {"status":"ok","version":"0.2.0"}
```

Bewusst minimal (keine Infra-Details auf öffentlichem Endpoint).

### 2.2 Studenten-Zugangscode

```bash
# Ohne Header, wenn STUDENT_ACCESS_CODE gesetzt ist:
curl -s -o /dev/null -w "%{http_code}\n" -X POST $API/auth/student/verify
# → 401

# Mit korrektem Code:
curl -s -X POST $API/auth/student/verify -H "X-Student-Access-Code: <CODE>"
# → {"ok":true,"required":true}

# Wenn KEIN Code konfiguriert ist (offener Dev-Modus):
# → {"ok":true,"required":false}   (auch ohne Header)
```

Derselbe Header `X-Student-Access-Code` wird von ALLEN Studierenden-Endpunkten
verlangt (Router-Dependency in `backend/api/routes.py:38`); das Frontend hängt
ihn aus `sessionStorage` an (`frontend/lib/api.ts`).

### 2.3 Diagnostics (X-API-Key-geschützt)

```bash
curl -s $API/health/diagnostics -H "X-API-Key: <TOADAPT_API_KEY>"
```

Erwartet: JSON mit `"status":"ok"`, `tp_phase`, `build_marker` (Relikt
`railway-mongo-env-diagnostics-2026-05-14-1809z`), `mongo_logging_enabled`,
`mongo_connection_mode` (`uri` | `mas_credentials` | `disabled`),
`mongo_env_keys` und Längen-Feldern. Ohne Header: 401. Ist
`TOADAPT_API_KEY` serverseitig NICHT gesetzt: 503 (fail-closed,
`backend/auth.py`).

### 2.4 Case-Liste (öffentlich lesbar)

```bash
curl -s "$API/admin/cases?status=approved"
```

Die lesenden `/admin/cases`-GETs sind bewusst ohne Key (das Studierenden-
Frontend lädt darüber die approved Cases); nur schreibende Admin-Routen und
alle `/dashboard/*`-Routen verlangen `X-API-Key`.

### 2.5 Teacher-Login-Flow (über das Frontend, nicht das Backend)

Der Teacher-Login läuft komplett im Next.js-Frontend:

1. `POST /teacher-login` (Form-Feld `teacher_code`) an das FRONTEND —
   `frontend/app/teacher-login/route.ts` prüft gegen `TEACHER_ACCESS_CODE`
   und setzt das signierte httpOnly-Cookie `teacher_session` (HMAC-SHA256
   mit `TEACHER_SESSION_SECRET`, 12 h gültig; `frontend/lib/teacherAuth.ts`).
2. `frontend/middleware.ts` schützt `/admin/*` und `/dashboard/*` (Redirect
   auf `/?mode=teacher` ohne gültiges Cookie).
3. Teacher-API-Calls gehen über den same-origin Proxy
   `frontend/app/api/teacher/[...path]/route.ts`, der server-seitig den
   `X-API-Key` (aus `TOADAPT_API_KEY`) ergänzt — der Key erreicht den
   Browser nie.

Smoke im Browser: `http://localhost:3000/?mode=teacher` → Code eingeben →
Redirect auf `/cases`; danach muss `/dashboard` laden (Proxy → Backend).

---

## 3. Deploy-Anatomie

### Railway (Backend)

- Baut per **Nixpacks** (Railway-eigener Builder, KEIN Dockerfile) aus dem
  GitHub-Repo, Branch `main`.
- `railway.toml` (Repo-Root) steuert den Start:

```toml
startCommand = "sh -c 'uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers ${WEB_CONCURRENCY:-1} --proxy-headers --forwarded-allow-ips=\"*\"'"
healthcheckPath = "/health"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

  - `--proxy-headers`: Client-IPs aus `X-Forwarded-For` — nötig fürs
    IP-basierte Rate-Limiting hinter dem Railway-Proxy.
  - `WEB_CONCURRENCY` (Default 1) = Anzahl uvicorn-Worker. **>1 NUR mit
    verifiziertem Mongo** (siehe §4) — sonst liegen Sessions nur im
    Speicher EINES Workers und der andere antwortet mit 404.
- Das **Railway-Dateisystem ist ephemer**: alles unter `backend/db/…` und
  `backend/cases/pool/`, das zur Laufzeit geschrieben wird, ist nach dem
  nächsten Deploy weg (siehe §5).

### Vercel (Frontend)

- Vercel baut das Next.js-Frontend; es gibt KEIN `vercel.json` im Repo —
  Projekt-Einstellungen (Root Directory `frontend/`, Env-Variablen) leben
  ausschließlich im Vercel-Dashboard (UNVERIFIZIERT aus dem Repo heraus;
  Stand 2026-07-08 laut ROLLOUT_PLAN.md noch nicht vollständig scharf
  geschaltet).

### Die eine Regel daraus

**Jeder Push auf `main` deployt Backend (Railway) UND Frontend (Vercel).**
Es gibt keine Branch Protection und kein Staging (Stand: 2026-07-08). Also:

- Kein WIP/Debug-Commit auf `main` — jede halbfertige Änderung geht sofort live.
- Vor dem Push: CI-relevante Checks lokal laufen lassen (siehe
  `toadapt-validation-and-qa`) und Gates aus `toadapt-change-control` beachten.
- Backend- und Frontend-Änderung im selben Push halten, wenn sie sich
  gegenseitig brauchen (z. B. neues API-Feld + UI-Nutzung).

---

## 4. Produktion scharf schalten — Checkliste (Reihenfolge einhalten!)

Die Reihenfolge existiert, weil `WEB_CONCURRENCY>1` ohne funktionierende
Mongo-Verbindung laufende Chats mit `404 Session nicht gefunden` zerschießt
(Sessions haben KEINEN Datei-Fallback, nur Mongo oder Worker-RAM).

1. **Railway-Variablen setzen** (Werte-Referenz: `toadapt-config-and-flags`):
   `OPENROUTER_API_KEY`, `TOADAPT_API_KEY`, `ALLOWED_ORIGINS`
   (= konkrete Vercel-Domain, kommagetrennt), `ENVIRONMENT=production`
   (schaltet JSON-Logs), MongoDB-Zugang (`MONGODB_URI` ODER
   `MONGODB_MAS_NAME`+`MONGODB_MAS_KEY`+`MONGODB_HOST`), optional
   `SENTRY_DSN`. `WEB_CONCURRENCY` noch NICHT anfassen.
2. **Deploy auslösen/abwarten**, dann `curl $API/health` → `{"status":"ok",...}`.
3. **Mongo verifizieren:**
   ```bash
   curl -s $API/health/diagnostics -H "X-API-Key: <TOADAPT_API_KEY>"
   ```
   Prüfe: `mongo_logging_enabled: true`, `mongo_connection_mode` ≠
   `disabled`, `mongo_last_connection_failure: 0.0`. Erst wenn das stimmt →
   Schritt 4.
4. **`WEB_CONCURRENCY=2` setzen** (Railway-Variable), Redeploy, Schritt 2–3
   wiederholen. Danach einen Chat-Roundtrip testen (Session anlegen, 2+
   Chat-Nachrichten) — mit 2 Workern deckt das Worker-übergreifendes
   Session-Loading ab.
5. **`STUDENT_ACCESS_CODE` setzen** und den Code an die Kohorte
   kommunizieren (Reihenfolge egal, aber beides vor Kursnutzung; solange er
   leer ist, warnt das Startup-Log `student_flow_open` — dann kann jeder im
   Internet LLM-Kosten auslösen).
6. **Vercel-Variablen prüfen** (siehe §7) und Teacher-Login-Smoke (§2.5)
   gegen die Prod-Domain fahren.

---

## 5. Wo Daten landen

Grundmuster in allen Stores: Mongo, wenn konfiguriert; sonst Fallback. Der
In-Memory-Cache in `backend/api/routes.py` (`_sessions`, `_submissions`)
liegt IMMER davor (prozesslokal).

| Datenart | Mongo-Collection (Env-Override) | Fallback ohne Mongo | Code |
|---|---|---|---|
| Chat-Sessions | `sessions` (`MONGODB_SESSIONS_COLLECTION`) | **NUR In-Memory** — weg bei Restart, unsichtbar für andere Worker | `backend/db/session_store.py` |
| Submission-Zustände (Antworten, Status, Scores) | `submission_states` (`MONGODB_SUBMISSIONS_COLLECTION`) | Dateien `backend/db/runtime_submissions/*.json` | `backend/db/submission_store.py` |
| Dashboard-Ergebnisse (evaluierte Scores) | `dashboard_results` (`MONGODB_DASHBOARD_COLLECTION`) | Dateien `backend/db/submissions/*.json` | `backend/db/dashboard_store.py` |
| Forschungs-Events (jeder Chat-Turn, jede Submission) | `experiment_events` (`MONGODB_COLLECTION`) | **KEINER — Events werden stillschweigend verworfen** | `backend/db/experiment_logger.py` |
| Cases | `cases` (fest) | Dateien `backend/cases/pool/*.json` (kuratierte Cases sind zusätzlich im Repo/Image) | `backend/cases/manager.py` |

Datenbank-Name: `MONGODB_DATABASE` (Default `toadapt`).

**Konsequenzen:**

- **Railway ohne Mongo = Datenverlust bei jedem Redeploy** (ephemeres FS):
  Datei-Fallbacks und zur Laufzeit generierte Cases verschwinden;
  `experiment_events` gehen sofort verloren. Datei-Fallbacks sind reine
  Dev-Bequemlichkeit.
- `backend/db/runtime_submissions/` und `backend/db/submissions/*.json` sind
  gitignored (enthalten personenbezogene Antworten) — niemals committen.
- Bei Mongo-Verbindungsfehler wird 30 s lang nicht neu verbunden
  (Backoff in den Stores) — kurze Ausfälle heilen sich selbst.

---

## 6. Forschungs-Pipeline bedienen (scripts/)

Zweck: Judge-Scores gegen Blind-Bewertungen einer Lehrkraft alignen
("Teacher-Alignment"). Alle Skripte laufen vom **Repo-Root** mit
`.venv/bin/python`. Reihenfolge:

```
1) import_prolific_runs      Rohdaten versioniert ablegen (SHA-256-Manifest)
2) export_review_workbooks   Excel-Workbooks erzeugen (rubric + blind + chat_turns)
3) [Mensch] Lehrkraft füllt das BLIND-Workbook aus (ohne Judge-Scores)
4) compare_teacher_rubric_scores   Metriken Lehrer vs. Judge (Pearson, MAE, RMSE)
5) retry_technical_fallback_scores [optional — ACHTUNG: echte LLM-Calls, kostet Geld]
6) publish_dashboard_scores  Evaluierte Scores in den Dashboard-Store publizieren
```

### 6.1 Import

```bash
.venv/bin/python scripts/import_prolific_runs.py ~/Downloads/prolific-export --batch may-2026-pilot
```

Input: Datei ODER Verzeichnis. Output: `data/prolific_runs/raw/<batch>/`
(unveränderte Kopien) + `data/prolific_runs/manifests/<batch>.json`
(Dateiliste, Größen, SHA-256). Optional `--dest-root` für anderen Zielort.

### 6.2 Workbooks exportieren

```bash
.venv/bin/python scripts/export_review_workbooks.py \
  --submissions data/submission_states.json \
  --events data/experiment_events.json \
  --prefix prolific_review
```

Defaults: `--submissions data/submission_states.json`, `--events
data/experiment_events.json`, `--cases-dir backend/cases/pool`,
`--output-dir data/prolific_runs/derived/review_exports`. Output: drei
xlsx-Dateien `{prefix}_{timestamp}_rubric.xlsx` (mit Judge-Scores),
`…_blind.xlsx` (OHNE Judge-Scores — dieses bekommt die Lehrkraft) und
`…_chat_turns.xlsx`. Join-Schlüssel über alle Artefakte:
`review_item_id` = `{case_id}:{question_id}:{nnn}`.

### 6.3 Vergleich rechnen

```bash
.venv/bin/python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook <ausgefülltes_blind.xlsx> \
  --rubric-workbook <..._rubric.xlsx>
```

Output nach `data/prolific_runs/derived/`: Workbook (5 Blätter) + CSV
(Semikolon-getrennt), Prefix via `--prefix` (Default
`teacher_rubric_comparison`). Das Lehrer-Workbook ist kanonisch: Judge-Zeilen
ohne passende `review_item_id` werden bewusst ausgeschlossen (bereinigte
Testuser bleiben draußen).

### 6.4 Technical-Fallbacks nachbewerten (echtes LLM!)

`technical_fallback` = Judge-Ergebnis, bei dem das LLM-JSON auch nach
Repair-Versuch nicht parsebar war → 0 Punkte, `needs_human_review`. Dieses
Skript wiederholt NUR diese Bewertungen:

```bash
# Erst IMMER Dry-Run (keine LLM-Calls, zeigt nur Kandidaten):
PYTHONPATH=. .venv/bin/python scripts/retry_technical_fallback_scores.py --dry-run
# Dann scharf (verursacht OpenRouter-Kosten, braucht OPENROUTER_API_KEY):
PYTHONPATH=. .venv/bin/python scripts/retry_technical_fallback_scores.py
```

`PYTHONPATH=.` ist PFLICHT (das Skript importiert `backend.*`; ohne bricht es
mit `ModuleNotFoundError: No module named 'backend'` ab — am 2026-07-08
verifiziert). Liest/schreibt `backend/db/submissions/*.json` (`--dashboard-dir`),
Antworttexte aus einer Vergleichs-CSV (`--comparison-csv`, Default zeigt auf
einen historischen Lauf unter `data/prolific_runs/derived/aligned_rescores/`).
Eingrenzen mit `--submission-id <id>` (wiederholbar). Vor einem scharfen Lauf
gilt das Judge-Gate aus `toadapt-change-control`.

### 6.5 Publizieren

```bash
.venv/bin/python scripts/publish_dashboard_scores.py <source.json>
```

Input: JSON-Liste von Submission-Zuständen. Schreibt NUR Einträge mit
`status == "evaluated"` UND vorhandenen Scores als Einzeldateien nach
`backend/db/submissions/` (`--output-dir` überschreibbar) und druckt
`published/skipped/needs_human_review_count/technical_fallback_count`.

### 6.6 Daten-Disziplin

- `data/prolific_runs/**` ist komplett gitignored (nur das README ist
  getrackt) — Konvention: `raw/` (unverändert), `manifests/`, `derived/`.
- **Echte Teilnehmerdaten liegen in `~/ToAdapt_sensitive_data/`** (seit
  2026-07-08, inkl. Backup-Bundle der alten Git-History) und kommen NIEMALS
  zurück ins Repo — nicht als Fixture, nicht als Beispiel, nicht in Skills.
  Für Tests synthetische Daten verwenden.

---

## 7. Secrets-Handling — wo welches Secret lebt

| Secret / Variable | Lokal | Produktion | Zweck |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Root-`.env` | Railway | LLM-Calls (Agenten + Judge) |
| `TOADAPT_API_KEY` | Root-`.env` UND `frontend/.env.local` (identischer Wert!) | Railway UND Vercel | Shared Secret `X-API-Key` für /dashboard/* + schreibende /admin-Routen; Frontend-Seite nur im Server-Proxy, nie im Browser |
| `STUDENT_ACCESS_CODE` | Root-`.env` (Dev meist leer) | Railway | Kohorten-Code für den Studierenden-Flow; leer = offen |
| `MONGODB_URI` bzw. `MONGODB_MAS_NAME`/`MONGODB_MAS_KEY`/`MONGODB_HOST` | Root-`.env` | Railway | Mongo-Zugang (eine der beiden Formen) |
| `TEACHER_ACCESS_CODE` | `frontend/.env.local` | Vercel | Teacher-Login-Code (fail-closed: ohne Wert kein Login) |
| `TEACHER_SESSION_SECRET` | `frontend/.env.local` | Vercel | HMAC-Key des Teacher-Session-Cookies |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` (optional) | Vercel | Browser→Backend-Basis-URL (öffentlich, kein Secret) |
| `BACKEND_API_URL` | `frontend/.env.local` (optional) | Vercel | Server-seitige Backend-URL für den Teacher-Proxy (Fallback: `NEXT_PUBLIC_API_URL`) |
| `SENTRY_DSN` | optional | Railway | Error-Tracking Backend (Frontend hat KEIN Sentry) |

Regeln:

- `.env` und `.env.local` sind gitignored und waren nie getrackt — so lassen.
- Key erzeugen: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- Ein historisches `SECRET_KEY` in alten `.env`-Dateien wird nirgends im Code
  verwendet — ignorieren/entfernen.
- Keine Key-Werte oder -Präfixe in Logs/Commits/Skills; das Startup-Log loggt
  bewusst nur boolesche Konfigurationsflags.

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle curl-Antworten in §2 wurden an diesem Tag gegen
einen lokal gestarteten Server verifiziert; Deploy-Zustand (Railway/Vercel
"scharf geschaltet"?) ist volatil — maßgeblich ist der Status-Block in
`ROLLOUT_PLAN.md`.

Re-Verifikation pro drift-anfälligem Fakt:

- Start-Kommando/Worker/Healthcheck: `cat railway.toml`
- Health-/Diagnostics-Endpunkte und Version: `grep -n '"version"\|/health' backend/main.py`
- Studenten-Header + Verify-Route: `grep -n "X-Student-Access-Code\|auth/student/verify" backend/auth.py backend/api/routes.py`
- Rate-Limits der Studenten-Routen: `grep -n "rate_limit(" backend/api/routes.py`
- Collection-Namen + Fallback-Pfade: `grep -rn "COLLECTION\", \|_DIR = Path" backend/db/*.py backend/cases/manager.py`
- Skript-Argumente: `for f in scripts/*.py; do PYTHONPATH=. .venv/bin/python $f --help; done`
- Env-Katalog aktuell?: `git log -1 --format=%ci -- .env.example` (und mit `toadapt-config-and-flags` abgleichen)
- Vercel-/Rollout-Status: `grep -n "Vercel\|Railway" ROLLOUT_PLAN.md`
- Teacher-Auth-Flow: `ls frontend/app/teacher-login frontend/app/api/teacher; grep -n MAX_AGE frontend/lib/teacherAuth.ts`
