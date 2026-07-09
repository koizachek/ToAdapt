---
name: toadapt-proof-and-analysis-toolkit
description: "First-Principles-Analysemethoden für ToAdapt, jeweils als Rezept mit durchgerechnetem Beispiel aus der Repo-Geschichte. Lade diese Skill, wenn du (a) eine Judge-vs.-Teacher-Vergleichsstudie designen oder auswerten willst (Blind-Review, review_item_id-Join, Scope-Regeln), (b) Alignment-Metriken interpretieren musst (Pearson r vs. MAE/RMSE vs. Mean Diff, within_2pt, Kleine-n-Ehrlichkeit bei n=16), (c) LLM-Kosten oder Token-Verbrauch abschätzen willst (llm_call_completed-Logs aggregieren), (d) eine Prompt-Änderung gegen die Guardrail-Pattern prüfen willst BEVOR sie live geht, (e) eine Hypothese sauber in Vorhersage und Messung übersetzen willst, oder (f) wissen musst, welcher Beweis-Typ für welche Behauptung NICHT reicht. Keywords: Pearson, MAE, RMSE, Bias, Kalibrierung, Korrelation, Blind Review, Workbook, Anker-Bias, Token, Kosten, prompt_tokens, guardrail_check, Regression, Hypothese, Vorhersage, Konfidenzintervall, in-sample, n=16."
---

# ToAdapt Proof-and-Analysis-Toolkit

Sechs Analysemethoden, mit denen dieses Projekt Behauptungen in Belege
verwandelt. Jede Methode: Rezept + durchgerechnetes Beispiel aus der
Repo-Geschichte. Repo-Root ist `/Users/dianakozachek/ToAdapt`; alle Pfade
sind repo-relativ, alle Kommandos laufen vom Repo-Root.

## Wann diese Skill NICHT gilt

| Du willst … | Lade stattdessen |
|---|---|
| die konkrete q4/Bloom-6-Kampagne ausführen (Schritte, Meilensteine) | `toadapt-judge-alignment-campaign` |
| wissen, welche Tests/Evidenz vor einem Commit Pflicht sind; neue pytest-Tests schreiben | `toadapt-validation-and-qa` |
| die 5 Forschungs-Skripte Schritt für Schritt bedienen (import → export → compare → retry → publish) | `toadapt-run-and-operate` |
| die generelle Evidenz-Bar, den Idee-Lebenszyklus, Publikationsstandards | `toadapt-research-methodology` |
| Log-Events und Diagnose-Endpoints als Katalog | `toadapt-diagnostics-and-tooling` |
| BWL-Begriffe verstehen (Bloom, TP, Canvas, Scaffolding, Rubric-Felder) | `bwl-scaffolding-reference` |
| eine Änderung freigeben/committen (Gates, Unverhandelbares) | `toadapt-change-control` |

## Begriffskasten (Erstnennung)

| Begriff | Bedeutung in diesem Projekt |
|---|---|
| Judge | Der LLM-Rubric-Evaluator (`backend/evaluator/rubric_evaluator.py`), der Studierenden-Freitextantworten pro Frage bepunktet |
| Teacher-Score | Punktzahl, die eine menschliche Lehrkraft derselben Antwort gibt — der Goldstandard |
| Blind-Review | Die Lehrkraft bewertet, OHNE die Judge-Scores zu sehen |
| Workbook | Excel-Datei (xlsx) aus der Export-Pipeline; eine Zeile = eine Frage-Antwort |
| review_item_id | Join-Schlüssel `{case_id}:{question_id}:{nnn}` zwischen Blind- und Rubric-Workbook |
| q1–q4 | Die vier Fragen eines Cases; q4 ist die Integrationsfrage (Bloom 6, 30 Punkte im Golden Case `alpes-bank-genai-001`) |
| Kalibrierungsanker | Bewertungshinweise im Judge-Prompt — ZWEISTUFIG seit 2026-07-09: case-spezifische `question.calibration_notes` (im Case-JSON, editierbar im Case-Editor; die studien-validierten Alpes-Anker liegen dort) haben Vorrang vor generischen `BLOOM_CALIBRATION_ANCHORS` pro Bloom-Stufe (`backend/evaluator/rubric_evaluator.py`) |
| Guardrail | Substring-/Regex-Prüfung `guardrail_check(text, tp)` in `backend/agents/orchestrator.py`, die Agent-Antworten bei Verstoß komplett durch einen Fallback-Text ersetzt |
| TP | Touchpoint 1–4, die Kursphasen; konfiguriert in `backend/config/tp_configs.py` (`TP_CONFIGS`) |

