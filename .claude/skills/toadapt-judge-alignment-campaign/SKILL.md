---
name: toadapt-judge-alignment-campaign
description: Executable Kampagne für das härteste lebende Problem in ToAdapt — der LLM-Judge unterbewertet q4 (Bloom 6, Integration/Reflexion, 30 Punkte) systematisch (q4-MAE ~4.97, 16/16 Fälle unterbewertet, Stand Studie 2026-05-31). Lade diese Skill, wenn du (a) die Judge-Teacher-Alignment-Metriken reproduzieren, verbessern oder erneut messen willst, (b) an backend/evaluator/rubric_evaluator.py (EVALUATE_PROMPT, EVALUATOR_SYSTEM, Kalibrierungsanker), backend/config/rubrics/tp4_rubric.json oder OPENROUTER_MODEL wegen Bewertungsqualität arbeitest, (c) Symptome wie "Judge ist strenger als die Lehrkraft", "q4-Scores zu niedrig", "Pearson/MAE/RMSE nachrechnen", "Blind-Review auswerten" oder "neue Kalibrierungsrunde" hast, oder (d) scripts/export_review_workbooks.py bzw. scripts/compare_teacher_rubric_scores.py bedienen willst. Keywords: LLM-as-Judge, Alignment, Kalibrierung, teacher_awarded_points, review_item_id, q4, Bloom 6, MAE, Pearson, Blind-Review, Rescore.
---

# Judge-Alignment-Kampagne: q4/Bloom-6-Unterbewertung beheben

Stand aller Zahlen und Pfade: 2026-07-08.

## Wann diese Skill NICHT gilt

| Dein Anliegen | Richtige Skill |
|---|---|
| Judge liefert 0 Punkte mit `technical_fallback` / JSON-Parse-Fehler | `toadapt-debugging-playbook` |
| Was zählt als Evidenz, Test-Landkarte, CI-Gates | `toadapt-validation-and-qa` |
| Blind-Review-Protokoll im Detail, Analysemethodik mit Rechenbeispiel | `toadapt-proof-and-analysis-toolkit` |
| Was bedeutet Bloom 6 / q4 / Canvas-Scoring fachlich? | `bwl-scaffolding-reference` |
| Darf ich das ändern? Gates vor Deploy? | `toadapt-change-control` (Judge-Änderungen = Klasse [B]) |
| Warum sieht rubric_evaluator.py historisch so aus (12 Commits Churn)? | `toadapt-failure-archaeology` |
| venv/Env aufsetzen, damit die Skripte überhaupt laufen | `toadapt-build-and-env` |

Diese Skill ist der Feldzug-Plan für GENAU EIN Problem: den q4-Bias des Judges messbar beheben, ohne q1–q3 zu verschlechtern.

---

## 0. Kontext: Das Problem und die Studie vom 2026-05-31

Begriffe (einmalig definiert, danach vorausgesetzt):

| Begriff | Bedeutung |
|---|---|
| **LLM-Judge** | Der Rubric-Evaluator (`backend/evaluator/rubric_evaluator.py`): ein LLM-Call pro Frage, der Studierenden-Freitextantworten Punkte, Feedback und Review-Flags zuweist. |
| **q4** | Die vierte Frage jedes Cases: Integrations-/Reflexionsfrage ("Welche Entscheidung ist die riskanteste, was folgt aus einer Revision?"), Bloom-Stufe 6 (höchste Denkstufe: Synthese/Bewerten), 30 Punkte — die schwerste Frage mit dem höchsten Gewicht. |
| **MAE** | Mean Absolute Error: mittlerer Betrag der Punktdifferenz Judge minus Lehrkraft. Kleiner = besser. |
| **Pearson r** | Rangähnliche Korrelation der Punktvergabe Judge vs. Lehrkraft. Hoch = Judge sortiert Antworten in derselben Reihenfolge wie die Lehrkraft, auch wenn das Niveau abweicht. |
| **Blind-Review** | Die Lehrkraft bewertet Antworten in einem Excel-Workbook, das KEINE Judge-Scores enthält (Spalten `teacher_awarded_points`, `teacher_rationale` leer zum Ausfüllen). |
| **review_item_id** | Join-Schlüssel zwischen Lehrer- und Judge-Workbook, Format `{case_id}:{question_id}:{nnn}` (dreistellig laufend), erzeugt in `scripts/export_review_workbooks.py` (Zeile 178). |
| **Kalibrierungsanker** | Hartkodierte Bewertungshinweise pro Frage-ID (q1–q4) im Judge-Prompt, abgeleitet aus der Lehrerbewertung: `_format_calibration_notes` in `backend/evaluator/rubric_evaluator.py` (Zeilen 155–181). |

