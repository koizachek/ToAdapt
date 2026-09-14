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
| `POST /briefings/upload` | Upload je Übungsgruppenleiter: ZIP mit Einreichungen → Briefing + Feedback je Datei (Touchpoint vom Deckblatt) |
| `GET /briefings?tp=&tutor=` | Briefings (eigene Uploads; Master alle, `tutor` filtert) |
| `GET /briefings/overview?tp=` | Je Übungsgruppe: vorhandene Stammgruppen |
| `GET /briefings/monitoring` | Master: je Konto Uploads/Downloads je Touchpoint, Prüffälle, Kontostatus |
| `GET /briefings/docx?tp=&ueg=&tutor=` | DOCX mit allen Briefings einer Übungsgruppe (Master: `tutor` Pflicht) |
| `GET /briefings/{id}/docx` | DOCX eines einzelnen Briefings |
| `GET /briefings/{id}/assessment` | Interne Kriterien-Einstufung (nur Master) |
| `PATCH /briefings/{id}` | Touchpoint/Übungsgruppe/Stammgruppe verifizieren oder nachtragen (eigene Uploads) |
| `GET /briefings/batches`, `/batches/{id}` | Status der eigenen Upload-Batches (Master: alle) |
| `POST /auth/tutor/login`, `/set-password`, `/reset-request` | Login der Übungsgruppenleiter (vom Frontend-Server aufgerufen) |
| `POST /auth/tutor/{account}/reset-code`, `GET /auth/tutor/accounts` | Master: Einmalcode erzeugen, Kontostatus |
| `GET /briefings/{id}/feedback/docx` | KI-Feedback einer Stammgruppe (DOCX) |
| `GET /briefings/feedback/zip?tp=&ueg=&tutor=` | ZIP mit einem Feedback-DOCX je Stammgruppe |

## Tech Stack

| Layer | Technologie |
|-------|-------------|
| Frontend | Next.js, Tailwind, Vercel |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| LLM | OpenRouter, Default `mistralai/mistral-large-2512` (EU; Modellvergleich 2026-09-13 in `docs/beispiele/modellvergleich/`) |
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

- Das Frontend hat zwei Modi. Studierende nutzen den bestehenden Studien-/Case-Flow (in der Pilotphase ausgeblendet). Übungsgruppenleiter melden sich auf der Startseite mit Konto (`UEGL01`–`UEGL26`) und selbst gewähltem Passwort an, der Master mit dem Master-Code in beiden Feldern; danach sehen sie `Briefings` und `Anleitung` in der oberen Navigation.
- Passwörter werden serverseitig geprüft (Backend `POST /auth/tutor/login`, nur Prüfwerte gespeichert); der Master-Code kommt aus `TEACHER_ARCHIVE_CODE` und wird nie im Frontend angezeigt.
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
nicht angezeigt. Rollen (Owner-Entscheidung 2026-09-13): **26 Übungsgruppenleiter** mit festen
Konten `UEGL01`–`UEGL26` laden jeweils eine ZIP-Datei mit den Einreichungen ihrer Gruppen hoch,
sehen nur ihre eigenen Uploads und laden Briefings und Feedbacks herunter. Der **Master**
(Login mit `TEACHER_ARCHIVE_CODE` in beiden Feldern) darf dasselbe und sieht zusätzlich das
Monitoring (wer hat wann was hoch- und heruntergeladen, Passwort-Anfragen). Schalter: Frontend
`NEXT_PUBLIC_PILOT_TUTOR_ONLY` (Standard AN; `0` schaltet die Studierenden frei), Backend
`PILOT_TUTOR_ONLY=1` (sperrt Studierenden-API und Case-Generator mit 503). Die Freischaltung der
Studierenden ist damit ein Env-Wechsel, kein Umbau.

### Login der Übungsgruppenleiter

Die Passwörter legen die Übungsgruppenleiter selbst fest: Beim ersten Login hat das Konto noch
kein Passwort, das Backend antwortet `set_password`, das Formular verlangt das neue Passwort
zweimal (mindestens 6 Zeichen). Gespeichert wird nur ein PBKDF2-Prüfwert
(`backend/db/tutor_account_store.py`, Mongo `tutor_accounts`, Datei-Fallback
`backend/db/tutor_accounts/`). Es gibt keine Env-Variable mit Tutor-Codes mehr
(`TEACHER_ACCESS_CODES` ist entfallen). Passwort vergessen: der Übungsgruppenleiter wählt sein Konto,
der Master sieht die Anfrage rot im Monitoring, erzeugt einen Einmalcode (24 h gültig) und
schickt ihn selbst per E-Mail; der Login mit dem Code löscht das alte Passwort und führt zum
Festlegen eines neuen. Routen: `POST /auth/tutor/login`, `/set-password`, `/reset-request`,
`/{account}/reset-code` (Master), `GET /auth/tutor/accounts` (Master) — alle hinter `X-API-Key`,
aufgerufen vom Frontend-Route-Handler `/teacher-login`.

## KI-Briefings für Übungsgruppenleiter (Tutor-Pipeline)

Die Stammgruppen geben ihre Touchpoint-Ergebnisse über Canvas (LMS) ab — als PPTX aus der
offiziellen Vorlage (Deckblatt-Code `TPn-UEGxx-SGy`), ersatzweise DOCX oder PDF. Jeder
Übungsgruppenleiter lädt die Dateien seiner Gruppen als ZIP hoch (`POST /briefings/upload`,
kein Touchpoint-Feld — Touchpoint, Übungsgruppe und Stammgruppe kommen vom Deckblatt); je Datei
entsteht ein Briefing nach dem KI-Paket der Kursleitung: je Baustein Kernposition (ein Satz),
tragende Argumente (max. 2), dünne Stellen als Rückfrage-Ansatz (max. 2) und eine Einschätzung
in Prosa, dazu das Feedback an die Stammgruppe und die formale Vorprüfung (Zeichengrenzen je
Folie, Code, Dateiname — gemeldet, nie bewertet). Die Niveau-Einstufung je Kriterium wird intern
gespeichert und ist nur für den Master sichtbar. Keine Punkte, keine Musterlösung, kein
Gruppenvergleich; Leitplanken werden nach dem LLM-Call regelbasiert nachgeprüft
(`backend/briefings/guardrails.py`).