---

## Methode 1 — Ein Blind-Review-Protokoll designen

**Zweck:** Messen, wie gut der Judge mit einer Lehrkraft übereinstimmt,
ohne dass die Lehrkraft von den Judge-Scores beeinflusst wird.

### Warum blind?

Anker-Bias: Wer eine Zahl sieht, bevor er selbst bewertet, bewertet in
Richtung dieser Zahl (klassischer Verankerungseffekt). Deshalb erzeugt
`scripts/export_review_workbooks.py` ZWEI Workbooks aus denselben Daten:

- `{prefix}_{timestamp}_rubric.xlsx` — enthält alle Judge-Felder
  (rubric_awarded_points, feedback, canvas-Felder, judge_confidence …)
- `{prefix}_{timestamp}_blind.xlsx` — enthält NUR case_id, Frage,
  Antworttext plus zwei leere Spalten `teacher_awarded_points` und
  `teacher_rationale`. Keine user_id, keine participant_id, keine
  Prolific-IDs, keine Judge-Scores.

Die Lehrkraft bekommt ausschließlich die Blind-Datei.

### Der Join: review_item_id

Beide Workbooks tragen dieselbe `review_item_id` im Format
`{case_id}:{question_id}:{nnn}` (z. B. `alpes-bank-genai-001:q4:007`).
Der Zähler `nnn` wird pro (case_id, question_id) in der Reihenfolge
vergeben, in der Submissions in der Eingabedatei stehen
(`scripts/export_review_workbooks.py`, Zeile 178).

**Konsequenz (wichtig):** Blind- und Rubric-Workbook sind nur joinbar,
wenn sie aus DEMSELBEN Export-Lauf stammen. Ein Blind-Workbook von
gestern gegen ein Rubric-Workbook von heute zu joinen ist unsicher,
sobald sich die Submission-Datei geändert hat — die `nnn`-Indizes
verschieben sich.

### Warum das Lehrer-Workbook kanonisch ist

`scripts/compare_teacher_rubric_scores.py` nimmt das Lehrer-Workbook als
Grundgesamtheit; Rubric-Zeilen ohne passende `review_item_id` im
Lehrer-Workbook werden verworfen und im Summary als
`rubric_only_ids_excluded_by_design` gezählt (Zeile 337). Grund (aus dem
Modul-Docstring, Zeilen 1–6): In den Rohdaten steckten Testuser, die vor
dem Blind-Review bereinigt wurden. Wäre das Rubric-Workbook kanonisch,
kämen diese bereinigten Zeilen durch die Hintertür zurück in die Analyse.

### Scope-Regel: nur vollständige q1–q4-Submissions

Die 20260531-Studie (Report: `docs/teacher_alignment_report_20260531_17submissions.md`
— der Dateiname sagt fälschlich 17; der Inhalt und die kanonische Zahl
sind 16 Submissions) hat den Scope so definiert:

- Nur Submissions, bei denen q1, q2, q3 UND q4 in der Lehrerbewertung
  gemappt werden konnten. Einzelfrage-Einreichungen fliegen raus.
- Ergebnis: 16 Submissions × 4 Fragen = 64 bewertete Frage-Zeilen.

Ohne diese Regel vergleicht man Äpfel (komplette Bearbeitungen) mit
Birnen (Abbrecher, die nur q1 beantwortet haben) — und die
Frage-Subgruppen hätten ungleiche n.

### Rezept (Kommandos)

```bash
# 1. Workbooks erzeugen (Rubric + Blind + Chat-Turns aus denselben Daten)
.venv/bin/python scripts/export_review_workbooks.py \
  --submissions data/submission_states.json \
  --events data/experiment_events.json \
  --prefix myreview
# → data/prolific_runs/derived/review_exports/myreview_{ts}_blind.xlsx u.a.

# 2. NUR die Blind-Datei an die Lehrkraft geben; sie füllt
#    teacher_awarded_points (+ optional teacher_rationale) aus.

# 3. Vergleich rechnen
.venv/bin/python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook <ausgefuellte_blind.xlsx> \
  --rubric-workbook <myreview_{ts}_rubric.xlsx> \
  --prefix my_comparison
# → my_comparison.xlsx (Blätter: summary, by_question, item_comparison,
#   outliers, validation) + my_comparison_item_comparison.csv (Semikolon-CSV)
```

