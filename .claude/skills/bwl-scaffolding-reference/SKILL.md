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
  (Individuum im Tool, Gruppen-Aggregate beim Tutor, group_code,
  Pseudonymisierung), formative Live-Unterstützung (Denkanstoß,
  Canvas-Abdeckung, Selbst-Check), warum "ON Running" und
  "NORDIC HOME" verboten sind, oder Projektjargon wie ÜGL, Matrikelnummer /
  Teilnehmer-ID, technical_fallback. Typische Symptome: "Was bedeutet dieses
  Feld im Rubric-JSON?", "Warum darf der Agent keinen Framework-Namen sagen?",
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
- Du willst die pädagogische Qualität von Agent-Antworten/Denkanstößen
  MESSEN (NAACL-Taxonomie, Judge-Läufe) →
  **toadapt-tutor-response-evaluation**
- Du willst Lernverläufe/Mastery über Zeit auswerten →
  **toadapt-knowledge-tracing**

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
(Modul-Konstante `BLOOM_TAGS` + `_make_tags` in
`backend/evaluator/rubric_evaluator.py`).
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
NICHT die CLAUDE.md-Kopie. Stand 2026-07-09 (re-verifiziert, unverändert):

| TP | Name | Kurs-Format (Gruppenabgabe) | Bloom | Case-Kapitel | individual_component |
|----|------|------------------------------|-------|--------------|----------------------|
| 1 | Analyse & Stakeholder | 3 Slides (PDF) | 2–4 | A | "Was würden Sie an Ihrer eigenen Analyse konkret verändern – und warum?" — 6 Pkt, 5 Min |
| 2 | Strategische Entscheidung | Management-Memo (1 Seite, PDF) | 4–5 | A, B | "Welche Entscheidung würden Sie anders treffen?" — 8 Pkt, 5 Min |
| 3 | Strategie in den Markt übersetzen | Decision Log (max. 2 Seiten A4, PDF) | 3–5 | A, B, C | "Wo weicht die Umsetzung am stärksten von der Strategie ab?" — 8 Pkt, 5 Min |
| 4 | Integration & Gesamtbild | Strategy-on-a-Page (1 Seite) | 5–6 | A–D | "Riskanteste Entscheidung + Revisionskonsequenz (Kaskadeneffekt)" — 10 Pkt, 10 Min |

Einordnung: `format` und `case_chapters` beschreiben den PRÄSENZKURS
(Gruppenabgaben zum Kurs-Case), nicht das Tool. Im Tool beantworten
Studierende Freitext-Fragen zu AI-generierten Mini-Cases; Wortlimits kommen
seit 2026-07-09 primär aus der Case-Frage (`question.min_words`/`max_words`,
Case-Paket); fehlen sie, greift der Index-Fallback im Frontend
(`frontend/app/cases/[id]/page.tsx`: Index 0–1 → 50–200 Wörter,
Index 2–3 → 100–200, danach 150–200). `individual_component` ist der
geplante Einzelanteil in der Präsenzphase.

TP-Kalender (`TP_SCHEDULE`, ebd.): TP1 2026-09-14…10-05, TP2 10-06…10-26,
TP3 10-27…11-16, TP4 11-17…12-07. BEHOBEN (2026-07-09): Die frühere Lücke
"`current_tp_phase()` existiert, wird aber nicht benutzt — Frontend sendet
`target_tp: 1` hartkodiert" ist geschlossen (Commit e71d9ee):
`GET /tp` (public, `backend/api/routes.py`) liefert `current_tp` + Schedule,
der Case-Pool filtert auf die aktuelle Phase (umschaltbar), und `target_tp`
kommt aus `case.target_tp` bzw. der aktuellen Phase — nicht mehr hartkodiert.
(Die `TP*_START`-Env-Variablen bleiben weiterhin tot — `TP_SCHEDULE` ist
hartkodiert.)

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
2 Sections à max. 400 Zeichen. Agent-Guidance (`key_tensions`,
`common_mistakes`, `case_summary`) kommt seit 2026-07-09 PRIMÄR aus dem
Case-Paket (`case.agent_guidance`, `backend/models/case.py`);
`{case_id}-agent.json` aus `backend/cases/pool/` ist nur noch Fallback für
den kuratierten Alpes-Case (`scaffolding_questions`/`learning_objectives`
darin bleiben ungenutzt). Sprache EN, wenn
`experiment.metadata.language == "en"` oder die case_id auf `-en` endet.

