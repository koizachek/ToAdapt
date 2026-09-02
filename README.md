# ToAdapt

AI-gestützter Transfer-Trainer für Business Cases

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
| `POST /briefings/upload` | Master-Upload: ZIP mit Stammgruppen-Abgaben → KI-Briefings (nur Master) |
| `GET /briefings?tp=&ueg=` | Briefings (ÜGL: nur eigene Übungsgruppe) |
| `GET /briefings/overview?tp=` | Je Übungsgruppe: vorhandene/fehlende Stammgruppen |
| `GET /briefings/docx?tp=&ueg=` | DOCX mit allen Briefings einer Übungsgruppe |
| `GET /briefings/{id}/docx` | DOCX eines einzelnen Briefings |
| `GET /briefings/{id}/assessment` | Interne Kriterien-Einstufung (nur Master) |
| `PATCH /briefings/{id}` | Zuordnung Übungsgruppe/Stammgruppe nachtragen (nur Master) |
| `GET /briefings/batches`, `/batches/{id}` | Status der Upload-Batches (nur Master) |
| `GET /briefings/{id}/feedback/docx` | KI-Feedback einer Stammgruppe (DOCX) — erst nach dem Termin (423 vorher) |
| `GET /briefings/feedback/zip?tp=&ueg=` | ZIP mit einem Feedback-DOCX je Stammgruppe — erst nach dem Termin |

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

## Aktueller Stand

- Das Frontend hat zwei Modi. Studierende nutzen den bestehenden Studien-/Case-Flow. Lehrkräfte melden sich auf der Startseite mit einem Zugangscode an und sehen danach `Cases`, `Dashboard` und `Admin` direkt in der oberen Navigation.
- Der Lehrkräfte-Code wird serverseitig über `TEACHER_ACCESS_CODE` geprüft. Lokal ist `0000` möglich, der Code wird im Frontend nicht angezeigt.
- Der LLM-as-a-Judge ist an die Lehrerbewertung kalibriert: Rubric-Scores enthalten jetzt Confidence, Score-Band, Review-Flags, technische Fallbacks, Stärken und Abzüge.
- Die zuletzt neu bewertete Datei liegt lokal unter `data/prolific_runs/derived/aligned_rescores/submission_states_aligned_20260531T140830Z.json`.
- Der Vorher-Nachher-Bericht liegt unter `data/prolific_runs/derived/aligned_rescores/teacher_alignment_report_20260531.md`.
- Die bereinigte Nutzerbasis bleibt maßgeblich. Fehlende Testnutzer oder schlechte Outputs werden nicht wieder eingefügt, solange mit der bereinigten Submission-Datei gearbeitet wird.

## Bewertungen ins Lehrkräfte-Dashboard übertragen

Das Dashboard liest live aus `backend/db/submissions/*.json`. Neue Online-Abgaben werden dort beim Submit automatisch geschrieben. Für bereits neu bewertete Prolific-/Alignment-Dateien gibt es einen Publish-Schritt:

```bash
python scripts/publish_dashboard_scores.py data/prolific_runs/derived/aligned_rescores/submission_states_aligned_20260531T140830Z.json
```

Danach erscheinen die bewerteten Abgaben direkt im Lehrkräfte-Dashboard unter `/dashboard`, inklusive Review-Flags und technischen Fallbacks. Die Rohdatei unter `data/prolific_runs/` wird dabei nicht verändert.

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

## Pilotphase HS26: nur Tutorenansicht

In der Pilotphase ist ausschliesslich die Tutorenansicht freigeschaltet. Studierenden-Flow,
Case-Ansicht, Case-Generator (Admin) und das Individual-Dashboard bleiben im Code, werden aber
nicht angezeigt. Es gibt zwei Rollen: der **Master-Tutor** (Login mit `TEACHER_ARCHIVE_CODE`)
lädt den Canvas-Export hoch und lädt alles herunter; jede **Übungsgruppenleitung** (Einzelcode
aus `TEACHER_ACCESS_CODES`) sieht ihre eigenen Übungsgruppen und lädt deren Briefings und
Feedbacks herunter. Schalter: Frontend `NEXT_PUBLIC_PILOT_TUTOR_ONLY` (Vercel, Standard AN;
`0` schaltet die Studierenden frei), Backend `PILOT_TUTOR_ONLY=1` (Railway; sperrt
Studierenden-API und Case-Generator mit 503 — empfohlen, damit die versteckten Endpoints nicht
offen bleiben). Die Freischaltung der Studierenden ist damit ein Env-Wechsel, kein Umbau.

## KI-Briefings für Übungsgruppenleitungen (Tutor-Pipeline)

