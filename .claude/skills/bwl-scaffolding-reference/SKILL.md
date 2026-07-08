---
name: bwl-scaffolding-reference
description: >
  Domänen-Referenz für ToAdapt (BWL-A-Transfer-Trainer, Universität St.Gallen).
  Lade diese Skill, wenn du BWL-didaktische Begriffe im Code verstehen musst:
  Bloom-Taxonomie / bloom_level / Lernziel-Tags, Touchpoints (TP1–TP4),
  TP_CONFIGS, Constructive Alignment, Scaffolding vs. Answer-Giving, die vier
  Agenten (metacognitive/strategic/conceptual/procedural), Guardrails und
  Guardrail-Fallbacks, pfadoffene Rubrics, Business Model Canvas / 
  canvas_alignment / rubric_fit / Exemplar, das Assessment-Modell
  (Individuum im Tool, Gruppe beim Tutor), warum "ON Running" und
  "NORDIC HOME" verboten sind, oder Projektjargon wie ÜGL, Matrikelnummer,
  technical_fallback. Typische Symptome: "Was bedeutet dieses Feld im
  Rubric-JSON?", "Warum darf der Agent keinen Framework-Namen sagen?",
  "Wie wird canvas_alignment_pct berechnet?", "Was ist q4/Bloom 6?".
---

# BWL-Scaffolding-Referenz für ToAdapt

Diese Skill erklärt das Domänenwissen, das ein Engineer ohne BWL-Didaktik-
Hintergrund braucht, um den Code in `backend/` und `frontend/` korrekt zu
lesen und zu ändern — SO WIE ES IN DIESEM REPO ANGEWANDT WIRD, kein Lehrbuch.
Alle Pfade sind repo-relativ zu `/Users/dianakozachek/ToAdapt` bzw. dem
Repo-Root.

## Wann diese Skill NICHT gilt

- Du willst eine Änderung klassifizieren oder freigeben (was ist erlaubt,
  was gated) → **toadapt-change-control**
- Du debuggst ein konkretes Fehlverhalten → **toadapt-debugging-playbook**
- Du willst die Judge-q4-Schwäche BEARBEITEN (nicht nur verstehen) →
  **toadapt-judge-alignment-campaign**
- Du brauchst Env-Variablen oder Magic Numbers als Katalog →
  **toadapt-config-and-flags**
- Du willst das System starten/deployen → **toadapt-run-and-operate** /
  **toadapt-build-and-env**
- Du willst Architektur-Entscheidungen und Invarianten →
  **toadapt-architecture-contract**

WARNUNG vorab: `CLAUDE.md` im Repo-Root beschreibt eine VERWORFENE
Gruppen-Echtzeit-Architektur (Fossil, Stand vor 2026-04-30). Diese Skill
beschreibt den REALEN Code. Bei Widerspruch gewinnt der Code.

---

## 1. Bloom-Taxonomie — wie sie HIER kodiert ist

Bloom-Taxonomie = Klassifikation kognitiver Lernziele in Stufen (2 =
Verstehen … 6 = Erschaffen/Synthese). Im Code ist die Stufe ein `int`-Feld
`bloom_level` (2–6) auf jeder Case-Frage (`CaseQuestion` in
`backend/models/case.py`).

Der Rubric-Evaluator übersetzt die Stufe in Lernziel-Tags
(`_make_tags` in `backend/evaluator/rubric_evaluator.py`, Zeilen 127–135).
Diese Tags landen im Judge-Prompt und (vom Judge zurückgegeben) in
`QuestionScore.learning_objective_tags`, worauf das Teacher-Dashboard
aggregiert:

| bloom_level | Tags (exakt so im Code)                        | Bedeutung (Kurzform) |
|-------------|------------------------------------------------|----------------------|
| 2           | `verstehen`, `identifizieren`                  | Sachverhalt erkennen |
| 3           | `anwenden`, `transfer`                         | Wissen auf neuen Fall übertragen |
| 4           | `analysieren`, `wirkungskette`, `stakeholder`  | Ursache-Wirkung zerlegen |
| 5           | `evaluieren`, `trade-off`, `kpi`               | Optionen bewerten, Zielkonflikte |
| 6           | `synthese`, `integration`, `reflexion`         | Teile zu Gesamtbild integrieren |
| sonst       | `analyse` (Fallback)                           | — |