### Die Studie (docs/teacher_alignment_report_20260531_17submissions.md)

Achtung: der Dateiname sagt "17submissions", der Scope im Report sind **16 Submissions / 64 Frage-Zeilen** (nur vollständige Abgaben mit q1–q4 in der Lehrerbewertung). Protokoll: Blind-Review-Workbook, Join über `review_item_id`, Lehrer-Workbook ist kanonisch (Judge-Zeilen ohne Lehrer-Match werden by design ausgeschlossen, damit bereinigte Testuser nicht zurückkommen).

Gesamtergebnis vor → nach Kalibrierung (aus dem Report, 64 Items):

| Metrik | Vor | Nach |
|---|---:|---:|
| Pearson r | 0.631 | **0.796** |
| MAE (Punkte) | 2.984 | **2.711** |
| RMSE (Punkte) | 4.626 | 3.897 |
| Mean Diff (Judge − Lehrkraft) | −0.234 | **−2.07** |
| Lehrkraft höher (n) | 28 | **48** |

Lesart: Die Kalibrierung hat die **Rangordnung** deutlich verbessert (r 0.63→0.80), aber den Judge insgesamt **systematisch strenger** gemacht (unterbewertet in 48 von 64 Fällen).

Pro Frage (nach Kalibrierung, Report):

| Frage | n | MAE nach | Mean Diff nach | Pearson nach |
|---|---:|---:|---:|---:|
| q1 | 16 | 2.188 | −1.5 | 0.918 |
| q2 | 16 | 2.5 | −0.938 | 0.745 |
| q3 | 16 | 1.188 | −0.875 | 0.843 |
| **q4** | **16** | **4.969** | **−4.969** | 0.79 |

**q4 ist die Schwachstelle:** MAE ~5 von 30 Punkten, in **allen 16 Fällen** unterbewertet (rubric_higher_n = 0, within_1pt_n = 0; verifiziert im by_question-Blatt der Vergleichsdatei). Lehrer-Mittel 18.47, Judge-Mittel 13.5.

**n=16-Vorbehalt (ehrlich):** 16 Datenpunkte pro Frage sind wenig. Pearson-Konfidenzintervalle sind breit, MAE-Unterschiede unter ~1 Punkt sind nicht belastbar. Alle Erfolgskriterien unten sind notwendige, keine hinreichenden Bedingungen — die finale Aussage braucht eine neue Blind-Runde.

---

## 1. Datenlage und Voraussetzungen

**PII-Regel (unverhandelbar):** Die echten Teilnehmerdaten (Prolific-Antworten, PIDs) liegen seit 2026-07-08 in `~/ToAdapt_sensitive_data/` und sind aus dem Repo entfernt (git filter-repo). NIEMALS nach `data/` oder sonstwohin ins Repo zurückkopieren, niemals committen, niemals in Tests/Fixtures/Skills einbetten. Details: `toadapt-change-control`.

Ablageorte (Stand 2026-07-08, alle verifiziert vorhanden):