Hinweis: Echte Teilnehmerdaten liegen NICHT im Repo (Ablageort:
`~/ToAdapt_sensitive_data/`, niemals zurückkopieren oder committen).
Für Methoden-Tests synthetische Daten verwenden — siehe
`tests/test_compare_teacher_rubric_scores.py` als Vorbild.

### Design-Checkliste für eine neue Studie

- [ ] Blind- und Rubric-Workbook aus DEMSELBEN Export-Lauf?
- [ ] Testuser/Piloten VOR der Lehrer-Runde aus dem Lehrer-Workbook entfernt?
- [ ] Scope-Regel schriftlich fixiert, BEVOR Ergebnisse angeschaut werden?
- [ ] `validation`-Blatt geprüft (duplicate ids, question_id_mismatch, max_points_mismatch)?
- [ ] `technical_fallback`-Zeilen (0-Punkte-Judge-Ausfälle) gezählt und im Report ausgewiesen?

---

## Methode 2 — Alignment-Metriken korrekt lesen

Das Vergleichsskript liefert mehrere Metriken. Sie beantworten
VERSCHIEDENE Fragen — eine gute Zahl in der einen sagt nichts über die
andere:

| Metrik | Beantwortet | Sagt NICHTS über |
|---|---|---|
| Pearson r | "Sortiert der Judge die Antworten in dieselbe Reihenfolge wie die Lehrkraft?" (Rangordnung / lineare Kovariation) | absolute Punkthöhe |
| MAE (mean absolute error, Punkte) | "Wie weit liegt der Judge im Schnitt daneben?" (Kalibrierung) | Richtung des Fehlers |
| RMSE | wie MAE, bestraft Ausreißer quadratisch — RMSE ≫ MAE ⇒ wenige grobe Ausreißer | — |
| Mean Diff (rubric − teacher) | "Ist der Judge systematisch strenger (negativ) oder milder (positiv)?" (Bias-Richtung) | Streuung (Bias 0 kann aus +5/−5 gemittelt sein) |
| within_1pt_n / within_2pt_n | "Wie viele Items liegen praktisch beieinander?" (absolutes Band) | Vergleichbarkeit zwischen Fragen mit verschiedenen max_points |
| within_10pctpts_n | dasselbe als Prozentpunkte-Band — nutzbar über Fragen mit unterschiedlichen max_points hinweg (q1=25, q4=30 Punkte im Golden Case) | — |

### Lehrstück: der 2026-05-31-Befund

Aus `docs/teacher_alignment_report_20260531_17submissions.md`
(n=64 Zeilen, 16 Submissions), vor → nach Einführung der
Kalibrierungsanker:

| Metrik | Vorher | Nachher | Lesart |
|---|---:|---:|---|
| Pearson r | 0.631 | 0.796 | Rangordnung deutlich besser |
| MAE | 2.984 | 2.711 | Kalibrierung leicht besser |
| RMSE | 4.626 | 3.897 | grobe Ausreißer seltener |
| Mean Diff | −0.234 | −2.07 | **Judge wurde systematisch strenger** |
| teacher_higher_n | 28/64 | 48/64 | Unterbewertung in 3 von 4 Fällen |

**Die Pointe:** r stieg UND der Bias verschlechterte sich gleichzeitig.
Wer nur r berichtet hätte, hätte "Alignment verbessert" verkündet,
während der Judge real jedem Studierenden im Schnitt 2 Punkte zu wenig
gab. Korrelation ist keine Kalibrierung. Immer mindestens das Tripel
(r, MAE, Mean Diff) berichten.

Pro Frage zeigt derselbe Report die eigentliche Baustelle: q4 (Bloom 6,
Integration, 30 Punkte) mit MAE ≈ 4.97 und Mean Diff ≈ −4.97 nach
Kalibrierung — der Judge unterbewertet q4 systematisch. q1–q3 liegen bei
Pearson 0.75–0.92. Das ist das Thema der Skill
`toadapt-judge-alignment-campaign`.