Welche TP-Phase welche Stufen trainiert, steht in
`backend/config/tp_configs.py` (`TP_CONFIGS[n]["bloom_levels"]`):
TP1 → [2, 3, 4], TP2 → [4, 5], TP3 → [3, 4, 5], TP4 → [5, 6].
Der Case-Validator (`backend/cases/validator.py`) warnt (warning, kein
error), wenn ein Case nicht alle erwarteten Bloom-Stufen seiner Ziel-TP
abdeckt.

Praktisch wichtig: **q4 = Bloom 6 = Integration** ist die Frage, bei der
der LLM-Judge am schlechtesten mit Lehrer-Scores übereinstimmt (MAE ~5 von
30 Punkten, systematische Unterbewertung; Details und Bearbeitung →
toadapt-judge-alignment-campaign).

## 2. Constructive Alignment und die 4 Touchpoints

Constructive Alignment (Biggs, 2003) = Lernziele, Lernaktivitäten und
Prüfung sind auf DIESELBEN Kompetenzen ausgerichtet: Was am Touchpoint
trainiert wird, wird in der Klausur geprüft — nichts anderes. Für den Code
heißt das: Jede TP-Phase hat feste Bloom-Stufen, erlaubte Denkwerkzeuge und
ein festes Abgabeformat; das Tool darf diese Kopplung nicht aufweichen
(z. B. keine Bloom-6-Hilfe in TP1).

Quelle der Wahrheit ist `backend/config/tp_configs.py` (`TP_CONFIGS`),
NICHT die CLAUDE.md-Kopie. Stand 2026-07-08:

| TP | Name | Kurs-Format (Gruppenabgabe) | Bloom | Case-Kapitel | individual_component |
|----|------|------------------------------|-------|--------------|----------------------|
| 1 | Analyse & Stakeholder | 3 Slides (PDF) | 2–4 | A | "Was würden Sie an Ihrer eigenen Analyse konkret verändern – und warum?" — 6 Pkt, 5 Min |
| 2 | Strategische Entscheidung | Management-Memo (1 Seite, PDF) | 4–5 | A, B | "Welche Entscheidung würden Sie anders treffen?" — 8 Pkt, 5 Min |
| 3 | Strategie in den Markt übersetzen | Decision Log (max. 2 Seiten A4, PDF) | 3–5 | A, B, C | "Wo weicht die Umsetzung am stärksten von der Strategie ab?" — 8 Pkt, 5 Min |
| 4 | Integration & Gesamtbild | Strategy-on-a-Page (1 Seite) | 5–6 | A–D | "Riskanteste Entscheidung + Revisionskonsequenz (Kaskadeneffekt)" — 10 Pkt, 10 Min |

Einordnung: `format` und `case_chapters` beschreiben den PRÄSENZKURS
(Gruppenabgaben zum Kurs-Case), nicht das Tool. Im Tool beantworten
Studierende Freitext-Fragen zu AI-generierten Mini-Cases; Wortlimits setzt
das Frontend nach Frage-INDEX (`frontend/app/cases/[id]/page.tsx`,
Zeilen 311–313: Index 0–1 → 50–200 Wörter, Index 2–3 → 100–200, danach
150–200). `individual_component` ist der geplante Einzelanteil in der
Präsenzphase.

TP-Kalender (`TP_SCHEDULE`, ebd.): TP1 2026-09-14…10-05, TP2 10-06…10-26,
TP3 10-27…11-16, TP4 11-17…12-07. `current_tp_phase()` existiert, wird aber
Stand 2026-07-08 NICHT benutzt — das Frontend sendet `target_tp: 1`
hartkodiert (`frontend/app/cases/[id]/page.tsx`, Zeile 717). Bekannte Lücke.