| Artefakt | Pfad |
|---|---|
| Rescorte Submission-States (Basis der Studie) | `~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/submission_states_aligned_20260531T140830Z.json` |
| Judge-Workbook der Studie (rubric) | `~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/aligned_review_20260531T140830Z_20260531T142056Z_rubric.xlsx` |
| Vergleichsdatei der Studie (5 Blätter) | `~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/teacher_rubric_comparison_aligned_20260531T140830Z.xlsx` + gleichnamige `_item_comparison.csv` |
| Experiment-Events (für chat_turns-Export) | `~/ToAdapt_sensitive_data/data/experiment_events.json` |
| Ausgefülltes Lehrer-Workbook | `~/Desktop/prolific_review_20260517T120141Z_blind.xlsx` (Stand 2026-07-08; sollte nach `~/ToAdapt_sensitive_data/` umziehen — kanonisch findest du den Pfad immer in der `summary`-Zeile `teacher_file` der Vergleichsdatei) |
| Zusatz-Diagnostik | `judge_uncertain_reviews_20260531_16submissions.xlsx`, `teacher_judge_confusion_*` (PNG/CSV) im selben `aligned_rescores/`-Ordner |

Umgebung: Repo-Root `cd` voraussetzen, venv unter `.venv/` (siehe `toadapt-build-and-env`). Skripte, die `backend.*` importieren (z. B. Rescore), brauchen `PYTHONPATH=.` — sonst `ModuleNotFoundError: No module named 'backend'`. LLM-Calls (nur beim Rescore, Phase 3) brauchen `OPENROUTER_API_KEY` in der Env und kosten Geld (Modell: `OPENROUTER_MODEL`, Default `anthropic/claude-sonnet-4.5`, `backend/llm.py` Zeile 22).

---

## 2. Phase 1 — Baseline-Reproduktion

Ziel: Beweise, dass du die Studien-Zahlen aus den Rohartefakten reproduzieren kannst, BEVOR du irgendetwas änderst. Führe aus (ein Kommando, keine LLM-Calls, ~2 s):

```bash
.venv/bin/python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook ~/Desktop/prolific_review_20260517T120141Z_blind.xlsx \
  --rubric-workbook ~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/aligned_review_20260531T140830Z_20260531T142056Z_rubric.xlsx \
  --output-dir ~/ToAdapt_sensitive_data/data/prolific_runs/derived/baseline_repro \
  --prefix baseline_repro
```

Erwartete Artefakte: `baseline_repro.xlsx` (Blätter: `summary`, `by_question`, `item_comparison`, `outliers` [Top 20 nach |Diff|], `validation`) und `baseline_repro_item_comparison.csv` (Semikolon-getrennt).

**GATE (muss exakt stimmen — am 2026-07-08 verifiziert reproduziert):**

| Prüfung | Sollwert |
|---|---|
| `summary`: n | 67 |
| `summary`: mae_points / rmse_points / pearson_r | 2.784 / 3.921 / 0.777 |
| `summary`: mean_diff_rubric_minus_teacher / teacher_higher_n | −1.784 / 48 |
| `by_question` q4: n / mae / diff / pearson | 16 / 4.969 / −4.969 / 0.79 |
| `by_question` q2, q3 | 16 / 2.5 / −0.938 / 0.745 bzw. 16 / 1.188 / −0.875 / 0.843 |

**Bekannte Scope-Differenz (kein Fehler):** Das Skript rechnet über alle 67 gematchten Lehrer-Zeilen; der Report nutzt einen engeren 64er-Scope (nur Submissions mit allen vier Fragen — q1 hat roh n=19 statt 16). Die q2/q3/q4-Zeilen stimmen exakt mit dem Report überein; Gesamt-MAE 2.784 (67er) vs. 2.711 (64er) und q1 2.526 vs. 2.188 unterscheiden sich nur durch diesen Filter. Der Filtermechanismus des Reports liegt NICHT als Skript im Repo (UNVERIFIZIERT, vermutlich ad-hoc) — nimm für die Kampagne die 67er-Skript-Ausgabe als operative Baseline und q4 (deckungsgleich in beiden Scopes) als Zielmetrik.

Wenn das GATE nicht stimmt: NICHT weitermachen, erst Pipeline debuggen (`toadapt-debugging-playbook`; typische Ursachen: falsches Workbook-Paar, verschobene Dateien, verändertes Lehrer-Workbook).

---

## 3. Phase 2 — Diagnose: q4-Fehler kategorisieren