### Kleine-n-Ehrlichkeit

Bei 64 Zeilen gesamt hat jede Frage-Subgruppe nur n=16. Wie fragil das
ist, zeigt das 95%-Konfidenzintervall für Pearson r (Fisher-z-Methode:
z = atanh(r), SE = 1/√(n−3), Intervall z ± 1.96·SE, zurück via tanh):

| Wert | n | 95%-CI |
|---|---:|---|
| Gesamt r = 0.631 (vorher) | 64 | [0.46, 0.76] |
| Gesamt r = 0.796 (nachher) | 64 | [0.68, 0.87] |
| q4 r = 0.642 (vorher) | 16 | [0.21, 0.86] |
| q4 r = 0.790 (nachher) | 16 | [0.48, 0.92] |

Die q4-Intervalle vorher/nachher überlappen massiv: Die per-Frage-
"Verbesserung" von r ist bei n=16 statistisch nicht unterscheidbar.
Konsequenzen:

- Sub-Gruppen-Zahlen (pro Frage) als **deskriptiv** kennzeichnen, keine
  Signifikanz-Theatralik (keine p-Wert-Sternchen auf n=16).
- Richtungs-Befunde (Mean Diff −4.97 bei q4, Unterbewertung in 48/64
  Items) sind trotzdem berichtbar — sie sind grob und konsistent, nicht
  von Dezimalstellen abhängig.
- Entscheidungen an **vorregistrierte Schwellen** binden (Methode 5),
  nicht an post-hoc-Signifikanz.

---

## Methode 3 — Kosten-/Token-Analyse

**Prinzip: MESSEN aus den Logs, nicht schätzen.** Jeder LLM-Call läuft
über den gemeinsamen Client `backend/llm.py` (Chat-Agenten,
Rubric-Evaluator, Case-Generator), der nach jedem Call den
Token-Verbrauch loggt (Zeilen 102–110):

```
llm_call_completed  model=… prompt_tokens=… completion_tokens=… total_tokens=…
```

Mit `ENVIRONMENT=production` sind das JSON-Zeilen
(`structlog.processors.JSONRenderer` in `backend/main.py`), lokal
Console-Format. Für Auswertungen JSON-Logs verwenden (Railway-Logs
abziehen oder lokal `ENVIRONMENT=production` setzen und stdout in eine
Datei leiten).

### Aggregieren (getestet)

```bash
python3 -c '
import json, sys
calls = prompt = completion = 0
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if "llm_call_completed" not in line:
        continue
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    if d.get("event") != "llm_call_completed":
        continue
    calls += 1
    prompt += d.get("prompt_tokens") or 0
    completion += d.get("completion_tokens") or 0
print(f"calls={calls} prompt_tokens={prompt} completion_tokens={completion}")
' app.log
```

Für Kosten pro Feature nach `model` gruppieren und ggf. das Logfile
vorher zeitlich filtern (Timestamps sind ISO-UTC).

### Call-Struktur (verifiziert im Code, Stand: 2026-07-08)

| Aktion | LLM-Calls | max_tokens (Completion-Deckel) |
|---|---|---|
| 1 Chat-Turn | 1 (`backend/agents/orchestrator.py`, Zeile 407) | 220 (CONCEPTUAL) / 320 (übrige Agenten) |
| 1 Submission-Evaluation | 4 (je Frage q1–q4) + 0–4 Repair-Calls bei JSON-Parse-Fehlern | 1200 pro Call |
| Case-Generierung | variabel (`backend/cases/generator.py`) | — |

Prompt-Tokens dominieren beim Chat (Systemprompt + Case-Kontext +
Guidance + bis zu 10 History-Einträge, die das Frontend pro Request
mitschickt) — deshalb nie nur Completion-Tokens zählen.

### Kosten überschlagen (Rechenweg)

```
Kosten = prompt_tokens × P_in/1e6  +  completion_tokens × P_out/1e6
```

P_in/P_out = Preis pro 1 Mio Input-/Output-Tokens für das Modell in
`OPENROUTER_MODEL` (Default `anthropic/claude-sonnet-4.5`). **Preise sind
UNVERIFIZIERT und volatil** — immer aktuell auf openrouter.ai/models
nachschlagen, nie aus Gedächtnis oder alten Reports übernehmen.

