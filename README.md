# ToAdapt

AI-gestützter Transfer-Trainer für BWL A — Universität St. Gallen.

Studierende bearbeiten individuell AI-generierte Mini-Cases und trainieren so den Transfer betriebswirtschaftlicher Denklogiken auf unbekannte Unternehmenskontexte — die Kernkompetenz der summativen Prüfung.

## Architektur

```
Frontend (Next.js → Vercel)
  ↕ REST + WebSocket
FastAPI Backend (→ Railway)
  ├── Case Generator       (AI-Draft: Branche + Land + TP-Ziel → Mini-Case)
  ├── Case Pool            (JSON-basiert, Approval-Workflow für Dozierende)
  ├── Agent Orchestrator   (Metacognitive-first, 4 Agents, Guardrail-Layer)
  ├── Rubric Evaluator     (Bloom-Level-Scoring, scaffolded Feedback)
  ├── Admin Interface      (Case generieren, reviewen, freigeben)
  └── Instructor Dashboard (Matrikelnummer + Scores nach TP/Bloom/Lernziel)
```

## Design-Prinzipien

- **Transfer, nicht Reproduktion** — jeder Case ist ein unbekanntes Unternehmen in einer neuen Branche
- **Scaffolding, nicht Antworten** — Agenten stellen Gegenfragen, geben keine Musterlösungen
- **Metacognitive-first** — jede Session beginnt mit Reflexion vor Inhaltsarbeit
- **Pfadoffene Bewertung** — mehrere valide Antwortpfade erhalten volle Punktzahl
- **Dual-Use** — Studierenden-Submissions aggregieren automatisch zum GA-Kalibrierungs-Dashboard

## Case-Pool Workflow

```
Dozent → POST /admin/cases/generate  (Branche, Land, TP-Ziel)
       → AI erstellt Draft (status: draft)
       → Dozent reviewed im Admin-Interface
       → POST /admin/cases/{id}/approve  (status: approved)
       → Case erscheint im Studierenden-Pool
```

## API-Endpunkte

| Endpunkt | Beschreibung |
|----------|-------------|
| `POST /sessions` | Neue individuelle Session starten |
| `WS /ws/{session_id}` | Scaffolding-Chat mit Agent |
| `POST /submissions` | Submission erstellen |
| `POST /submissions/{id}/answer` | Antwort auf Frage speichern |
| `POST /submissions/{id}/submit` | Abgeben + Evaluieren |
| `POST /admin/cases/generate` | AI-Draft generieren |
| `GET /admin/cases` | Case-Pool einsehen |
| `POST /admin/cases/{id}/approve` | Case freigeben |
| `GET /dashboard/overview` | Kursübersicht |
| `GET /dashboard/student/{matrikel}` | Einzelstudent |

## Tech Stack

| Layer | Technologie |
|-------|-------------|
| Frontend | Next.js, Tailwind, Vercel |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| LLM | Anthropic API (claude-sonnet-4-6) |
| Case Pool | JSON-Dateien (pool/) |
| Scoring Storage | JSON (db/submissions/) |
| Experiment Logging | Optional MongoDB (`MONGODB_URI`) |
| Deployment | Railway (Backend), Vercel (Frontend) |

## Setup

```bash
git clone https://github.com/koizachek/ToAdapt.git
cd ToAdapt
cp .env.example .env  # API Keys eintragen
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

### Optional: Prolific + MongoDB Logging

Für Experimental-Runs kann das Backend strukturierte Events nach MongoDB schreiben. Dafür genügen diese Env-Variablen:

```bash
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=...
MONGODB_COLLECTION=...
```

Alternativ kann die Verbindung aus bestehenden Credentials aufgebaut werden:

```bash
MONGODB_MAS_NAME=...
MONGODB_MAS_KEY=...
MONGODB_HOST=cluster0.xxxxx.mongodb.net
MONGODB_DATABASE=...
MONGODB_COLLECTION=...
```

Wenn Prolific die Landing-Page mit `PROLIFIC_PID`, `STUDY_ID` und `SESSION_ID` aufruft, werden diese Werte automatisch ins Backend durchgereicht und zusammen mit Session-, Chat- und Submission-Events geloggt.

### Lokale Prolific-Exporte

Falls rohe Exportdateien aus Prolific im Repo mitliegen sollen, aber nicht versioniert werden duerfen, gibt es dafuer den lokalen Pfad `data/prolific_runs/`.

```bash
python scripts/import_prolific_runs.py ~/Downloads/prolific-export --batch may-2026-pilot
```

Der Import legt die Originaldateien unter `data/prolific_runs/raw/<batch>/` ab und schreibt dazu ein Manifest mit Dateiliste und Checksummen nach `data/prolific_runs/manifests/`.

### Review-Exporte als Excel

Falls `data/submission_states.json` vorliegt, lassen sich daraus zwei Review-Dateien erzeugen:

```bash
python scripts/export_review_workbooks.py
```

Der Export schreibt bis zu drei Excel-Dateien nach `data/prolific_runs/derived/review_exports/`:

- `*_rubric.xlsx`: pro Frage ein Blatt mit Antworten, `user_id`, Prolific-IDs und der bestehenden Rubric-Bewertung
- `*_blind.xlsx`: pro Frage ein Blatt ohne Personenkennung und ohne Rubric-Bewertung, dafuer mit Feldern fuer `teacher_awarded_points` und `teacher_rationale`
- `*_chat_turns.xlsx`: separate Datei mit einer Zeile pro Bot-Interaktion aus `experiment_events.json`, inklusive `user_message`, `assistant_message`, `agent_type`, `message_count` und Session-/Prolific-Kontext

Beide Dateien teilen dieselbe `review_item_id`, damit menschliche Bewertungen spaeter leicht mit den Rubric-Scores abgeglichen werden koennen.

## Guardrails

- Keine Framework-Namen in Agent-Antworten (Porter, RBV, VRIO, TCE, 4P …)
- Keine direkten Antworten oder Musterlösungen
- TP-phasenspezifische Framework-Beschränkungen (aus `tp_configs.py`)
- NORDIC HOME und ON dürfen in generierten Cases nicht vorkommen

## License

MIT
