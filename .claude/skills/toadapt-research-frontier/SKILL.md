---
name: toadapt-research-frontier
description: >
  Offene Forschungsprobleme des ToAdapt-Projekts, bei denen dieses Repo einen
  Beitrag jenseits des aktuellen Stands der Technik leisten kann. Lade diese
  Skill, wenn du (a) ein Forschungsthema, Paper-Thema oder eine Studie auf
  Basis dieses Repos suchst ("was ist hier publizierbar?", "wo ist die
  Forschungslücke?", "research agenda", "CompEd-Nachfolge"), (b) eines der
  fünf Frontier-Probleme bearbeiten willst: Bloom-6/q4-Judge-Alignment,
  gruppen-bewusste Tutor-Insights, Scaffolding-Wirksamkeitsnachweis, adaptive
  Scaffolding-Intensität, Qualitäts-Autoevaluation generierter Cases, oder
  (c) wissen willst, welches Projekt-Asset (Daten, Pipeline, Logging) ein
  Forschungsvorhaben trägt und was der erste konkrete Schritt im Repo ist.
  Keywords: Forschung, Publikation, SOTA, LLM-as-Judge, Bloom 6, Alignment,
  Learning Analytics, Scaffolding-Effekt, experiment_events, Frontier.
---

# ToAdapt Research Frontier — Offene Probleme mit Hebel

## Wann diese Skill NICHT gilt

| Dein Anliegen | Passende Geschwister-Skill |
|---|---|
| Das q4-Problem AUSFÜHREN (Schritt-für-Schritt-Kampagne) | `toadapt-judge-alignment-campaign` |
| Evidenz-Standards, Hypothesen-Format, Idee-Lebenszyklus | `toadapt-research-methodology` |
| Analyse-Methoden mit durchgerechnetem Beispiel | `toadapt-proof-and-analysis-toolkit` |
| Forschungs-Skripte bedienen (import → export → compare → publish) | `toadapt-run-and-operate` |
| Didaktik-Begriffe verstehen (Bloom, TP, Canvas, Scaffolding) | `bwl-scaffolding-reference` |
| Bevor du dafür Code änderst | `toadapt-change-control` |

## Kontext in 5 Sätzen

ToAdapt ist ein Einzelnutzer-Transfer-Trainer für den BWL-A-Kurs der
Universität St.Gallen: Studierende bearbeiten individuell AI-generierte
Mini-Business-Cases, chatten mit 4 Scaffolding-Agenten (Lernbegleiter, die
Fragen stellen statt Antworten geben) und reichen Freitext-Antworten ein, die
ein LLM-Judge (ein LLM, das nach Rubric bewertet) gegen ein
Business-Model-Canvas-Schema scored. Jede Interaktion wird als Event in die
MongoDB-Collection `experiment_events` geloggt. Es existiert eine
Teacher-Alignment-Studie (Judge-Scores vs. Lehrkraft-Blind-Review, 16
Submissions, 64 Frage-Items, Stand 2026-05-31). Das Projekt schließt an eine
CompEd-Publikation zu Multi-Agent-Scaffolding an (Metacognitive-First,
Cohen's d = 0.44 — projektinterne Angabe aus der Vorgänger-Studie,
hier nicht unabhängig verifiziert). Alle SOTA-Aussagen unten sind
Arbeitsannahmen, Stand 2026-07-08, ohne systematisches Literatur-Review —
vor einer Einreichung Related Work sauber recherchieren.

Harte Grenzen für ALLE Vorhaben (Details: `toadapt-change-control`):
keine Framework-Namen in studierendensichtbarem Text, keine Musterlösungen,
keine Bezüge auf "ON Running"/"NORDIC HOME" (kurs-reservierte Cases), keine
echten Teilnehmerdaten im Repo (liegen in `~/ToAdapt_sensitive_data/`),
Judge-/Prompt-Änderungen nie ohne Alignment-Recheck.

---

## Problem 1 — Automatisierte Bewertung von Bloom-6-/Integrationsleistung

**Warum aktuelles SOTA versagt:** LLM-Judges erreichen auf Fakten- und
Struktur-Fragen brauchbare Korrelation mit menschlichen Ratern, brechen aber
bei Synthese-/Integrationsleistung ein (Bloom 6 = eigene Urteile bilden,
Teilentscheidungen zu einem konsistenten Ganzen integrieren). Das ist keine
Literatur-Behauptung, sondern eigener Befund dieses Projekts
(`docs/teacher_alignment_report_20260531_17submissions.md`, Stand 2026-05-31,
16 Submissions):

| Frage | Bloom-Fokus | MAE nach Kalibrierung | Pearson r nach |
|---|---|---:|---:|
| q1–q3 | 2–5 (Analyse, Entscheidung, Umsetzung) | 1.19–2.50 | 0.745–0.918 |
| **q4** | **6 (Integration, 30 Punkte)** | **4.97** | 0.79 |

q4 wird zudem SYSTEMATISCH unterbewertet (Mean Diff −4.97; insgesamt liegt
der kalibrierte Judge in 48 von 64 Items unter der Lehrkraft). Ob und wie
dieses Muster in publizierter Judge-Literatur repliziert ist: UNVERIFIZIERT
(Stand 2026-07-08) — Related-Work-Recherche nötig.

**Das spezifische Asset dieses Projekts:**
- Eine getestete Blind-Review-Pipeline: `scripts/export_review_workbooks.py`
  erzeugt `_rubric`/`_blind`/`_chat_turns`-Excel-Workbooks; die Lehrkraft
  bewertet blind (ohne Judge-Scores); `scripts/compare_teacher_rubric_scores.py`
  rechnet Pearson/MAE/RMSE/within-2pt, Join über
  `review_item_id = "{case_id}:{question_id}:{nnn}"`.
- Lehrer-Ground-Truth existiert bereits (64 Items; Rohdaten in
  `~/ToAdapt_sensitive_data/`, NIEMALS ins Repo kopieren).
- Hartkodierte Kalibrierungsanker pro Frage im Judge
  (`_format_calibration_notes`, `backend/evaluator/rubric_evaluator.py`,
  Zeile ~155) — Ergebnis der ersten Kalibrierungsrunde, direkt iterierbar.
- Konservativer Judge mit Unsicherheits-Signalen (`judge_confidence`,
  `needs_human_review`, `score_band`) — Ansatzpunkt für "Judge unterstützt
  statt ersetzt".

**Erste 3 Schritte in diesem Repo:**
1. Lies den Befund: `sed -n '33,41p' docs/teacher_alignment_report_20260531_17submissions.md`
   (Tabelle "Nach Frage").
2. Lies die q4-Anker: `grep -n -A 8 '"q4": \[' backend/evaluator/rubric_evaluator.py`
   — prüfe, ob die Anker Integration belohnen oder (Hypothese) übermäßig
   bestrafen ("reicht nicht"-Formulierungen).
3. Lade `toadapt-judge-alignment-campaign` — dort liegt die executable
   Kampagne (Hypothesen, Re-Run-Protokoll, Akzeptanzkriterien). Diese
   Frontier-Skill beschreibt nur das Forschungsproblem.

**Du hast ein Ergebnis, wenn:** auf einem FRISCHEN Blind-Review-Batch
(≥ 16 vollständige Submissions, Lehrkraft ohne Sicht auf Judge-Scores) die
Erfolgskriterien erfüllt sind. **Maßgeblich ist das operative Deploy-Gate
in `toadapt-judge-alignment-campaign` §6** (q4-MAE < 3.0, Gesamt-Pearson
r ≥ 0.78, q1–q3-MAE-Verschlechterung jeweils < 0.3). Darüber hinaus gilt
als ehrgeizigere **Publikations-Bar** (nur für den Paper-Claim
"Bloom-6-Alignment gelöst", nicht als Deploy-Kriterium): q4-MAE ≤ 2.5 UND
|q4 Mean Diff| ≤ 2.0. Falsifiziert, wenn q4-MAE trotz Anker-Redesign
über ~4 bleibt — dann ist der Befund "LLM-Judges können Bloom 6 (noch) nicht"
selbst der publizierbare Beitrag, inklusive Methodik.

---

## Problem 2 — Gruppen-bewusste Tutor-Insights

**Warum aktuelles SOTA versagt:** Learning-Analytics-Dashboards aggregieren
typischerweise pro Individuum oder pro Gesamtkohorte (Arbeitsannahme, Stand
2026-07-08, UNVERIFIZIERT als Literaturaussage). Das Assessment-Modell dieses
Kurses ist aber dreistufig: Individuum übt im Tool → GRUPPE (6er-Team) gibt
ab → Tutor:in beurteilt die Gruppe in der Präsenzphase. Die Ownerin hat am
2026-07-08 geklärt: Gruppen sind die Assessment-Einheit, die Tool-Arbeit ist
individuelle Vorbereitung. Ein Dashboard, das Tutor:innen VOR der
Präsenzphase sagt "in Gruppe 12 haben 4 von 6 Mitgliedern das Lernziel X
verfehlt", existiert weder hier noch (nach Kenntnisstand) als etabliertes
Muster.

**Das spezifische Asset dieses Projekts:**
- Die Aggregation pro PERSON existiert bereits vollständig:
  `GET /dashboard/difficulties` (`backend/dashboard/routes.py`, Zeile ~341)
  liefert pro Studierendem `attention_level` (high/medium/low), schwache
  Lernziele (Schwelle `WEAK_THRESHOLD_PCT = 60.0`), fehlende Canvas-Blöcke
  und wiederkehrende Schwächen (`main_penalties`-Phrasen), plus
  Kohorten-Sicht (`cohort_weak_objectives`, `cohort_common_penalties`).
- Die fehlende Zutat ist EIN Feld: Im gesamten Code existiert kein
  Gruppenkonzept — `backend/models/user.py` kennt nur `matrikelnummer`
  (verifiziere: `grep -rn group backend/models/` → leer). Das ist die größte
  bekannte konzeptionelle Lücke des Projekts.

**Erste 3 Schritte in diesem Repo:**
1. Datenmodell: Füge `group_id: str | None = None` in `User`
   (`backend/models/user.py`) und denormalisiert in `SubmissionState`
   (`backend/models/submission.py`, analog zu `matrikelnummer`, Zeile ~43)
   hinzu. Vorher `toadapt-change-control` laden (Datenmodell-Änderung).
2. Aggregation: Erweitere `backend/dashboard/routes.py` — das Muster
   `by_student: dict[str, list] = defaultdict(list)` (Zeile ~352) wird
   dupliziert zu `by_group`; ein neuer Endpoint `/dashboard/groups` liefert
   pro Gruppe die schwächsten Lernziele + wie viele Mitglieder betroffen
   sind. Tests analog `tests/test_dashboard_difficulties.py`.
3. Pilot: Erzeuge synthetische Gruppen (6er-Zuordnung über bestehende
   Testdaten), zeige das Gruppen-Dashboard 2–3 Tutor:innen und protokolliere
   strukturiert, welche Anzeige eine konkrete Vorbereitungshandlung auslöst.
   KEINE echten Teilnehmerdaten dafür verwenden.

**Du hast ein Ergebnis, wenn:** Tutor:innen im Pilot (n ≥ 3) vor einer
simulierten Präsenzphase pro Gruppe mindestens ein spezifisches, korrektes
Defizit benennen können, das sie OHNE Dashboard nicht benannt hätten — und
das Dashboard-Signal mit der tatsächlichen (synthetischen) Score-Verteilung
der Gruppe übereinstimmt. Falsifiziert, wenn Tutor:innen die Gruppen-Sicht
gegenüber der Personen-Liste als redundant bewerten.

---

## Problem 3 — Scaffolding-Wirksamkeitsnachweis (CompEd-Nachfolge)

**Warum aktuelles SOTA versagt:** Wirksamkeitsstudien zu LLM-Tutoren messen
häufig Zufriedenheit oder Task-Completion statt bewerteter Lernleistung, und
selten mit Turn-Level-Prozessdaten UND unabhängiger Leistungsmessung im
selben System (Arbeitsannahme, Stand 2026-07-08, UNVERIFIZIERT). Die
Vorgänger-Studie des Projekts (CompEd-Publikation, Hao et al. 2026, laut
Projektdoku) fand für das Metacognitive-First-Prinzip Cohen's d = 0.44 —
in einem Concept-Mapping-Setting, nicht im Business-Case-Transfer. Ob der
Effekt hier repliziert, ist offen.

**Das spezifische Asset dieses Projekts:** Comprehensive Event-Logging ist
bereits produktiv (`backend/db/experiment_logger.py`, Collection
`experiment_events`; Call-Sites in `backend/api/routes.py`):

| Event | Enthält u.a. |
|---|---|
| `session_created` | Session-Dump inkl. `ExperimentContext` |
| `chat_turn_completed` | `user_message`, `assistant_message`, `agent_type`, `message_count` |
| `submission_answer_saved` | Frage-ID, Antworttext |
| `submission_submitted` / `submission_evaluated` | vollständige Scores, Canvas-Alignment, Judge-Metadaten |

Entscheidend: `ExperimentContext` (`backend/models/experiment.py`) hat
bereits ein `condition`-Feld — A/B-Bedingungen sind ohne Backend-Änderung
zuweisbar. `scripts/export_review_workbooks.py` exportiert Chat-Turns als
Excel (`*_chat_turns.xlsx`).

**Erste 3 Schritte in diesem Repo:**
1. Prüfe die Logging-Kette end-to-end mit einem synthetischen Durchlauf:
   `grep -n "_log_experiment_event(" backend/api/routes.py` (8 Treffer =
   1 Definition + 7 Call-Sites) und verifiziere, dass `condition` im
   Event-Payload ankommt.
2. Definiere die Manipulation: Metacognitive-First an/aus ist EIN Flag —
   `session.metacognitive_phase_complete` (`backend/agents/orchestrator.py`,
   Zeile ~270/420). Eine Condition-abhängige Initialisierung in
   `POST /sessions` (`backend/api/routes.py`) genügt als minimaler Eingriff.
   Change-Control beachten (studierendensichtbares Verhalten).
3. Präregistriere die Analyse nach `toadapt-research-methodology`
   (Hypothese sagt Zahlen voraus), Outcome = `percentage` /
   `rubric_fit_pct` aus `submission_evaluated`, Prozessvariablen =
   Turn-Anzahl und Agent-Mix aus `chat_turn_completed`.

**Du hast ein Ergebnis, wenn:** eine präregistrierte Zwei-Gruppen-Analyse
(Power-Rechnung mit d = 0.44 als Prior → benötigte n VOR Start festlegen)
einen Score-Unterschied mit Konfidenzintervall liefert, das 0 ausschließt —
ODER ein sauberer Null-Befund mit ausreichender Power. Beides ist ein
Ergebnis; "kein signifikanter Trend bei n = 15" ist keines.

---

## Problem 4 — Adaptive Scaffolding-Intensität statt Keyword-Routing

**Warum aktuelles SOTA versagt:** Adaptive Tutoring-Systeme adaptieren
klassisch über Knowledge Tracing auf strukturierten Aufgaben; für offene
Freitext-Chat-Interaktion gibt es kein etabliertes, validiertes
Readiness-Maß (Arbeitsannahme, Stand 2026-07-08, UNVERIFIZIERT). Dieses
Projekt ist selbst Negativ-Beispiel: Das Agent-Routing ist eine
Keyword-Liste (`_select_agent`, `backend/agents/orchestrator.py`,
Zeile ~265: "entscheidung"→STRATEGIC, "konzept"→CONCEPTUAL, …, Fallback
STRATEGIC), und die metakognitive Phase (Reflexion vor Inhalt) gilt nach
GENAU EINER Agenten-Antwort als abgeschlossen (Zeile ~420:
`message_count >= 1`). Eine `scaffolding_intensity` existiert im Code
nirgends (das Konzept in CLAUDE.md ist ein Fossil der verworfenen
Gruppen-Architektur).

**Das spezifische Asset dieses Projekts:** Turn-Level-Daten mit
Outcome-Verknüpfung: Jeder `chat_turn_completed`-Event enthält
`user_message`, `assistant_message`, `agent_type`, `message_count` und ist
über `session_id`/`user_id`/`case_id` mit `submission_evaluated`
(Punkte pro Frage, Canvas-Blöcke, Schwächen) verknüpfbar. Damit lassen sich
Readiness-Kandidaten OFFLINE evaluieren, bevor irgendetwas im
Live-Verhalten geändert wird.
Ehrliche Lücke: `guardrail_triggered` ist nur ein structlog-Warning
(`backend/agents/orchestrator.py`, Zeile ~416), KEIN experiment_event —
Guardrail-Auslösungen sind in den Forschungsdaten derzeit nicht pro Turn
auswertbar (nur der ersetzte Fallback-Text im Event verrät sie indirekt).

**Erste 3 Schritte in diesem Repo:**
1. Baseline messen: Extrahiere aus vorhandenen (synthetischen oder
   einwilligungsgedeckten) `experiment_events` alle Turn-Sequenzen und
   labelle manuell für ~50 Turns, welcher Agent SOLLTE geantwortet haben.
   Routing-Accuracy der Keyword-Heuristik = Baseline-Zahl.
2. Kandidaten-Maß definieren (z.B. LLM-Klassifikator über die letzten k
   Turns: "reflektiert die Person bereits über ihr Vorgehen?") und offline
   gegen dieselben Labels testen — kein Live-Eingriff nötig.
3. Erst bei Offline-Überlegenheit: Ersetze die `message_count >= 1`-Heuristik
   hinter einem Env-Flag (Muster: `toadapt-config-and-flags`, "Neue
   Config-Achse hinzufügen") und evaluiere als A/B über
   `ExperimentContext.condition` (siehe Problem 3).

**Du hast ein Ergebnis, wenn:** das gelernte/definierte Readiness-Maß auf
gehaltenen Daten die Routing-/Phasenwechsel-Entscheidung messbar besser
trifft als die Keyword- bzw. `>= 1`-Heuristik (vorab festgelegte Schwelle,
z.B. +15 Prozentpunkte Accuracy gegen menschliche Labels) — und in der
A/B-Phase die Outcome-Scores nicht verschlechtert. Falsifiziert, wenn die
naive Heuristik gleichauf liegt: auch das ist publizierbar ("cheap
heuristics suffice").

---

## Problem 5 — Qualitäts-Autoevaluation AI-generierter Cases

**Warum aktuelles SOTA versagt:** Generierte Lernmaterialien werden meist
nur regelbasiert oder gar nicht qualitätsgesichert; validierte Prädiktoren
für "würde eine Lehrkraft diesen Case freigeben?" sind nicht etabliert
(Arbeitsannahme, Stand 2026-07-08, UNVERIFIZIERT). Der projekteigene
Validator (`validate_case`, `backend/cases/validator.py`, Zeile ~49) prüft
ausschließlich REGELN: verbotene Framework-Namen, reservierte
Kurs-Case-Begriffe, leere Pflichtfelder, Section-/Exhibit-Anzahl,
Bloom-Abdeckung, Punktesumme. Er prüft NICHT Güte: Plausibilität der
Zahlen in Exhibits, innere Konsistenz, Schwierigkeitsgrad, didaktische
Ergiebigkeit der Spannungsfelder.

**Das spezifische Asset dieses Projekts:** Der Case-Lebenszyklus erzeugt
Lehrpersonen-Labels als Nebenprodukt: Das `Case`-Modell
(`backend/models/case.py`) persistiert `status`
(draft/approved/rejected/retired), `reviewed_by`, `review_notes`,
`revision` und `edit_history` (Liste von `CaseEditEvent` mit
action = "edited" | "regenerated" | "approved" | …); der Admin-Flow
(`backend/admin/routes.py`) schreibt bei jedem PATCH/Regenerate/Approve/
Reject hinein, inkl. protokolliertem `force`-Override beim Approve trotz
Validierungsfehlern. Approve/Reject/Edit-Historie = kostenlose
Qualitäts-Labels.
Ehrliche Einschränkung (Stand 2026-07-08): Der Pool enthält erst 2 Cases
(DE+EN-Variante desselben Cases, beide approved, `edit_history` leer) —
die Label-Basis muss erst wachsen, bevor hier irgendetwas validierbar ist.

**Erste 3 Schritte in diesem Repo:**
1. Label-Inventur (jederzeit wiederholbar):
   ```bash
   python3 -c "
   import json, pathlib
   for p in sorted(pathlib.Path('backend/cases/pool').glob('*.json')):
       if p.name.endswith('-agent.json'): continue
       c = json.loads(p.read_text())
       print(c['case_id'], c['status'], 'edits:', [e['action'] for e in c.get('edit_history', [])])
   "
   ```
2. Definiere 4–6 Güte-Dimensionen, die der Regel-Validator NICHT abdeckt
   (Zahlen-Plausibilität in Exhibits, Konsistenz Sections↔Exhibits↔Fragen,
   Ergiebigkeit der `key_tensions` aus `{case_id}-agent.json`), als
   Rubrik-Dokument — abgeleitet aus dem, was Lehrpersonen in
   `review_notes`/`edit_history` tatsächlich bemängeln, sobald Daten da sind.
3. Baue einen Offline-LLM-Judge für Case-Güte (analog
   `backend/evaluator/rubric_evaluator.py` als Vorlage für JSON-Robustheit)
   und evaluiere ihn AUSSCHLIESSLICH retrospektiv gegen die
   Approve/Reject/Edit-Historie — nicht als Gate in den Admin-Flow einbauen,
   bevor er validiert ist (Change-Control).

**Du hast ein Ergebnis, wenn:** bei ≥ 30 gelabelten Cases (approved vs.
rejected/stark editiert) der Güte-Judge die Lehrpersonen-Entscheidung auf
gehaltenen Cases besser als Zufall UND besser als der Regel-Validator
allein vorhersagt (vorab festgelegte Metrik, z.B. balanced accuracy ≥ 0.75).
Meilenstein davor: die Label-Basis existiert überhaupt (≥ 30 Cases mit
dokumentierter Review-Entscheidung). Falsifiziert, wenn Lehrpersonen-Urteile
untereinander nicht konsistent genug sind (Inter-Rater-Check zuerst!).

---

## Priorisierung (Empfehlung, Stand 2026-07-08)

| # | Problem | Reifegrad | Blocker |
|---|---|---|---|
| 1 | q4/Bloom-6-Judge | Daten + Pipeline vorhanden, Befund dokumentiert | Lehrkraft-Zeit für neuen Blind-Batch |
| 3 | Scaffolding-Wirksamkeit | Logging + `condition`-Feld produktiv | Teilnehmer-Rekrutierung, Ethik/Einwilligung |
| 2 | Gruppen-Insights | Personen-Aggregation fertig | `group_id` fehlt im Datenmodell; Entscheidung A/B im ROLLOUT_PLAN offen |
| 4 | Adaptive Intensität | Turn-Daten vorhanden | Manuelle Labels nötig; guardrail-Events fehlen in Forschungsdaten |
| 5 | Case-Güte-Judge | Label-Mechanik existiert | Nur 2 Cases im Pool — Label-Basis fehlt |

---

## Provenance und Wartung

Erstellt: 2026-07-08 auf Basis direkter Repo-Verifikation. Drift-anfällige
Fakten und ihr Re-Verifikations-Kommando (vom Repo-Root ausführen):

| Fakt | Re-Verifikation |
|---|---|
| q4-MAE ~4.97 / q1–q3-Werte (Report vom 2026-05-31) | `sed -n '33,41p' docs/teacher_alignment_report_20260531_17submissions.md` |
| Kalibrierungsanker hartkodiert in q1–q4 | `grep -n '_format_calibration_notes' backend/evaluator/rubric_evaluator.py` |
| Kein Gruppenkonzept im Datenmodell | `grep -rn group backend/models/` (leer = Fakt gilt noch) |
| `/dashboard/difficulties` + Schwelle 60.0 | `grep -n 'WEAK_THRESHOLD_PCT\|/difficulties' backend/dashboard/routes.py` |
| 7 Event-Call-Sites im Studenten-Flow | `grep -c '_log_experiment_event(' backend/api/routes.py` (8 = 1 Definition + 7 Calls) |
| `condition`-Feld im ExperimentContext | `grep -n condition backend/models/experiment.py` |
| Keyword-Routing + `message_count >= 1`-Heuristik | `grep -n '_select_agent\|message_count >= 1' backend/agents/orchestrator.py` |
| `guardrail_triggered` nur Log, kein Event | `grep -n guardrail_triggered backend/agents/orchestrator.py backend/api/routes.py` |
| Validator prüft nur Regeln | `grep -n 'code=' backend/cases/validator.py` |
| Case-Pool-Größe / Label-Basis | `ls backend/cases/pool/ \| grep -v -- '-agent.json' \| wc -l` |
| Rollout-Entscheidung A/B noch offen | `grep -n 'Weg B\|Entscheidung' ROLLOUT_PLAN.md` |