Illustratives Beispiel (Token-Zahlen fiktiv, Rechenweg das Eigentliche):
Angenommen die Log-Aggregation ergibt für einen Chat-Turn im Mittel
2 100 prompt- und 300 completion-Tokens, und P_in=3 USD, P_out=15 USD
pro 1M (Platzhalter!):

```
0.0021M × 3 + 0.0003M × 15 = 0.0063 + 0.0045 ≈ 0.011 USD pro Chat-Turn
```

Skalierung dann: Turns/Studierende × Studierendenzahl. Die
Modell-Antwort auf "was kostet der Rollout?" ist also immer:
(1) Logs aggregieren, (2) aktuelle Preise nachschlagen, (3) Rechenweg
zeigen — nie eine nackte Zahl.

---

## Methode 4 — Guardrail-Regressionsmethode

**Zweck:** Vor jeder Prompt-Änderung (Agent-Prompts, Case-Guidance)
prüfen, ob die neuen Outputs die Guardrails reißen — BEVOR Studierende
generische Fallback-Texte statt Antworten sehen.

### Wie der Guardrail funktioniert (verifiziert, Stand: 2026-07-08)

`guardrail_check(text, tp)` in `backend/agents/orchestrator.py`
(Zeilen 113–132) prüft der Reihe nach und gibt `(ok, reason)` zurück:

1. TP-spezifische `forbidden_framework_names` aus
   `TP_CONFIGS[tp]` (`backend/config/tp_configs.py`)
2. `FORBIDDEN_PATTERNS` (direkte-Antwort-Floskeln + harte
   Framework-Namen: porter, five forces, rbv, vrio, …)
3. `SLANG_PATTERNS`
4. Emoji (jedes Zeichen der Unicode-Kategorie "So")
5. `RECOMMENDATION_PATTERNS` + 7 Regexe (direkte Empfehlungen wie
   "ich empfehle", "tamara sollte …")
6. `CASE_SPECULATION_PATTERNS` (finma, azure switzerland, microsoft, …)

Bei Treffer wird die Agent-Antwort KOMPLETT durch einen festen
Fallback-Text ersetzt (`_guardrail_fallback`, je Agent-Typ, DE/EN) und
als `guardrail_triggered` (warning, mit `reason` und `agent`) geloggt.
Ein hoher Anteil getriggerter Antworten ist also direkt spürbare
UX-Verschlechterung — genau das misst diese Methode.

**Bekannte Lücke (verifiziert per Aufruf):** `TP_CONFIGS[4]` hat KEINEN
`forbidden_framework_names`-Key. In TP4 greifen nur die globalen
Patterns; z. B. wird `"Der Marketing-Mix hilft."` in TP2 UND TP3
blockiert (`framework_name_dropped: Marketing-Mix`), passiert TP4 aber
ungefiltert. Achtung bei der Wortwahl der Verbotslisten:
`"Die Transaktionskosten sind hier relevant."` wird NUR in TP2 geblockt —
TP3 verbietet nur `"Transaktionskostentheorie"`/`"TCE"`, nicht das bloße
Wort "Transaktionskosten", der Satz passiert also auch TP3 (und TP4)
ungefiltert. Bei TP4-Arbeiten einkalkulieren (Fix wäre eine
Judge-/Verhaltensänderung → `toadapt-change-control`).

### Rezept

```bash
# 1. Bestehende Regressionstests laufen lassen (Keim-Sammlung: 3 Tests)
.venv/bin/python -m pytest tests/test_orchestrator_guardrails.py -q

# 2. Kandidaten-Outputs der geänderten Prompts stichprobenartig prüfen
#    (Texte aus einem Smoke-Lauf oder handgeschrieben Grenzfälle):
.venv/bin/python -c "
from backend.agents.orchestrator import guardrail_check
samples = [
    ('Welche Faktoren sprechen fuer eine interne Loesung?', 2),
    ('Ich empfehle den Website-Chatbot.', 2),
]
for text, tp in samples:
    print(guardrail_check(text, tp), '|', text[:60])
"
```