Weitere TP-Config-Felder: `allowed_frameworks` (Denkwerkzeuge, die die
Agenten IMPLIZIT hervorrufen dürfen), `forbidden_framework_names` (Namen,
die studierendensichtbar NIE fallen dürfen — s. §3), `key_questions`
(Leitfragen), `rubric_reference` (Dateiname der Rubric, s. §4).
ACHTUNG: `TP_CONFIGS[4]` hat KEINEN Key `forbidden_framework_names` —
in TP4 greifen nur die globalen `FORBIDDEN_PATTERNS` des Guardrails
(vermutlich unbeabsichtigte Lücke, nicht als Feature behandeln).

## 3. Scaffolding vs. Answer-Giving — die 4 Agenten

Scaffolding = Lernende durch Fragen und Denkimpulse zur EIGENEN Lösung
führen, statt die Lösung zu geben (Answer-Giving). Das ist das
Kernversprechen des Systems und didaktisch unverhandelbar: Sobald das Tool
Antworten liefert, trainiert es die geprüfte Kompetenz nicht mehr.

Alle vier Agenten leben in EINEM File: `backend/agents/orchestrator.py`
(System-Prompts `AGENT_PROMPTS` DE / `AGENT_PROMPTS_EN` EN). Kein Markdown,
keine Listen, keine Emojis, 2–4 Sätze (CONCEPTUAL: <90 Wörter, zweiteilig).

| Agent | Rolle | Tut | Tut NIE |
|-------|-------|-----|---------|
| METACOGNITIVE | Reflexion über den eigenen Denkprozess | max. 1 Gegenfrage, die tiefer führt | direkte Antworten, Musterlösungen, Framework-Namen, kopierbare Formulierungen |
| STRATEGIC | Entscheidungslogik | Optionen strukturieren, Trade-offs und Konsequenzen sichtbar machen; Kriterien und Spannungen NENNEN | für den Studierenden entscheiden, konkrete Use-Case-Auswahl, "erste Herausforderung könnte sein…", erfundene Case-Details (Regulatoren, Anbieter, Hosting, Verträge) |
| CONCEPTUAL | Begriffe implizit zugänglich machen | Begriff in 1–2 Sätzen erklären + 1 Satz Rolle im aktuellen Case | Framework-Namen nennen, nicht belegte Fall-Details ergänzen |
| PROCEDURAL | Format & Struktur der Antwort | Gliederungs- und Prägnanz-Hinweise, Klarheitsfragen | inhaltliche Antworten, ausformulierte Musterantworten |

Routing (`_select_agent`, keyword-basiert — naiv, bekannte Schwachstelle):
1. Begriffs-Anfrage ("erklär", "was bedeutet", "explain", "term" …) →
   CONCEPTUAL, überschreibt alles.
2. Solange `session.metacognitive_phase_complete == False` → METACOGNITIVE
   (**Metacognitive-First**: jede Session beginnt mit Reflexion; empirische
   Basis laut Projekt: Cohen's d = 0.44, CompEd-Paper Hao et al. 2026 —
   Projektbehauptung, im Repo nicht reproduzierbar).
3. Strategie-Keywords (entscheidung, strategie, warum, trade-off …) →
   STRATEGIC; 4. konzept/modell/theorie → CONCEPTUAL; 5. format/struktur/
   folie/memo → PROCEDURAL; 6. Fallback STRATEGIC.

Realität vs. Vision: Die metakognitive Phase gilt bereits nach EINER
metakognitiven Antwort als abgeschlossen (`session.message_count >= 1`;
der Zähler wird in `backend/api/routes.py` VOR dem Agent-Call inkrementiert,
d. h. die erste Antwort beendet die Phase). Keine echte Readiness-Messung.