Datenquellen: `outliers`- und `item_comparison`-Blatt der Vergleichsdatei bzw. die CSV. Relevante Spalten: `teacher_awarded_points`, `rubric_awarded_points`, `diff_points_rubric_minus_teacher`, `rubric_score_band`, `rubric_judge_confidence`, `rubric_needs_human_review`, `rubric_missing_canvas_blocks`, `teacher_rationale`, `rubric_feedback`, `answer_text`.

**Regel: Jede Hypothese muss VOR der Auswertung Zahlen vorhersagen** (Methodik: `toadapt-proof-and-analysis-toolkit`). Die vier Kandidaten-Hypothesen:

| # | Hypothese | Vorhersage (falsifizierbar) |
|---|---|---|
| H1 | q4-Kalibrierungsanker zu streng (konstanter Offset) | Diff ≈ konstant über Teacher-Qualitätsbänder; r bleibt hoch |
| H2 | Integrationsblindheit: Judge honoriert Integrations-/Kaskadenlogik nicht | Diff wächst mit teacher_score (beste Antworten am stärksten unterbewertet) |
| H3 | 30-Punkte-Skala zu grob geankert (nur 30 / 16.5 / 7.5 / 0 im Prompt) | rubric_awarded_points clustern an wenigen Ankerwerten; within_1pt = 0 |
| H4 | Canvas-Blöcke für TP4 unpassend (4 Pflicht-Blöcke erzwingen Silo-Abarbeitung statt Integration) | häufige `missing_canvas_blocks` TROTZ hoher Teacher-Scores; Canvas-Alignment korreliert schwach mit teacher_score |

Auswertungs-Snippet (getestet gegen die Baseline-CSV):

```bash
.venv/bin/python - <<'EOF'
import csv
from statistics import mean
from collections import Counter
path = "/Users/dianakozachek/ToAdapt_sensitive_data/data/prolific_runs/derived/baseline_repro/baseline_repro_item_comparison.csv"
rows = [r for r in csv.DictReader(open(path, encoding="utf-8"), delimiter=";")
        if r["question_id"] == "q4" and r["teacher_awarded_points"] and r["rubric_awarded_points"]]
bands = {"niedrig (<15)": [], "mittel (15-20)": [], "hoch (>20)": []}
for r in rows:
    t = float(r["teacher_awarded_points"]); d = float(r["diff_points_rubric_minus_teacher"])
    key = "niedrig (<15)" if t < 15 else ("mittel (15-20)" if t <= 20 else "hoch (>20)")
    bands[key].append(d)
for k, v in bands.items():
    print(f"{k}: n={len(v)}, mean_diff={round(mean(v),2) if v else '-'}")
print("Punkteverteilung Judge:", sorted(Counter(float(r["rubric_awarded_points"]) for r in rows).items()))
print("score_band:", Counter(r["rubric_score_band"] for r in rows))
EOF
```

Befund auf der Baseline (2026-07-08 gerechnet, n=16):

```
niedrig (<15):  n=4, mean_diff=-1.88
mittel (15-20): n=5, mean_diff=-7.9
hoch (>20):     n=7, mean_diff=-4.64
Punkteverteilung Judge: 0.0×1, 8.5–14.5×9, 18.0×4, 20.0×1, 24.0×1
score_band: partial=9, low=4, solid=1, strong=1, unscored=1
```

Lesart (Stand 2026-07-08): Der Diff ist NICHT konstant → H1 allein erklärt es nicht. Die stärkste Unterbewertung liegt im mittleren/oberen Band → konsistent mit H2 (Integrationsleistung wird nicht honoriert) und H3 (der Judge vergibt fast nie >20; 9 von 16 landen im Band "partial"). H4 gegen `rubric_missing_canvas_blocks` und `teacher_rationale` qualitativ prüfen (Antworttexte NUR lokal lesen, nie zitieren/committen). Kategorisiere jeden der 16 q4-Fälle einer Haupthypothese zu, bevor du eine Lösung wählst.

---

## 4. Phase 3 — Lösungsmenü (gerankt)