3. Für jeden neu entdeckten Failure-Mode einen Testfall in
   `tests/test_orchestrator_guardrails.py` ergänzen (Muster: Text +
   TP rein, `ok is False` + erwarteter `reason`-String raus; Konventionen
   siehe `toadapt-validation-and-qa`). Die Sammlung soll mit jeder
   Prompt-Iteration wachsen — sie ist das institutionelle Gedächtnis
   der Guardrail-Kämpfe.

4. Nach Deploy: `guardrail_triggered`-Rate in den Logs vorher/nachher
   vergleichen (gleiche Aggregationstechnik wie Methode 3, Suchstring
   `guardrail_triggered`).

**Grenze der Methode:** Die Pattern-Listen sind substring-/regex-basiert
und fangen nur BEKANNTE Formulierungen. Ein grüner Regressionslauf
beweist "keine bekannte Verletzung", nicht "kein Answer-Giving". Für
letzteres braucht es Stichproben-Lektüre echter Transkripte (Methode 6).

---

## Methode 5 — Hypothese → Vorhersage → Messung (Schablone)

Regel des Projekts: **Eine Hypothese sagt Zahlen voraus, bevor gemessen
wird.** Sonst ist jedes Ergebnis nachträglich "erklärbar". Ausfüllbare
Schablone:

```markdown
## Hypothese <kurzname>            (Datum, Autor:in)
BEOBACHTUNG   Was ist der belegte Ist-Zustand? (Zahl + Quelle)
HYPOTHESE     Welcher Mechanismus erklärt die Beobachtung?
INTERVENTION  Welche EINE Änderung wird gemacht?
VORHERSAGE    Welche Metriken bewegen sich wohin? (Zahlen! inkl.
              Nebenwirkungs-Grenzen: was darf sich NICHT verschlechtern)
MESSUNG       Welches Kommando/Pipeline erzeugt die Zahlen?
ENTSCHEIDUNG  Vorab fixiert: bei welchem Ergebnis wird angenommen /
              verworfen / weiter untersucht?
STATUS        offen | bestätigt | falsifiziert | unentscheidbar (n zu klein)
```

### Durchgerechnetes Beispiel: das q4-Problem

```markdown
## Hypothese q4-anker-zu-hart      (illustrativ, Status: offen/Kandidat)
BEOBACHTUNG   q4 (Bloom 6, 30 Pkt): MAE 4.969, Mean Diff −4.969 (n=16),
              Unterbewertung — docs/teacher_alignment_report_20260531….md
HYPOTHESE     Die q4-Kalibrierungsanker (calibration_notes im Golden-Case-JSON,
              _format_calibration_notes) bestrafen fehlende
              Integrations-Explizitheit härter als die Lehrkraft, die
              implizite Integration honoriert.
INTERVENTION  Nur den dritten q4-Anker ("Revision muss Konsequenzen…")
              abschwächen; q1–q3-Anker unverändert.
VORHERSAGE    q4 Mean Diff von −4.97 auf > −2.5; q4 MAE < 4.0;
              Nebenwirkungsgrenzen: q1–q3 MAE ändert sich um < ±0.5,
              Gesamt-r fällt nicht unter 0.75.
MESSUNG       Judge-Rescore derselben 64 Zeilen, dann
              scripts/compare_teacher_rubric_scores.py; Blatt by_question.
ENTSCHEIDUNG  Alle Vorhersage-Bänder getroffen → Kandidat für Deploy
              (Gate: toadapt-change-control, Alignment-Recheck-Pflicht).
              q4 besser, aber q1–q3 verletzt → verworfen.
              Bewegung < halbes Band → unentscheidbar bei n=16;
              neue Blind-Batch nötig.
```

Die tatsächliche, ausgearbeitete Kampagne zu q4 lebt in
`toadapt-judge-alignment-campaign` — dieses Beispiel zeigt nur die Form.

---

## Methode 6 — Wann welche Methode NICHT reicht