Weitere Mechanik: `max_tokens` 220 (CONCEPTUAL) / 320 (Rest). Chat-History
hält der CLIENT (letzte 10 Einträge pro Request); der Server speichert
keinen Verlauf. Case-Kontext im System-Prompt = Titel + Tagline + erste
2 Sections à max. 400 Zeichen. Optional fließt `{case_id}-agent.json` aus
`backend/cases/pool/` ein — aber NUR `key_tensions` und `common_mistakes`;
`scaffolding_questions`/`learning_objectives` darin sind ungenutzt.
Sprache EN, wenn `experiment.metadata.language == "en"` oder die case_id
auf `-en` endet.

**Guardrails ERSETZEN, sie editieren nicht:** `guardrail_check(text, tp)`
prüft nacheinander (a) TP-spezifische `forbidden_framework_names`,
(b) globale `FORBIDDEN_PATTERNS` (Antwort-Phrasen wie "die lösung lautet"
+ harte Namen: porter, five forces, rbv, vrio, 4p, tce, preiselastizität …),
(c) `SLANG_PATTERNS`, (d) Emojis (Unicode-Kategorie So),
(e) `RECOMMENDATION_PATTERNS` + 7 Regexe (direkte Empfehlungen),
(f) `CASE_SPECULATION_PATTERNS` (erfundene Details: finma, microsoft …).
Bei EINEM Treffer wird die komplette LLM-Antwort durch einen festen,
agent-spezifischen Fallback-Text ersetzt (`_guardrail_fallback`, DE/EN)
und `guardrail_triggered` als warning geloggt. Begründung des Designs:
Eine "reparierte" Antwort könnte die verbotene Information paraphrasiert
weitertragen; kompletter Ersatz ist der einzig sichere Pfad. Deshalb: Wer
Guardrail-Patterns verschärft, erhöht die Fallback-Quote und verschlechtert
die UX — messen, nicht raten (→ toadapt-diagnostics-and-tooling).

**Warum keine Framework-Namen?** Anti-Framework-Dropping: Die Klausur prüft,
ob Studierende die LOGIK eines Modells (z. B. Make-or-Buy-Faktoren:
Spezifität, Häufigkeit, Unsicherheit) selbst auf einen Fall anwenden.
Nennt das Tool den Modellnamen, lernen sie Label statt Logik — und der
Klausur-Vorteil gegenüber Nicht-Nutzern wäre unfair. Gilt für ALLES
Studierendensichtbare: Agent-Antworten, Case-Texte, Evaluator-Feedback.

## 4. Pfadoffene Rubrics — was die JSONs WIRKLICH enthalten

Pfadoffen = es gibt KEINE Musterlösung; jede schlüssig begründete
Entscheidung kann volle Punkte erreichen. Bewertet wird die Qualität des
Denkens (Case-Bezug, Ursache-Wirkung, Konsequenzen), nicht eine erwartete
Ziel-Antwort. Deshalb existiert im Repo nirgends eine "richtige Antwort"
pro Frage — such nicht danach.

Verkettung der Bewertung (LLM-as-Judge, ein Call pro Frage,
`backend/evaluator/rubric_evaluator.py`):

```
CaseQuestion (im Case-JSON):  bloom_level, max_points, rubric_reference
        │  z. B. "tp1_rubric.json"
        ▼
backend/config/rubrics/tp{1-4}_rubric.json
        │  payload["questions"][question_id]  (Fallback: payload["default"])
        ▼
QuestionRubric (backend/evaluator/rubric_loader.py)
```

Die Rubric-JSONs enthalten pro Frage NUR:
- `evaluation_focus`: 3 Prosa-Kriterien, worauf der Judge achtet
- `required_canvas_blocks`: Pflicht-Canvas-Bausteine (s. §5) mit `block`,
  `label`, `accepted_keywords` (nur Signale!), `expectation`, `weight`
- `exemplar_threshold_pct` und `score_floor_pct` — reale Per-Rubric-Werte
  (verifiziert 2026-07-08): tp1 80.0/75.0, tp2 82.0/75.0, tp3 80.0/72.0,
  tp4 82.0/75.0. 80.0/75.0 sind nur die DEFAULTS aus
  `backend/evaluator/rubric_loader.py` (greifen, wenn eine Rubric die
  Felder weglässt)