**Formative Live-Unterstützung (neu 2026-07-09, Commit 0c4acb8)** — drei
Scaffolding-Elemente direkt an der Antwort-Textbox, zusätzlich zum Chat:

- **Denkanstoß** (`POST /submissions/{id}/questions/{qid}/feedback`,
  Modul `backend/evaluator/formative_feedback.py`): sokratisches formatives
  Feedback zum Antwort-ENTWURF, OHNE Punkte, max. 2 pro Frage
  (`MAX_FEEDBACK_PER_QUESTION = 2`, danach HTTP 429; Rate-Limit 5/min).
  Guardrail-gefiltert mit Fallback-Frage — dieselbe Anti-Answer-Logik wie
  bei den Agenten. Pädagogische Qualitätsbewertung der Denkanstöße →
  **toadapt-tutor-response-evaluation**.
- **Canvas-Abdeckung** (`POST …/coverage`, Rate-Limit 30/min):
  DETERMINISTISCH (kein LLM) — matcht die `accepted_keywords` der Rubric
  serverseitig gegen den Entwurf; zurück gehen nur Block-Label +
  addressed-Flag. Die Keywords selbst verlassen den Server nie
  (Scoring-Signale dürfen nicht leaken).
- **Selbst-Check**: metakognitive Checkboxen pro Frage, rein clientseitig
  (kein Backend-Call, keine Persistenz).

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
`backend/evaluator/rubric_evaluator.py`). Seit 2026-07-09 (Commits
4fda3e9/f8abdc9) gilt **EMBEDDED-FIRST**: Die Rubric lebt primär
EINGEBETTET in der Case-Frage; die Datei-JSONs sind nur noch FALLBACK für
Alt-Cases:

```
CaseQuestion (im Case-JSON):  bloom_level, max_points,
        │   evaluation_focus, required_canvas_blocks, calibration_notes,
        │   exemplar_threshold_pct, score_floor_pct, min_words, max_words
        │
        ├─ hat evaluation_focus ODER required_canvas_blocks
        │        → _embedded_rubric() direkt aus der Frage
        │
        └─ sonst: rubric_reference, z. B. "tp1_rubric.json"
                 → backend/config/rubrics/tp{1-4}_rubric.json
                   payload["questions"][question_id]  (Fallback: "default")
                   (Datei-Payloads per lru_cache gecacht;
                    leere rubric_reference → None)
        ▼
QuestionRubric (backend/evaluator/rubric_loader.py)
```

Die Rubric (eingebettet wie Datei) enthält pro Frage NUR:
- `evaluation_focus`: 3 Prosa-Kriterien, worauf der Judge achtet
- `required_canvas_blocks`: Pflicht-Canvas-Bausteine (s. §5) mit `block`,
  `label`, `accepted_keywords` (nur Signale!), `expectation`, `weight`
- `exemplar_threshold_pct` und `score_floor_pct` — reale Per-Frage-Werte
  (verifiziert 2026-07-09, identisch in Golden-Case-Einbettung und
  Datei-Fallback): q1/tp1 80.0/75.0, q2/tp2 82.0/75.0, q3/tp3 80.0/72.0,
  q4/tp4 82.0/75.0. 80.0/75.0 sind nur die DEFAULTS aus
  `backend/evaluator/rubric_loader.py` (greifen, wenn die Felder fehlen)

Zusätzlich trägt die CaseQuestion `calibration_notes` (s. u.) und
`min_words`/`max_words` (Wortlimits, s. §2); der Case selbst trägt
`glossary` und `agent_guidance` (s. §3/§8) — das komplette "Case-Paket",
das der Generator (`backend/cases/generator.py`, max_tokens 8192) erzeugt
und der Validator prüft (Warnung `missing_embedded_rubric` bei fehlenden
Canvas-Blöcken, Warnungen bei Keywords-losen Blöcken, fehlendem
Glossar/Guidance, Glossar-Begriffen ohne wörtliches Text-Vorkommen).

**Bloom-Stufe und Punktzahl leben in der Case-Frage, NICHT in der Rubric.**
Die Datei-Rubrics (je genau ein Eintrag, tp1→q1 … tp4→q4) bleiben als
Fallback für Alt-Cases erhalten; Äquivalenz eingebettet↔Datei ist in
`tests/test_case_package.py` bewiesen.