- Code: `backend/briefings/` (Extraktion, Rubrics, Generator, DOCX-Renderer, Routen),
  Store `backend/db/briefing_store.py` (Mongo `briefings`, Datei-Fallback `backend/db/briefings/`),
  Download-Protokoll `backend/db/download_log.py` (Mongo `briefing_downloads`: Konto, Zeitpunkt,
  Touchpoint, Art — für das Master-Monitoring, keine Inhalte).
- Config: `backend/config/ki_rubrics/` — `ki_rubrics_tp{n}.json` (Kursleitung, 2026-08-28),
  Case-Kapitel des Running Case ON (`case/kapitel_{a..e}.md`, nur Tutor-Pipeline, nie
  studierendensichtbar), Vorlagentexte (`template_texts.json`); Konten
  `backend/config/tutor_accounts.py`.
- Sichtbarkeit: Der Teacher-Proxy schickt `X-Teacher-Id` (Konto) und `X-Teacher-Master` mit.
  Jeder sieht genau die Datensätze mit `uploaded_by == eigenes Konto`; der Master alles
  (`?tutor=UEGL05` filtert auf ein Konto, auch bei den Downloads). Keine Namensregel, keine
  Zuordnungstabelle Konto → Übungsgruppe, keine Annahme über die Anzahl Stammgruppen.
- Eingangsprüfung (`backend/briefings/intake.py`, seit 2026-09-14): Abgelehnt (Status
  `rejected`, kein Briefing, kein Download) wird nur, was keinen Text enthält oder erkennbar
  nichts mit dem Arbeitsauftrag am Running Case ON zu tun hat (Kernbegriff-Screen + kurzer
  Modellaufruf). Fehlendes Deckblatt ist bewusst KEIN Ablehnungsgrund: Der Modellaufruf
  bestimmt den Touchpoint aus dem Inhalt, die Abgabe wird ausgewertet und als "bitte
  nachtragen" markiert; `PATCH /briefings/{id}` trägt Übungsgruppe/Stammgruppe nach. Personenbezogene Angaben (E-Mail, Matrikel, Telefon, "Name:"-Zeilen) werden vor
  Speicherung und Modellaufruf entfernt; vom Deckblatt wird nur der Code gelesen. Prompt-
  Injection-Versuche (Anweisungen an die KI im Text, auch in weisser/winziger/ausserhalb
  liegender Schrift) werden erkannt, das Briefing entsteht trotzdem und trägt den Hinweis
  "Die Gruppe hat versucht, eine Prompt-Injection einzugeben"; die Browser-Ansicht zeigt einen
  roten Warnhinweis. `PATCH /briefings/{id}` korrigiert Touchpoint/Übungsgruppe/Stammgruppe
  ausgewerteter Datensätze.
- Downloads: `GET /briefings/docx?tp=` (ein DOCX je Übungsgruppe, bei mehreren ein ZIP; `ueg=`
  wählt eine aus), `GET /briefings/feedback/zip?tp=` (ein Feedback-DOCX je Stammgruppe), plus
  Einzeldokumente je Datensatz. Feedback ist sofort verfügbar (keine Terminsperre mehr).
  Jeder Download wird protokolliert (Konto, Zeitpunkt, Touchpoint, Art).
- Monitoring (nur Master): `GET /briefings/monitoring` — je Konto Uploads je Touchpoint mit
  Gruppen und Status, letzter Upload, letzter Download je Art, offene Prüffälle, Kontostatus.
- Kalibrierung (Pflicht vor Prompt-/Rubric-Änderungen): `python scripts/calibrate_briefings.py --all`
  schickt die drei Beispielabgaben je TP durch den Generator und vergleicht die Einstufung.
- **Upload-Weg (Vercel-Limit):** Vercel begrenzt Request-Bodies von Route-Handlern auf 4,5 MB
  (Infrastruktur-Limit). Der Upload geht deshalb **direkt vom Browser an Railway**:
  `POST /api/teacher/upload-token` (Frontend, jede Tutor-Session) signiert ein 15-Minuten-Token mit
  `TOADAPT_API_KEY`; der Browser schickt das ZIP mit Header `X-Upload-Token` an
  `NEXT_PUBLIC_API_URL/briefings/upload` (bis 400 MB). Voraussetzungen: `ALLOWED_ORIGINS` (Railway)
  enthält die Frontend-Domain; `TOADAPT_API_KEY` ist auf beiden Seiten identisch. Die Verarbeitung
  läuft asynchron (Antwort 202 mit `batch_id`, Fortschritt über `GET /briefings/batches/{id}`).
  DOCX-Downloads bleiben klein und laufen über den Proxy.
- Frontend: Seite `/briefings` (alle: Upload, Fortschritt, Zuordnung prüfen, Downloads, rotes
  Ausrufezeichen bei abweichenden Gruppen zwischen Touchpoints; Master: zusätzlich Monitoring
  mit Einmalcodes und Konto-Auswahl). Jede Funktion hat ein ?-Symbol; Reiter „Anleitung“ (`/guide`)
  beschreibt Login, Upload, Prüfen, Download Schritt für Schritt.

## License

MIT