**Bloom-Stufe und Punktzahl leben in der Case-Frage, NICHT in der Rubric.**
Stand 2026-07-08 hat jede tpN-Rubric genau einen Eintrag (tp1→q1 … tp4→q4).

Der Judge (`EVALUATOR_SYSTEM` + `EVALUATE_PROMPT`) arbeitet konservativ:
Punktleitplanken sind abgeleitet (`mid = max_points × 0.55`,
`low = × 0.25`), fehlende Pflichtbestandteile deckeln das obere Band,
Unsicherheit → `needs_human_review = true` (bei
`judge_confidence == "low"` erzwungen). Zusätzlich sind pro question_id
q1–q4 **Kalibrierungsanker hartkodiert** (`_format_calibration_notes`) —
Destillat der Teacher-Alignment-Studie; NIE ändern ohne
Alignment-Recheck (→ toadapt-change-control). Feedback wird sanitized:
`DISALLOWED_FEEDBACK_PATTERNS` (Answer-Giving-Phrasen und spekulative
Details wie "finma", "microsoft") ersetzen das Feedback komplett durch
einen neutralen Scaffolding-Text.

`technical_fallback`: Liefert das Judge-LLM auch nach einem
Repair-Call kein valides JSON, wird ein Payload mit 0 Punkten,
`evaluation_status="technical_fallback"` und `needs_human_review=true`
gespeichert — das ist ein TECHNISCHER Zustand, keine inhaltliche
0-Punkte-Bewertung. Nachbewertung: `scripts/retry_technical_fallback_scores.py`
(echter LLM-Call, → toadapt-run-and-operate).

## 5. Business Model Canvas und Canvas-Scoring

Business Model Canvas (BMC) = Standard-Raster, das ein Geschäftsmodell in
9 Bausteine zerlegt. Es ist der EINZIGE Rahmen, der studierendensichtbar
benannt werden darf (er ist der verbindliche Analyserahmen des Kurses,
kein verbotenes Framework). Die 9 Blöcke, mit den `key`-IDs wie im Code
(`BUSINESS_MODEL_CANVAS_BLOCKS` in `frontend/app/cases/[id]/page.tsx` —
Achtung: dort hartkodiert inkl. Alpes-Bank-spezifischer Hints; neue Cases
brauchen Frontend-Anpassung):

`value_propositions`, `customer_segments`, `channels`,
`customer_relationships`, `revenue_streams`, `key_resources`,
`key_activities`, `key_partners`, `cost_structure`.

Pflicht-Blöcke pro Frage (aus `backend/config/rubrics/`, Stand 2026-07-08):

| Frage (TP) | required_canvas_blocks |
|------------|------------------------|
| q1 (TP1)   | customer_relationships, channels, revenue_streams |
| q2 (TP2)   | value_propositions, key_resources, cost_structure |
| q3 (TP3)   | key_partners, key_activities, key_resources |
| q4 (TP4)   | value_propositions, key_activities, key_resources, cost_structure |

Scoring (alles in `rubric_evaluator.py`):
1. Pro Frage vergibt der Judge `canvas_alignment_score` ∈ [0, 1]
   (Prompt-Anker: 1.0 = korrekt/fallbezogen/integriert angewendet,
   0.5 = teilweise/oberflächlich, 0.0 = keine belastbare Canvas-Logik)
   plus `addressed_/missing_canvas_blocks` und `canvas_rationale`.
2. Submission-Ebene, **punktegewichteter Schnitt**:
   `canvas_alignment_pct = Σ(score_q × max_points_q) / Σ(max_points_q) × 100`
   — eine 30-Punkte-Frage wiegt also mehr als eine 22-Punkte-Frage.
3. `rubric_fit_pct = percentage × 0.7 + canvas_alignment_pct × 0.3`
   (70/30 — die zentrale Misch-Kennzahl im Dashboard).