Der Judge (`EVALUATOR_SYSTEM` + `EVALUATE_PROMPT`) arbeitet konservativ:
Punktleitplanken sind abgeleitet (`mid = max_points × 0.55`,
`low = × 0.25`), fehlende Pflichtbestandteile deckeln das obere Band,
Unsicherheit → `needs_human_review = true` (bei
`judge_confidence == "low"` erzwungen). Die **Kalibrierung ist seit
2026-07-09 ZWEISTUFIG** (`_format_calibration_notes`):
`question.calibration_notes` (case-spezifische Anker aus dem Case-Paket)
ERSETZEN, wenn vorhanden, die generischen `BLOOM_CALIBRATION_ANCHORS`
(pro Bloom-Stufe 2–6, Modul-Konstante in `rubric_evaluator.py`). Die
früher pro q1–q4 HARTKODIERTEN Anker existieren nicht mehr im Code — sie
wurden wörtlich in die Golden-Case-JSONs migriert
(`backend/cases/pool/alpes-bank-genai-001*.json`, Feld `calibration_notes`;
Bug-Fix: generierte Cases erben die Alpes-Anker nicht mehr über
q1–q4-IDs). Inhaltlich bleiben sie Destillat der Teacher-Alignment-Studie;
NIE ändern ohne Alignment-Recheck (→ toadapt-change-control).
Feedback wird sanitized:
`DISALLOWED_FEEDBACK_PATTERNS` (Answer-Giving-Phrasen und spekulative
Details wie "finma", "microsoft") ersetzen das Feedback komplett durch
einen neutralen Scaffolding-Text.

`technical_fallback`: Liefert das Judge-LLM auch nach einem
Repair-Call kein valides JSON — oder valides JSON mit typ-ungültigen
Zahlen (z. B. `awarded_points: "acht"`, seit b093fd8 kein 500 mehr) —
wird ein Payload mit 0 Punkten,
`evaluation_status="technical_fallback"` und `needs_human_review=true`
gespeichert — das ist ein TECHNISCHER Zustand, keine inhaltliche
0-Punkte-Bewertung. Nachbewertung: `scripts/retry_technical_fallback_scores.py`
(echter LLM-Call, → toadapt-run-and-operate).

## 5. Business Model Canvas und Canvas-Scoring

Business Model Canvas (BMC) = Standard-Raster, das ein Geschäftsmodell in
9 Bausteine zerlegt. Es ist der EINZIGE Rahmen, der studierendensichtbar
benannt werden darf (er ist der verbindliche Analyserahmen des Kurses,
kein verbotenes Framework). Die 9 Blöcke, mit den `key`-IDs wie im Code
(`BUSINESS_MODEL_CANVAS_BLOCKS` in `frontend/app/cases/[id]/page.tsx`).
Seit 2026-07-09 baut das Frontend den Canvas-Guide aus dem Case-Paket
(`deriveCanvasBlocks`: Union der `required_canvas_blocks` aller Fragen,
`expectation` als Hint) — neue Cases brauchen also KEINE
Frontend-Anpassung mehr; der hartkodierte Block-Katalog mit
Alpes-Bank-Hints bleibt Fallback und gilt weiterhin für den Golden Case
(`alpes-bank-genai-001*`):

`value_propositions`, `customer_segments`, `channels`,
`customer_relationships`, `revenue_streams`, `key_resources`,
`key_activities`, `key_partners`, `cost_structure`.

