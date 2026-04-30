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
| Deployment | Railway (Backend), Vercel (Frontend) |

## Setup

```bash
git clone https://github.com/koizachek/ToAdapt.git
cd ToAdapt
cp .env.example .env  # API Keys eintragen
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

## Guardrails

- Keine Framework-Namen in Agent-Antworten (Porter, RBV, VRIO, TCE, 4P …)
- Keine direkten Antworten oder Musterlösungen
- TP-phasenspezifische Framework-Beschränkungen (aus `tp_configs.py`)
- NORDIC HOME und ON dürfen in generierten Cases nicht vorkommen

## License

MIT