4. **Exemplar-Kandidat** (`canvas_exemplar_candidate`): `percentage ≥
   min(score_floor_pct)` UND `canvas_alignment_pct ≥
   min(exemplar_threshold_pct)` — jeweils das MINIMUM über die beteiligten
   Rubrics (`rubric_evaluator.py`, `_is_exemplar_candidate`; 75/80 sind
   nur die Loader-Defaults). Für den Golden-Full-Case (nutzt alle vier
   tpN-Rubrics) gilt effektiv `percentage ≥ 72` (min über 75/75/72/75)
   und `canvas_alignment_pct ≥ 80` (min über 80/82/80/82). "Exemplar" =
   eine Abgabe, die als Qualitätsanker für spätere
   Auswertung taugt — KEINE Musterlösung und wird Studierenden nie gezeigt.

Der "Golden Case" des Repos ist `alpes-bank-genai-001` (+ `-en`-Variante)
in `backend/cases/pool/`: difficulty `full`, q1–q4 mit Bloom 4/5/4/6 und
25/24/22/30 Punkten (Summe 101). Neu generierte Einzel-TP-Cases haben
laut `TP_GENERATION_PARAMS` (`backend/cases/generator.py`) andere Zuschnitte
(TP1: 3 Fragen/25 Pkt, TP2: 3/24, TP3: 4/22, TP4: 3/30).

## 6. Das Assessment-Modell — Individuum im Tool, Gruppe beim Tutor

So hängt Tool und Kurs zusammen (Klärung der Ownerin, Stand 2026-07-08):

1. Studierende arbeiten im Tool **individuell** (identifiziert per
   `matrikelnummer`) — das Tool ist VORBEREITUNG auf die Gruppenarbeit,
   kein Gruppenprodukt.
2. Studierende gehören organisatorisch zu 6er-Gruppen in Übungsgruppen.
   Die Gruppenabgabe (Slides/Memo/Decision Log/Strategy-on-a-Page, s. §2)
   entsteht AUSSERHALB des Tools.
3. Der Tutor (ÜGL) **assessed die GRUPPE in der Präsenzphase** —
   "assessed" heißt: beurteilt formativ, benotet NICHT.
4. Das Tool liefert dem Tutor **Fehlerquellen-Hinweise pro Person**:
   `GET /dashboard/difficulties` (`backend/dashboard/routes.py`) liefert je
   Matrikelnummer `attention_level` (high/medium/low), `weak_objectives`
   (schwache Lernziel-Tags), `weak_blooms`, `missing_canvas_blocks`,
   `recurring_penalties` (wiederkehrende Schwächen aus Judge-Feedback)
   sowie Kohorten-Aggregate. Chat-Logs sieht der Tutor NICHT.

**Bekannte konzeptionelle Lücke:** Im Code existiert KEIN Gruppenkonzept —
nur `matrikelnummer`. Das Dashboard kann daher nicht nach Gruppen
aggregieren, obwohl die Gruppe die Assessment-Einheit ist. Das ist die
größte offene Design-Frage (→ toadapt-architecture-contract /
toadapt-research-frontier); erfinde beim Lesen des Codes keine
Gruppen-Semantik, die nicht da ist.

Automatische BENOTUNG gibt es bewusst nicht: Pfadoffene Rubrics + Judge
mit Review-Flags liefern formatives Feedback und Tutor-Hinweise, keine
Noten.

## 7. Kurs-reservierte Cases: ON Running und NORDIC HOME

- **ON Running** = der reale Kurs-Case des Präsenzkurses (Gruppenarbeit
  über 4 TPs). Das Tool arbeitet mit AI-generierten FIKTIVEN Mini-Cases.
  Würde ein generierter Case ON Running referenzieren oder imitieren,
  würde das Tool die Kurs-Gruppenarbeit vorwegnehmen.
- **NORDIC HOME** = der geheime Klausur-Case. Jede Referenz wäre
  Prüfungskompromittierung.