Pflicht-Blöcke pro Frage (Golden Case eingebettet; identisch im
Datei-Fallback `backend/config/rubrics/`; verifiziert 2026-07-09):

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
   Rubrics (`rubric_evaluator.py`, `_canvas_exemplar_candidate`; 75/80 sind
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

So hängt Tool und Kurs zusammen (Klärung der Ownerin, Stand 2026-07-09):

1. Studierende arbeiten im Tool **individuell** (UI-Label "Teilnehmer-ID";
   `user_id` und `matrikelnummer` werden serverseitig PSEUDONYMISIERT —
   `backend/anonymize.py::pseudonymize`, HMAC-SHA256 mit `PSEUDONYM_SECRET`,
   Prefix `anon-`, idempotent; ohne Secret roh + Startup-Warnung
   `pseudonymization_disabled`; Secret-Rotation bricht alle Lernverläufe,
   → toadapt-knowledge-tracing) — das Tool ist VORBEREITUNG auf die
   Gruppenarbeit, kein Gruppenprodukt.
2. Studierende gehören organisatorisch zu 6er-Gruppen in Übungsgruppen.
   Beim Login geben sie ihre Gruppe als **Selbstauskunft** an (`group_code`,
   Pflichtfeld außer bei Prolific-URL-Ankunft; normalisiert `'12'→'G12'`
   via `backend/anonymize.py::normalize_group_code`); Session und
   Submission tragen den `group_code`. Die Gruppenabgabe (Slides/Memo/
   Decision Log/Strategy-on-a-Page, s. §2) entsteht AUSSERHALB des Tools —
   seit 2026-07-10 kann der Master-Tutor sie aber als ZIP hochladen
   (`/upload`-Reiter): jedes PDF wird per Deckblatt-Indikator ("Gruppe 12")
   seiner Gruppe zugeordnet und vom Judge gegen die TP-Rubric des gewählten
   Touchpoints bewertet (`backend/group_uploads/`, Punkteskala des Golden
   Case: 25/24/22/30). Die Ergebnisse erscheinen als ZWEITE Datenquelle in
   den Gruppen-Aggregaten (`group_work_count`, `group_work_avg_pct`,
   `group_work`-Liste im GroupDetail) — weiterhin Gruppenebene, keine
   Einzelkennungen; die Bewertung ist formativ-informierend, kein Grading.
3. Der Tutor (ÜGL) **assessed die GRUPPE in der Präsenzphase** —
   "assessed" heißt: beurteilt formativ, benotet NICHT.
4. Das Tool liefert dem Tutor **NUR Gruppen-Aggregate**:
   `GET /dashboard/groups` + `/dashboard/groups/{code}`
   (`backend/dashboard/routes.py`, `GroupSummary`/`GroupDetail` — enthalten
   KEINE Einzelkennungen; u. a. `avg_percentage`, Attention-Verteilung,
   `needs_human_review_count`, `paste_heavy_answers`). Das ist die im
   Login zugesagte Privacy-Garantie ("Tutor:innen sehen nur
   Gruppen-Zusammenfassungen"). Die Einzelpersonen-Endpoints
   `/dashboard/students`, `/dashboard/student/{m}` und
   `/dashboard/difficulties` (pro Pseudonym `attention_level`,
   `weak_objectives`, `weak_blooms`, `missing_canvas_blocks`,
   `recurring_penalties`) verlangen ZUSÄTZLICH `RESEARCH_API_KEY` via
   Header `X-Research-Key` (fail-closed 503; falscher Key 401) — sie sind
   FORSCHENDEN vorbehalten. Der Teacher-Proxy kennt nur `TOADAPT_API_KEY`,
   Tutor:innen bekommen dort 401: DAS IST GEWOLLT, kein Bug.
   Chat-Logs sieht der Tutor weiterhin NICHT.

**BEHOBEN (2026-07-09, Commit e71d9ee):** Die früher hier geführte
konzeptionelle Lücke "Im Code existiert KEIN Gruppenkonzept — nur
`matrikelnummer`; das Dashboard kann nicht nach Gruppen aggregieren" ist
geschlossen: `group_code` per Login-Selbstauskunft (s. o.), Dashboard
komplett auf Gruppen-Aggregate umgebaut (Einzelprofil-UI entfernt).
Offen bleibt die Forschungsfrage gruppen-bewusster Tutor-Insights
(→ toadapt-research-frontier).

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
| Rubric | Bewertungsraster pro Frage: `evaluation_focus` + `required_canvas_blocks` + Schwellen (§4), NICHT Punkte/Bloom. Seit 2026-07-09 primär IN der Case-Frage eingebettet; `tp{n}_rubric.json` nur Datei-Fallback. |
| Case-Paket | Vollständig eingebettete Frage-Ausstattung eines Case: Rubric-Felder + `calibration_notes` + Wortlimits pro Frage, `glossary` + `agent_guidance` pro Case (§4). |
| Kalibrierungsanker | Judge-Hinweise, zweistufig: case-spezifische `question.calibration_notes` VOR generischen `BLOOM_CALIBRATION_ANCHORS` pro Bloom-Stufe (§4). Change-Control-pflichtig. |
| Denkanstoß | Formatives Feedback zum Antwort-Entwurf: sokratisch, OHNE Punkte, max. 2 pro Frage, guardrail-gefiltert (§3). |
| LLM-as-Judge | Der Rubric-Evaluator: ein LLM bewertet Freitext-Antworten gegen die Rubric (§4). |
| technical_fallback | `evaluation_status`, wenn das Judge-JSON auch nach Repair unparsebar war: 0 Punkte, Review-Flag — technisch, nicht inhaltlich (§4). |
| needs_human_review | Judge-Flag: Mensch soll nachbewerten (Grenzfall, low confidence, technischer Fehler). |
| Canvas / BMC | Business Model Canvas, 9 Blöcke; einziger benennbarer Analyserahmen (§5). |
| canvas_alignment_pct | Punktegewichteter Canvas-Score der Submission in % (§5). |
| rubric_fit_pct | `percentage × 0.7 + canvas_alignment_pct × 0.3` (§5). |
| Exemplar(-Kandidat) | Abgabe über den min()-Schwellen der beteiligten Rubrics (Golden-Full-Case effektiv: ≥72 % Punkte UND ≥80 % Canvas, §5) — Qualitätsanker, keine Musterlösung. |
| ÜGL / Tutor | Übungsgruppenleitung: leitet die Präsenz-Übungsgruppe, assessed die Gruppenabgaben (beurteilt, benotet nicht) und sieht im Dashboard NUR Gruppen-Aggregate (§6). |
| Matrikelnummer | Studierenden-ID der HSG; im UI neutral "Teilnehmer-ID", serverseitig pseudonymisiert gespeichert (HMAC, `anon-`-Prefix, §6). |
| group_code | Übungsgruppe per Selbstauskunft beim Login (`'12'→'G12'` normalisiert); Aggregationsschlüssel des Tutor-Dashboards (§6). |
| Kohorten-Code | Optionaler Zugangscode für den Studenten-Flow (`STUDENT_ACCESS_CODE`; leer = offen). |
| Case-Pool | Freigegebene Mini-Cases in `backend/cases/pool/` (Status draft→approved→retired, `backend/models/case.py`). |
| Golden Case | `alpes-bank-genai-001`: der eine approved Full-Case, Referenz für Tests und Alignment (§5). |
| Glossar-Chips | Klickbare Fachbegriffe im Case-Reader; kommen aus `case.glossary` (Case-Paket); der Frontend-Hardcode `CASE_GLOSSARY` hat pro case_id Vorrang (nur Alpes). |
| ON Running / NORDIC HOME | Kurs-Case / Klausur-Case — reserviert, dürfen nirgends erscheinen (§7). |
| Teacher-Alignment-Studie | Blind-Review-Vergleich Judge vs. Lehrkraft (64 Frage-Zeilen, 16 Submissions); Basis der Kalibrierungsanker. Details → toadapt-judge-alignment-campaign. |
| SGMM | St.Galler Management-Modell — erlaubtes Denkwerkzeug in `allowed_frameworks` (Umwelt-Organisation-Spannungsfeld); als Name in Case-Texten unkritisch, taucht aber studierendensichtbar im Tool nicht auf. |

## Provenance und Wartung

Update 2026-07-11: Assessment-Modell um den Master-Upload der
Gruppenarbeiten ergänzt (zweite Datenquelle in den Gruppen-Aggregaten,
Commit `6350dca`); Gruppencode-Selbstauskunft wird seit `935e1ed` optional
gegen das Kurs-Schema validiert (GROUP_CODE_MAX, 422 bei Tippfehlern).

Erstellt: 2026-07-08 gegen den damaligen Stand von main (HEAD `141bb63`,
nach dem filter-repo-Rewrite vom 2026-07-08).
Update 2026-07-09 (HEAD 64b62f9): Rubric embedded-first (Case-Paket) +
zweistufige Kalibrierung (calibration_notes vor BLOOM_CALIBRATION_ANCHORS,
q1–q4-Hardcode in Golden-Case-JSONs migriert); formative
Live-Unterstützung (Denkanstoß max 2/Frage, Canvas-Abdeckung, Selbst-Check);
Assessment-Modell mit group_code-Selbstauskunft, Pseudonymisierung und
Gruppen-Aggregaten fürs Tutor-Dashboard (Einzel-Endpoints research-gated);
TP-Progression aktiv (target_tp-Hardcode BEHOBEN); Canvas-Guide/Glossar/
Wortlimits/Agent-Guidance aus dem Case-Paket (Alpes-Hardcodes als Fallback
bzw. Vorrang); Bloom-Tags jetzt Modul-Konstante BLOOM_TAGS.
Update 2026-07-09 (HEAD 64b62f9): Re-Verifikation aller Fakten gegen den
Code (90 pytest-Tests grün); Methodenname korrigiert:
`_canvas_exemplar_candidate` (nicht `_is_exemplar_candidate`).
Alle Code-Fakten wurden am 2026-07-09 direkt gegen die Quelldateien
verifiziert. Re-Verifikation pro drift-anfälligem Fakt (vom Repo-Root):

- Bloom-Tags: `grep -n -A 8 "_make_tags" backend/evaluator/rubric_evaluator.py`
- TP-Bloom/Format/individual_component: `grep -n "bloom_levels\|\"format\"\|individual_component" backend/config/tp_configs.py`
- TP4-Guardrail-Lücke: `python3 -c "from backend.config.tp_configs import TP_CONFIGS; print('forbidden_framework_names' in TP_CONFIGS[4])"`
- TP-Kalender: `grep -n -A 6 "TP_SCHEDULE" backend/config/tp_configs.py`
- target_tp aus Case/Phase (nicht mehr hartkodiert): `grep -n "target_tp" "frontend/app/cases/[id]/page.tsx"` und `grep -n "current_tp" backend/api/routes.py`
- Agent-Verbote/Prompts: `grep -n "Niemals\|Never:" backend/agents/orchestrator.py`
- Guardrail-Reihenfolge: `grep -n -A 20 "def guardrail_check" backend/agents/orchestrator.py`
- Metacognitive-Phase-Ende: `grep -n "metacognitive_phase_complete = True" backend/agents/orchestrator.py`
- Rubric-Inhalt & Canvas-Blöcke: `python3 -c "import json;[print(i,[ (q,[b['block'] for b in d['questions'][q]['required_canvas_blocks']]) for q in d['questions']]) for i,d in ((i,json.load(open(f'backend/config/rubrics/tp{i}_rubric.json'))) for i in (1,2,3,4))]"`
- Scoring-Formeln (0.55/0.25, 70/30, Exemplar): `grep -n "0.55\|0.25\|\* 0.7\|\* 0.3\|score_floor_pct\|exemplar_threshold_pct" backend/evaluator/rubric_evaluator.py backend/evaluator/rubric_loader.py`
- Kalibrierung zweistufig: `grep -n -A 12 "_format_calibration_notes" backend/evaluator/rubric_evaluator.py` und `grep -n "BLOOM_CALIBRATION_ANCHORS" backend/evaluator/rubric_evaluator.py`
- Embedded-first-Loader: `grep -n -A 4 "def load_question_rubric" backend/evaluator/rubric_loader.py`
- Gruppen/Privacy: `grep -n "GroupSummary\|require_research_key" backend/dashboard/routes.py` und `grep -n "def pseudonymize\|def normalize_group_code" backend/anonymize.py`
- Formative Endpoints: `grep -n "coverage\|/feedback\|MAX_FEEDBACK_PER_QUESTION" backend/api/routes.py backend/evaluator/formative_feedback.py`
- Reservierte Cases: `grep -n "RESERVED_CASE_TERMS" backend/cases/validator.py`
- Canvas-Blöcke/Glossar im Frontend: `grep -n "BUSINESS_MODEL_CANVAS_BLOCKS\|CASE_GLOSSARY" "frontend/app/cases/[id]/page.tsx"`
- Wortlimits nach Index: `grep -n "minWords" "frontend/app/cases/[id]/page.tsx"`
- Fehlerquellen-Dashboard: `grep -n "difficulties\|StudentDifficulty" backend/dashboard/routes.py`
- Golden Case: `python3 -c "import json; d=json.load(open('backend/cases/pool/alpes-bank-genai-001.json')); print(d['status'], [(q['question_id'],q['bloom_level'],q['max_points']) for q in d['questions']])"`
- Generierungs-Zuschnitte: `grep -n -A 5 "TP_GENERATION_PARAMS" backend/cases/generator.py`