**Theorie-Obligation:** Vor jedem Eingriff schriftlich festhalten: welche Hypothese er adressiert und welche Metrikbewegung er vorhersagt (z. B. "q4-Diff von −4.97 auf > −2.5, q1–q3-MAE ±0.3"). Ohne Vorhersage kein Rescore. Jede Option ist Change-Control **Klasse [B]** (`toadapt-change-control`).

| Rang | Option | Ort | Adressiert | Aufwand | Risiko |
|---|---|---|---|---|---|
| a | q4-Kalibrierungsanker verfeinern | `backend/evaluator/rubric_evaluator.py`, `_format_calibration_notes`, q4-Einträge Zeilen 172–176 | H1, H2 | klein | gering; nur q4 betroffen |
| b | `tp4_rubric.json` überarbeiten (evaluation_focus, Canvas-Erwartungen) | `backend/config/rubrics/tp4_rubric.json` | H4 | klein–mittel | Canvas-Scoring-Verschiebung; Exemplar-Schwellen (82/75) mitdenken |
| c | Score-Band-Anker für 30-Punkte-Fragen im Prompt | `backend/evaluator/rubric_evaluator.py`, EVALUATE_PROMPT "Vergabe-Leitlinien" Zeilen 104–111 (mid=0.55×max, low=0.25×max aus Zeilen 295–296 → für q4 nur 30/16.5/7.5/0) | H3 | mittel | wirkt auf ALLE Fragen → q1–q3-Recheck Pflicht |
| d | Few-Shot-Exemplar (geankertes q4-Beispiel im Prompt) | EVALUATE_PROMPT-Erweiterung | H2, H3 | mittel | **Kontamination:** NIE ein Item aus dem 16er-Eval-Set; nur synthetisches/neu verfasstes Beispiel. Token-Kosten steigen. Keine Musterlösung darf ins studierendensichtbare Feedback durchsickern |
| e | Modellwechsel via `OPENROUTER_MODEL` | Env-Variable, `backend/llm.py` Zeile 22 | alle (Schrotflinte) | Test billig | **invalidiert die GESAMTE Kalibrierung** (q1–q4) → volle Neubewertung und ggf. neue Anker nötig |
| f | Zweistufiger Judge für Bloom 6 (Pass 1: Integrations-/Kaskadenanalyse, Pass 2: Punktvergabe) | neuer Code-Pfad im Evaluator | H2 | groß | Kandidat, UNBEWIESEN; doppelte Kosten/Latenz; nur angehen, wenn a–c nachweislich nicht reichen |

Hinweise zu (b), am 2026-07-08 im File verifiziert: `tp4_rubric.json` verlangt vier Pflicht-Blöcke (value_propositions, key_activities, key_resources, cost_structure); die `expectation`-Texte sind Alpes-Bank-spezifisch formuliert ("…der Bank") — bei neuen Cases prüfen; in den `accepted_keywords` von cost_structure steht der Tippfehler `"risko"` neben `"risiko"`.

### Die Rescore-Lücke (Vorarbeit für JEDE Option)

Es gibt derzeit **kein Bulk-Rescore-Skript** im Repo. `scripts/retry_technical_fallback_scores.py` bewertet nur `technical_fallback`-Zeilen neu, enthält aber das komplette Muster zum Kopieren: Antworten aus einer `*_item_comparison.csv` laden (Spalten `submission_id`, `question_id`, `answer_text`; Semikolon-Delimiter), `Submission` rekonstruieren, `case_manager.get(case_id)`, dann `await RubricEvaluator(get_openrouter_key()).evaluate_question(submission=…, case=…, question_id=…, answer_text=…)`. Achtung: sein `DEFAULT_COMPARISON_CSV` zeigt auf den alten Repo-Pfad `data/prolific_runs/…`, der leer ist — immer `--comparison-csv` explizit auf die Datei unter `~/ToAdapt_sensitive_data/` setzen. Aufruf-Muster:

```bash
PYTHONPATH=. OPENROUTER_API_KEY=… .venv/bin/python scripts/retry_technical_fallback_scores.py \
  --comparison-csv ~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/teacher_rubric_comparison_aligned_20260531T140830Z_item_comparison.csv \
  --dry-run
```