Durchsetzung: `RESERVED_CASE_TERMS = ["ON Running", "NORDIC HOME"]` in
`backend/cases/validator.py` (Zeile 19). Der Validator prüft Titel,
Tagline, alle Sections, Exhibits und Fragen wortgrenzen-genau und
case-insensitiv; ein Treffer ist ein **error** (`reserved_case_reference`)
und blockiert `POST /admin/cases/{id}/approve` (HTTP 422; ein
`force`-Override wird protokolliert — nutze ihn dafür NIE, →
toadapt-change-control). Dieselbe Datei blockiert verbotene
Framework-Namen im Case-Text (error `forbidden_framework_name`).
Beide Namen dürfen auch in Tests, Fixtures oder Skills nur als VERBOT
erwähnt werden, nie als Inhalt.

## 8. Glossar der Projektbegriffe

| Begriff | Bedeutung in DIESEM Projekt |
|---------|------------------------------|
| TP / Touchpoint | Eine der 4 Kursphasen (TP1–TP4) mit eigenem Bloom-Profil, Format und Deadline (§2). Im Code: `tp_phase`, `target_tp` (0 = `full`). |
| BWL A | Grundlagenkurs Betriebswirtschaftslehre an der Universität St.Gallen (HSG), ~2.000 Studierende. |
| Scaffolding | Lernbegleitung durch Fragen/Denkimpulse statt Antworten (§3). Gegenteil: Answer-Giving. |
| Metacognitive-First | Jede Chat-Session beginnt mit dem metakognitiven Agenten (§3). Im Code: `metacognitive_phase_complete`. |
| Guardrail-Fallback | Fester Ersatztext, der eine regelverletzende Agent-Antwort KOMPLETT ersetzt (§3, `_guardrail_fallback`). |
| Framework-Dropping | Anti-Pattern: Modellnamen (Porter, VRIO …) studierendensichtbar nennen. Global + TP-spezifisch verboten (§3). |
| Pfadoffenheit | Rubric-Prinzip: keine Musterlösung, jeder schlüssige Pfad kann volle Punkte erreichen (§4). |
| Rubric | Bewertungsraster pro Frage: `evaluation_focus` + `required_canvas_blocks` + Schwellen (§4), NICHT Punkte/Bloom. |
| Kalibrierungsanker | Hartkodierte Judge-Hinweise pro q1–q4 aus der Teacher-Alignment-Studie (§4). Change-Control-pflichtig. |
| LLM-as-Judge | Der Rubric-Evaluator: ein LLM bewertet Freitext-Antworten gegen die Rubric (§4). |
| technical_fallback | `evaluation_status`, wenn das Judge-JSON auch nach Repair unparsebar war: 0 Punkte, Review-Flag — technisch, nicht inhaltlich (§4). |
| needs_human_review | Judge-Flag: Mensch soll nachbewerten (Grenzfall, low confidence, technischer Fehler). |
| Canvas / BMC | Business Model Canvas, 9 Blöcke; einziger benennbarer Analyserahmen (§5). |
| canvas_alignment_pct | Punktegewichteter Canvas-Score der Submission in % (§5). |
| rubric_fit_pct | `percentage × 0.7 + canvas_alignment_pct × 0.3` (§5). |
| Exemplar(-Kandidat) | Abgabe über den min()-Schwellen der beteiligten Rubrics (Golden-Full-Case effektiv: ≥72 % Punkte UND ≥80 % Canvas, §5) — Qualitätsanker, keine Musterlösung. |
| ÜGL / Tutor | Übungsgruppenleitung: leitet die Präsenz-Übungsgruppe, assessed die Gruppenabgaben (beurteilt, benotet nicht) und nutzt das Fehlerquellen-Dashboard (§6). |
| Matrikelnummer | Studierenden-ID der HSG; einziger Personen-Identifier im Code (§6). |
| Kohorten-Code | Optionaler Zugangscode für den Studenten-Flow (`STUDENT_ACCESS_CODE`; leer = offen). |
| Case-Pool | Freigegebene Mini-Cases in `backend/cases/pool/` (Status draft→approved→retired, `backend/models/case.py`). |
| Golden Case | `alpes-bank-genai-001`: der eine approved Full-Case, Referenz für Tests und Alignment (§5). |
| Glossar-Chips | Klickbare Fachbegriffe im Case-Reader; `CASE_GLOSSARY` ist pro case_id im Frontend hartkodiert. |
| ON Running / NORDIC HOME | Kurs-Case / Klausur-Case — reserviert, dürfen nirgends erscheinen (§7). |
| Teacher-Alignment-Studie | Blind-Review-Vergleich Judge vs. Lehrkraft (64 Frage-Zeilen, 16 Submissions); Basis der Kalibrierungsanker. Details → toadapt-judge-alignment-campaign. |
| SGMM | St.Galler Management-Modell — erlaubtes Denkwerkzeug in `allowed_frameworks` (Umwelt-Organisation-Spannungsfeld); als Name in Case-Texten unkritisch, taucht aber studierendensichtbar im Tool nicht auf. |