| Behauptung | Unzureichender Beleg | Was wirklich nötig ist |
|---|---|---|
| "Der Judge bewertet korrekt" | hohes Pearson r | r + MAE + Mean Diff zusammen; der 2026-05-31-Befund (r rauf, Bias runter) ist der hauseigene Gegenbeweis |
| "Die Kalibrierung hat das Alignment verbessert" | Vorher/Nachher auf denselben 64 Zeilen | Das ist **in-sample**: die Kalibrierungsanker wurden aus genau dieser Studie abgeleitet und auf denselben Daten evaluiert. Beweis erfordert eine NEUE Blind-Batch (out-of-sample) |
| "q4 ist jetzt besser" | Δr oder ΔMAE bei n=16 | Vorab definierte Bänder (Methode 5) + CI-Ehrlichkeit; ggf. mehr Daten. Bei n=16 überlappen die r-CIs fast immer |
| "Kein Answer-Giving mehr" | grüne Guardrail-Regressionstests | Pattern-Listen fangen nur Bekanntes; zusätzlich Stichproben-Lektüre echter Chat-Transkripte (Chat-Turns-Workbook aus Methode 1) |
| "Der Rollout kostet X" | Preis × geschätzte Tokens aus dem Kopf | Log-Aggregation (Methode 3) + tagesaktuelle OpenRouter-Preise + offener Rechenweg |
| "Frage A ist schwerer als Frage B" | within_2pt-Vergleich | Punkte-Bänder sind bei ungleichen max_points (25 vs. 30) nicht vergleichbar → Prozentpunkt-Bänder (within_10pctpts) oder pct-Spalten nutzen |
| "Der Judge ist unsicher, wo er falsch liegt" | needs_human_review-Flags zählen | Flags gegen tatsächliche |diff|-Werte kreuzen (item_comparison-Blatt); Flag-Präzision ist selbst eine offene Messfrage |

Generalregel: Korrelation beweist keine Punktegenauigkeit, ein grüner
Test beweist kein Verhalten außerhalb seiner Patterns, und eine
in-sample-Verbesserung beweist keine Generalisierung. Für jede dieser
Lücken hat dieses Toolkit die passende nächste Methode.

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle Codeverweise, Kommandos und Zahlen am
2026-07-08 gegen das Repo verifiziert (Guardrail-Beispiele und
Log-Aggregation tatsächlich ausgeführt; CI-Zahlen aus den Reportwerten
nachgerechnet). OpenRouter-Preise wurden bewusst NICHT genannt (volatil).

Re-Verifikation drift-anfälliger Fakten:

| Fakt | Kommando |
|---|---|
| review_item_id-Format `{case}:{q}:{nnn}` | `grep -n 'review_item_id = f' scripts/export_review_workbooks.py` |
| Lehrer-Workbook kanonisch / rubric_only-Ausschluss | `grep -n 'rubric_only_ids_excluded_by_design' scripts/compare_teacher_rubric_scores.py` |
| Studien-Scope 64 Zeilen / 16 Submissions | `grep -n 'Submissions im Scope' docs/teacher_alignment_report_20260531_17submissions.md` |
| Token-Logging-Event | `grep -n 'llm_call_completed' backend/llm.py` |
| Default-Modell | `grep -n 'DEFAULT_OPENROUTER_MODEL' backend/llm.py` |
| Chat-max_tokens 220/320 | `grep -n 'max_tokens=220' backend/agents/orchestrator.py` |
| Judge-max_tokens 1200 | `grep -n 'EVALUATOR_MAX_TOKENS' backend/evaluator/rubric_evaluator.py` |
| Guardrail-Reihenfolge/Patterns | `sed -n '113,132p' backend/agents/orchestrator.py` |
| TP4 ohne forbidden_framework_names | `grep -n 'forbidden_framework_names' backend/config/tp_configs.py` (3 Treffer = Lücke besteht) |
| Kalibrierungsanker zweistufig | `grep -n 'calibration_notes\|BLOOM_CALIBRATION_ANCHORS' backend/evaluator/rubric_evaluator.py backend/cases/pool/alpes-bank-genai-001.json \| head` |
| Guardrail-Regressionstests | `.venv/bin/python -m pytest tests/test_orchestrator_guardrails.py -q` |
| Golden-Case-Punkte (q4 = 30, Bloom 6) | `python3 -c "import json; print([(q['question_id'],q['bloom_level'],q['max_points']) for q in json.load(open('backend/cases/pool/alpes-bank-genai-001.json'))['questions']])"` |

Update 2026-07-09 (HEAD 64b62f9): Kalibrierungsanker auf das zweistufige Modell umgestellt (Case-Anker vor Bloom-Generik), Re-Verifikations-Kommandos an die restrukturierte rubric_evaluator.py angepasst.