Schreibe für die Kampagne einen abgeleiteten Bulk-Rescore-Treiber (z. B. `scripts/rescore_submissions.py`), der ALLE q4-Antworten (bzw. alle Fragen bei Option c/e) neu bewertet und einen neuen Submission-States-JSON **nach `~/ToAdapt_sensitive_data/`** schreibt (nie ins Repo). Kosten: 64 Antworten = 64 LLM-Calls (+ evtl. Repair-Calls), max_tokens 1200 pro Call.

Iterations-Loop pro Kandidat (Entwicklungssignal, KEIN Erfolgsnachweis — siehe Abschnitt 5):

```bash
# 1. Änderung auf Branch, Vorhersage notiert
# 2. Rescore → neuer States-JSON (s. o.)
# 3. Workbooks erzeugen:
.venv/bin/python scripts/export_review_workbooks.py \
  --submissions ~/ToAdapt_sensitive_data/data/prolific_runs/derived/candidate_X/submission_states_candidate_X.json \
  --events ~/ToAdapt_sensitive_data/data/experiment_events.json \
  --output-dir ~/ToAdapt_sensitive_data/data/prolific_runs/derived/candidate_X \
  --prefix candidate_X
# 4. Gegen das ALTE Lehrer-Workbook vergleichen:
.venv/bin/python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook ~/Desktop/prolific_review_20260517T120141Z_blind.xlsx \
  --rubric-workbook ~/ToAdapt_sensitive_data/data/prolific_runs/derived/candidate_X/candidate_X_<TS>_rubric.xlsx \
  --output-dir ~/ToAdapt_sensitive_data/data/prolific_runs/derived/candidate_X \
  --prefix candidate_X_comparison
# 5. summary + by_question gegen Vorhersage und Baseline halten
```

(UNVERIFIZIERT, weil ohne LLM-Call nicht testbar: dass `export_review_workbooks.py` einen von deinem neuen Treiber erzeugten States-JSON ohne Anpassung frisst — das Format von `submission_states_aligned_20260531T140830Z.json` als Vorlage nehmen.)

---

## 5. Falsche Wege (eingezäunt — nicht betreten)

1. **Auf dem Eval-Set tunen und auf dem Eval-Set Erfolg verkünden.** Die aktuellen Kalibrierungsanker wurden AUS diesen 16 Submissions abgeleitet — das Set ist für Anker-Tuning verbraucht. Iterationen darauf sind nur Entwicklungssignal; jede Erfolgsaussage braucht eine neue Blind-Runde oder ein Held-out-Set.
2. **Nach Augenschein urteilen** ("das Feedback liest sich jetzt fairer"). Nur die Pipeline-Metriken zählen.
3. **`needs_human_review` lockern, um weniger Flags zu bekommen.** Die Flags (43 von 64 in der Studie) sind Feature, nicht Bug: der Judge soll die Lehrkraft unterstützen, nicht ersetzen. Insbesondere `judge_confidence == "low"` erzwingt das Flag hart (rubric_evaluator.py Zeilen 352–354) — stehen lassen.
4. **Judge-Prompt ändern und ohne Recheck deployen.** Doktrin-Regel des Projekts und Change-Control-Gate Klasse [B]: jede Änderung an EVALUATOR_SYSTEM / EVALUATE_PROMPT / Ankern / Rubrics erfordert den Vergleichs-Durchlauf gegen Teacher-Scores VOR produktivem Einsatz.
5. **Eval-Daten ins Repo holen** ("nur kurz als Fixture"). Siehe PII-Regel, Abschnitt 1.

---

## 6. Phase 4 — Validierung & Promotion

**Erfolgskriterien (messbar, vorab fixiert — alle drei müssen gelten):**

1. q4-MAE **< 3.0** (Baseline 4.969), UND
2. Gesamt-Pearson r **≥ 0.78** (67er-Baseline 0.777), UND
3. q1–q3-MAE verschlechtern sich jeweils um **< 0.3** gegenüber der Baseline (q1 2.526 / q2 2.5 / q3 1.188 im 67er-Scope).