## Provenance und Wartung

Erstellt: 2026-07-08 gegen den damaligen Stand von main (HEAD `141bb63`,
nach dem filter-repo-Rewrite vom 2026-07-08).
Alle Code-Fakten wurden am 2026-07-08 direkt gegen die Quelldateien
verifiziert. Re-Verifikation pro drift-anfälligem Fakt (vom Repo-Root):

- Bloom-Tags: `grep -n -A 8 "_make_tags" backend/evaluator/rubric_evaluator.py`
- TP-Bloom/Format/individual_component: `grep -n "bloom_levels\|\"format\"\|individual_component" backend/config/tp_configs.py`
- TP4-Guardrail-Lücke: `python3 -c "from backend.config.tp_configs import TP_CONFIGS; print('forbidden_framework_names' in TP_CONFIGS[4])"`
- TP-Kalender: `grep -n -A 6 "TP_SCHEDULE" backend/config/tp_configs.py`
- target_tp hartkodiert: `grep -rn "target_tp: 1" frontend/app/cases/`
- Agent-Verbote/Prompts: `grep -n "Niemals\|Never:" backend/agents/orchestrator.py`
- Guardrail-Reihenfolge: `grep -n -A 20 "def guardrail_check" backend/agents/orchestrator.py`
- Metacognitive-Phase-Ende: `grep -n "metacognitive_phase_complete = True" backend/agents/orchestrator.py`
- Rubric-Inhalt & Canvas-Blöcke: `python3 -c "import json;[print(i,[ (q,[b['block'] for b in d['questions'][q]['required_canvas_blocks']]) for q in d['questions']]) for i,d in ((i,json.load(open(f'backend/config/rubrics/tp{i}_rubric.json'))) for i in (1,2,3,4))]"`
- Scoring-Formeln (0.55/0.25, 70/30, Exemplar): `grep -n "0.55\|0.25\|\* 0.7\|\* 0.3\|score_floor_pct\|exemplar_threshold_pct" backend/evaluator/rubric_evaluator.py backend/evaluator/rubric_loader.py`
- Kalibrierungsanker: `grep -n -A 4 "_format_calibration_notes" backend/evaluator/rubric_evaluator.py`
- Reservierte Cases: `grep -n "RESERVED_CASE_TERMS" backend/cases/validator.py`
- Canvas-Blöcke/Glossar im Frontend: `grep -n "BUSINESS_MODEL_CANVAS_BLOCKS\|CASE_GLOSSARY" "frontend/app/cases/[id]/page.tsx"`
- Wortlimits nach Index: `grep -n "minWords" "frontend/app/cases/[id]/page.tsx"`
- Fehlerquellen-Dashboard: `grep -n "difficulties\|StudentDifficulty" backend/dashboard/routes.py`
- Golden Case: `python3 -c "import json; d=json.load(open('backend/cases/pool/alpes-bank-genai-001.json')); print(d['status'], [(q['question_id'],q['bloom_level'],q['max_points']) for q in d['questions']])"`
- Generierungs-Zuschnitte: `grep -n -A 5 "TP_GENERATION_PARAMS" backend/cases/generator.py`