Die Stammgruppen geben ihre Touchpoint-Ergebnisse über Canvas (LMS) ab — als PPTX aus der
offiziellen Vorlage (Code `TPn-UEGxx-SGy`), ersatzweise DOCX oder PDF. Der Master-Tutor lädt
den Canvas-Export als ZIP hoch (`POST /briefings/upload`, `target_tp` 1–5); je Datei entsteht
ein Briefing für die ÜGL nach dem KI-Paket der Kursleitung: je Baustein Kernposition (ein Satz),
tragende Argumente (max. 2), dünne Stellen als Rückfrage-Ansatz (max. 2) und eine Einschätzung
in Prosa. Dazu die formale Vorprüfung (Zeichengrenzen je Folie, Code, Dateiname — gemeldet,
nie bewertet). Die Niveau-Einstufung je Kriterium wird intern gespeichert und ist nur für den
Master sichtbar. Keine Punkte, keine Musterlösung, kein Gruppenvergleich; Leitplanken werden
nach dem LLM-Call regelbasiert nachgeprüft (`backend/briefings/guardrails.py`).

- Code: `backend/briefings/` (Extraktion, Rubrics, Generator, DOCX-Renderer, Routen),
  Store `backend/db/briefing_store.py` (Mongo `briefings`, Datei-Fallback `backend/db/briefings/`).
- Config: `backend/config/ki_rubrics/` — `ki_rubrics_tp{n}.json` (Kursleitung, 2026-08-28),
  Case-Kapitel des Running Case ON (`case/kapitel_{a..e}.md`, nur Tutor-Pipeline, nie
  studierendensichtbar), Vorlagentexte (`template_texts.json`).
- Sichtbarkeit: Der Teacher-Proxy schickt `X-Teacher-Id` und `X-Teacher-Master` mit. Konvention:
  Tutor-Kennung nennt die Übungsgruppe(n) — `TEACHER_ACCESS_CODES = {"UEG07": "<code>",
  "UEG08+UEG12": "<code>", …}`; eine ÜGL sieht nur ihre eigenen Übungsgruppen, der Master alles.
  Der Download `GET /briefings/docx?tp=` liefert bei einer Übungsgruppe das DOCX, bei mehreren ein
  ZIP mit je einem einheitlichen Briefing-DOCX pro Übungsgruppe (`ueg=` wählt eine aus). Hochgeladene
  Dateien und Mitgliedernamen werden nie gespeichert.
- Kalibrierung (Pflicht vor Prompt-/Rubric-Änderungen): `python scripts/calibrate_briefings.py --all`
  schickt die drei Beispielabgaben je TP durch den Generator und vergleicht die Einstufung.
- **Upload-Weg (Vercel-Limit):** Vercel begrenzt Request-Bodies von Route-Handlern auf 4,5 MB
  (Infrastruktur-Limit). Der Master-Upload geht deshalb **direkt vom Browser an Railway**:
  `POST /api/teacher/upload-token` (Frontend, nur Master-Session) signiert ein 15-Minuten-Token mit
  `TOADAPT_API_KEY`; der Browser schickt das ZIP mit Header `X-Upload-Token` an
  `NEXT_PUBLIC_API_URL/briefings/upload` (bis 400 MB). Voraussetzungen: `ALLOWED_ORIGINS` (Railway)
  enthält die Vercel-Domain; `TOADAPT_API_KEY` ist auf beiden Seiten identisch. Die Verarbeitung
  läuft asynchron (Antwort 202 mit `batch_id`, Fortschritt über `GET /briefings/batches/{id}`),
  weil ein Semester-Batch (bis 440 Abgaben) länger dauert als jeder HTTP-Timeout. DOCX-Downloads
  bleiben klein und laufen über den Proxy.
- Frontend: Seite `/briefings` (alle Tutor:innen: eigene Übungsgruppe + DOCX-Download; Master:
  zusätzlich Upload, Batch-Status, Zuordnung nicht erkannter Abgaben). `/upload` leitet dorthin um.
- **Produkt 2 — KI-Feedback an die Stammgruppen.** Wird beim Upload gleich mit erzeugt (zweiter
  LLM-Call mit eigenem, gecachtem System-Prompt; die interne Einstufung dient als Konsistenzhilfe):
  je Baustein was trägt / was bleibt dünn (mit Kriterienbezug) / nächster Schritt, Abschluss ein
  Feed-forward auf den nächsten Touchpoint und die Klausur. **Freigabe erst am Tag nach dem
  Termin** (`BRIEFING_SCHEDULE`, Leitplanke `feedback_only_after_session`): vorher liefern die
  Feedback-Endpoints 423 und die Liste keinen Feedback-Inhalt; der Master kann zur Qualitätssicherung
  mit `force=1` lesen (Log `feedback_release_forced`). Die ÜGL lädt nach dem Termin ein ZIP mit
  einem DOCX je Stammgruppe und gibt es weiter (z.B. über Canvas). Kalibrierung inkl. Feedback:
  `python scripts/calibrate_briefings.py --all --feedback`.


## License

MIT