**Validierung = neue Blind-Runde** (Protokoll im Detail: `toadapt-proof-and-analysis-toolkit`; Kurzform):

1. Neue vollständige Submissions sammeln (Ziel ≥ 16, sonst ist die Aussagekraft schlechter als die Baseline).
2. `scripts/export_review_workbooks.py` auf die neuen Submissions → `*_blind.xlsx` (enthält keine Judge-Scores, keine user_id; Lehrkraft füllt `teacher_awarded_points` + `teacher_rationale`).
3. Lehrkraft bewertet blind — sie darf das Judge-Workbook nicht sehen.
4. `scripts/compare_teacher_rubric_scores.py` auf das ausgefüllte Lehrer-Workbook + das `*_rubric.xlsx` desselben Exports.
5. Kriterien 1–3 gegen `summary`/`by_question` prüfen.

**Promotion (Kriterien erfüllt):** Change-Control Klasse [B] durchlaufen (`toadapt-change-control`), Report als `docs/teacher_alignment_report_<YYYYMMDD>_<n>submissions.md` ablegen (Namenskonvention: `toadapt-docs-and-writing`), Baseline-Zahlen in dieser Skill aktualisieren (siehe Provenance), erst dann deployen.

**Retirement (Kriterien verfehlt):** Kandidat auf dem Branch einfrieren, Hypothese + Vorhersage + gemessene Zahlen + Verwerfungsgrund in `toadapt-failure-archaeology` nachtragen, damit niemand denselben Kandidaten erneut baut. Ein verfehlter Kandidat ist ein Ergebnis, kein Scheitern der Kampagne.

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle Zahlen gegen `docs/teacher_alignment_report_20260531_17submissions.md`, die Artefakte unter `~/ToAdapt_sensitive_data/` und einen tatsächlichen Reproduktionslauf des compare-Skripts verifiziert; Zeilenverweise gegen den Code am selben Tag.

Re-Verifikation drift-anfälliger Fakten (je ein Kommando):

| Fakt | Kommando |
|---|---|
| Kalibrierungsanker-Position (Zeilen 155–181 / q4 172–176) | `grep -n "_format_calibration_notes\|\"q4\": \[" backend/evaluator/rubric_evaluator.py` |
| Vergabe-Leitlinien / mid=0.55, low=0.25 | `grep -n "Vergabe-Leitlinien\|max_points \* 0.55\|max_points \* 0.25" backend/evaluator/rubric_evaluator.py` |
| low-Confidence erzwingt Review | `grep -n 'judge_confidence == "low"' backend/evaluator/rubric_evaluator.py` |
| Default-Modell | `grep -n "DEFAULT_OPENROUTER_MODEL" backend/llm.py` |
| tp4-Rubric-Inhalt (Blöcke, Schwellen 82/75, "risko"-Typo) | `grep -n "exemplar_threshold_pct\|score_floor_pct\|risko" backend/config/rubrics/tp4_rubric.json` |
| review_item_id-Format | `grep -n "review_item_id = f" scripts/export_review_workbooks.py` |
| Studien-Artefakte noch am Ablageort | `ls ~/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/` |
| Lehrer-Workbook-Pfad (kanonisch) | `.venv/bin/python -c "from openpyxl import load_workbook; ws=load_workbook('/Users/dianakozachek/ToAdapt_sensitive_data/data/prolific_runs/derived/aligned_rescores/teacher_rubric_comparison_aligned_20260531T140830Z.xlsx')['summary']; print(ws['B2'].value)"` |
| Kein Bulk-Rescore-Skript entstanden? | `ls scripts/ \| grep -i rescore` |
| Neuere Alignment-Reports? | `ls docs/ \| grep teacher_alignment_report` |
| Judge-Code seither geändert? | `git log --oneline -5 -- backend/evaluator/rubric_evaluator.py backend/config/rubrics/` |

Wenn eine neue Blind-Runde gelaufen ist: Baseline-Tabellen in Abschnitt 0/2 und die Erfolgskriterien in Abschnitt 6 auf die neue Referenz umstellen und den Stand-Stempel erneuern.
