---
name: toadapt-research-methodology
description: >
  Forschungs-Disziplin des ToAdapt-Projekts: Wie aus einer Ahnung ein akzeptiertes,
  publizierbares Ergebnis wird. Lade diese Skill, wenn du (a) eine Verbesserungs-Idee
  für Judge/Evaluator/Prompts/Scaffolding testen oder bewerten willst ("bringt X etwas?",
  "sollen wir Y ändern?"), (b) ein Experiment oder eine Messung planst (Hypothese,
  Metriken, Erfolgs-/Abbruchkriterien), (c) Ergebnisse berichten willst (Report,
  Paper-Abschnitt, Statusmeldung an die Ownerin) und wissen musst, welche Behauptungen
  zulässig sind und welche nicht, (d) fragst, ob eine Metrik-Verbesserung "echt" ist
  oder durch Auslassung lügt (Pearson r vs. Mean Diff), (e) Reproduzierbarkeit sichern
  musst (SHA-256-Manifeste, eingefrorene Scopes, Datenablage), oder (f) eine gescheiterte
  Idee sauber beerdigen willst. Keywords: Hypothese, Experiment, Evidenz, Evidenz-Bar,
  Alignment-Studie, Blind-Review, Pearson, MAE, Mean Diff, Kalibrierung, Publikation,
  Claim, Reproduzierbarkeit, Manifest, DSGVO, Prolific, Retirement, Sackgasse.
---

# ToAdapt Research-Methodology — von der Ahnung zum akzeptierten Ergebnis

## Wann diese Skill NICHT gilt

| Deine Frage | Richtige Skill |
|---|---|
| "Darf ich das überhaupt ändern? Welches Gate gilt?" | `toadapt-change-control` |
| "Wie rechne ich diese Analyse konkret durch (First-Principles-Methoden)?" | `toadapt-proof-and-analysis-toolkit` |
| "Welche offenen Forschungsfragen gibt es, wo fange ich an?" | `toadapt-research-frontier` |
| "Wie fixe ich konkret das q4/Bloom-6-Judge-Problem?" (executable Kampagne) | `toadapt-judge-alignment-campaign` |
| "Welche Tests/CI-Checks zählen als Evidenz für Code-Änderungen?" | `toadapt-validation-and-qa` |
| "Wie bediene ich die Forschungs-Skripte (import → export → compare)?" | `toadapt-run-and-operate` |
| "Wie benenne ich Reports und Pipeline-Artefakte?" | `toadapt-docs-and-writing` |
| "Was bedeutet Bloom / TP / Scaffolding / Canvas-Scoring?" | `bwl-scaffolding-reference` |

Diese Skill beantwortet: **Was zählt hier als Wissen, und wie erzeugt man es, ohne
sich selbst zu belügen?**

---

## Kontext in einem Absatz (für Zero-Context-Leser:innen)

ToAdapt ist ein Transfer-Trainer für BWL-Studierende (Universität St.Gallen):
Studierende beantworten Freitext-Fragen zu AI-generierten Business-Cases, ein
**LLM-Judge** (LLM-as-Judge = ein Sprachmodell, das Antworten nach einer Rubric
bewertet) vergibt Punkte, eine Lehrkraft sieht die Aggregate. Die zentrale
Forschungsfrage des Projekts ist deshalb immer eine Alignment-Frage: **Stimmen die
Judge-Scores mit menschlichen Lehrer-Scores überein — und unter welchen Bedingungen
nicht?** Die kanonische Referenzstudie liegt in
`docs/teacher_alignment_report_20260531_17submissions.md` (Achtung: Dateiname sagt
"17submissions", der tatsächliche eingefrorene Scope sind **16 Submissions / 64
Frage-Zeilen** — der Report selbst dokumentiert das korrekt).

---

## 1. Die Evidenz-Bar

**Regel 1: EIN Mechanismus muss ALLE Beobachtungen erklären — auch die negativen.**

Eine Erklärung, die nur die günstigen Datenpunkte abdeckt, ist keine Erklärung,
sondern Rosinenpickerei. Bevor du eine Behauptung als "gesichert" markierst, prüfe:
Gibt es eine Beobachtung im selben Datensatz, die der behauptete Mechanismus NICHT
erklärt? Dann ist entweder der Mechanismus falsch oder unvollständig.

**Das Lehrstück des Projekts (Stand: 2026-07-08, Quelle:
`docs/teacher_alignment_report_20260531_17submissions.md`):**

Die Kalibrierung des Judges (hartkodierte Kalibrierungsanker pro Frage, siehe
`_format_calibration_notes` in `backend/evaluator/rubric_evaluator.py`, Commit
`9a8077f` "human alignment with teacher scores") veränderte die Metriken so:

| Metrik | Vor Kalibrierung | Nach Kalibrierung | Lesart |
|---|---:|---:|---|
| Pearson r | 0.631 | 0.796 | **besser** (Rangordnung stimmt öfter) |
| MAE (Punkte) | 2.984 | 2.711 | leicht besser |
| RMSE (Punkte) | 4.626 | 3.897 | besser |
| Mean Diff (Judge − Teacher) | −0.234 | **−2.07** | **schlechter**: systematischer Bias |
| "Teacher höher" (n von 64) | 28 | **48** | Judge unterbewertet jetzt in 48/64 Fällen |

**Wer nur "Pearson r stieg von 0.63 auf 0.80" berichtet, lügt durch Auslassung.**
Die Kalibrierung machte den Judge korrelierter UND systematisch strenger. Beides
ist dasselbe Ergebnis; nur beides zusammen ist die Wahrheit. Konsequenz für jede
Messung in diesem Projekt:

- Berichte IMMER Korrelation (Pearson r) **und** Bias (Mean Diff) **und**
  Fehlergröße (MAE/RMSE) **und** die Verteilung (wer liegt öfter höher, n).
- Berichte IMMER pro Frage aufgeschlüsselt, nicht nur aggregiert: Der Aggregat-MAE
  von 2.711 versteckt, dass q4 (Bloom-6-Integrationsfrage, 30 Punkte) mit MAE ~4.97
  die Schwachstelle ist, während q1–q3 bei MAE 1.2–2.5 liegen.
- Das Vergleichs-Skript `scripts/compare_teacher_rubric_scores.py` liefert all das
  bereits (pearson_r, mae_points, rmse_points, mean/median diff, within_1pt/2pt/
  10pctpts, Per-Frage-Blätter). Nutze es. Erfinde keine eigene Metrik-Auswahl.

**Regel 2: Jede Behauptung bekommt einen zugewiesenen adversarialen
Widerlegungsversuch, BEVOR sie gilt.**

Prozedur (Solo-Projekt, also selbst durchführen, aber schriftlich):

1. Formuliere die Behauptung als einen Satz ("Änderung X verbessert Y").
2. Schreibe die stärkste dir bekannte Gegenerklärung auf ("Y stieg, weil sich
   gleichzeitig Z änderte / weil der Scope anders geschnitten ist / weil n zu
   klein ist / Regression zur Mitte").
3. Führe mindestens EINEN gezielten Check aus, der die Gegenerklärung bestätigen
   würde, wenn sie stimmt (z. B. gleiche Analyse auf identischem Scope, Blick auf
   die Metrik, die sich verschlechtert haben müsste).
4. Erst wenn der Check die Gegenerklärung NICHT bestätigt, darf die Behauptung in
   einen Report. Dokumentiere den Widerlegungsversuch im Report ("Geprüfte
   Alternativerklärungen: …").

---

## 2. Hypothese sagt Zahlen voraus — VOR dem Lauf

Eine Hypothese ohne vorhergesagte Zahl ist eine Meinung. Fülle dieses Template aus
und speichere es (z. B. als Notiz im Experiment-Branch oder im Report-Entwurf),
BEVOR du das Experiment startest — sonst passt du nachträglich die Erfolgskriterien
an das Ergebnis an (HARKing, "Hypothesizing After the Results are Known").

**Template:**

```markdown
## Hypothese <kurzer Name> — <Datum>

Behauptung (1 Satz):
Mechanismus (warum sollte das funktionieren?):
Datensatz + Scope (eingefroren, mit n):
Primärmetrik + vorhergesagter Wert/Bereich:
Nebenmetriken, die sich NICHT verschlechtern dürfen (Schwellen!):
Abbruchkriterium (wann gilt die Hypothese als widerlegt?):
Stärkste Alternativerklärung + geplanter Check dagegen:
Kosten des Laufs (LLM-Calls, Zeit):
```

**Ausgefülltes Beispiel** (nachgestellt an der realen Kalibrierungsstudie vom
2026-05-31 — so hätte das Blatt VOR dem Lauf aussehen müssen):

```markdown
## Hypothese kalibrierungsanker-v1 — 2026-05-31

Behauptung: Fragen-spezifische Kalibrierungsanker im Judge-Prompt erhöhen die
  Übereinstimmung mit Lehrer-Scores.
Mechanismus: Die Anker kodieren, was die Lehrkraft im Blind-Review tatsächlich
  bestraft/belohnt hat (z. B. "nur eine Herausforderung begrenzt den Score").
Datensatz + Scope: Blind-Review-Workbook, 16 vollständige Submissions,
  64 Frage-Zeilen (q1–q4 je 16). Scope eingefroren, Join über review_item_id.
Primärmetrik: Pearson r gesamt steigt von 0.63 auf ≥ 0.75.
Nebenmetriken (dürfen nicht kippen): |Mean Diff| bleibt ≤ 1.0 Punkt;
  MAE pro Frage steigt nirgends um > 0.5.
Abbruchkriterium: r < 0.65 ODER |Mean Diff| > 2.0 → Anker verwerfen/überarbeiten.
Alternativerklärung: r steigt nur, weil der Judge global strenger wird und die
  Rangordnung dadurch zufällig stabiler aussieht. Check: Mean Diff + "Teacher
  höher n" vor/nach vergleichen.
Kosten: 64 Judge-Calls (Rescore des eingefrorenen Scopes).
```

Mit diesem Blatt wäre das reale Ergebnis (r 0.796 ✓, aber Mean Diff −2.07 ✗)
automatisch als **Teilerfolg mit verletzter Nebenbedingung** klassifiziert worden —
genau das ist der heutige, ehrliche Projektstand: Der systematische Streng-Bias ist
das offene Problem, nicht ein Fußnotendetail.

---

## 3. Idee-Lebenszyklus

Jede Idee durchläuft diese Stationen. Keine Abkürzungen — insbesondere nicht von
"Idee" direkt zu "auf main deployen".

```
Idee
 → Klassifikation        (toadapt-change-control: welche Änderungsklasse, welches Gate?)
 → Hypothese-Blatt       (Abschnitt 2 dieser Skill, VOR dem Lauf)
 → Experiment            (lokal oder Branch — NIE direkt am produktiven Judge)
 → Messung               (toadapt-proof-and-analysis-toolkit; Vergleichs-Pipeline unten)
 → Adoption              (Gate aus change-control erfüllt, Report geschrieben)
   ODER
   dokumentiertes Retirement (Eintrag im Stil von toadapt-failure-archaeology:
   Symptom → Root Cause → Beleg → Status "verworfen, weil …")
```

Regeln zu den Stationen:

- **Experiment nie am Prod-Judge:** Änderungen an `EVALUATOR_SYSTEM`,
  `EVALUATE_PROMPT` oder den Kalibrierungsankern (`backend/evaluator/
  rubric_evaluator.py`) werden lokal bzw. auf einem Branch gegen den
  **eingefrorenen** Blind-Review-Scope gerechnet, bevor irgendetwas deployt wird.
  Das Gate selbst ("kein Judge-Deploy ohne Alignment-Recheck") gehört
  `toadapt-change-control`; diese Skill liefert die Methodik dafür.
- **Messung heißt: die bestehende Pipeline benutzen** (Bedienung im Detail:
  `toadapt-run-and-operate`):

  ```bash
  # 1. Rohdaten importieren (schreibt SHA-256-Manifest, s. Abschnitt 5)
  python scripts/import_prolific_runs.py <export-datei-oder-ordner> --batch <name>
  # 2. Workbooks erzeugen: *_rubric.xlsx (mit Judge-Scores),
  #    *_blind.xlsx (OHNE Judge-Scores, für die Lehrkraft), *_chat_turns.xlsx
  python scripts/export_review_workbooks.py --prefix <experiment-name>
  # 3. Lehrkraft füllt im Blind-Workbook teacher_awarded_points + teacher_rationale
  # 4. Vergleich rechnen (Lehrer-Workbook ist kanonisch)
  python scripts/compare_teacher_rubric_scores.py \
    --teacher-workbook <blind-ausgefüllt.xlsx> \
    --rubric-workbook <rubric.xlsx>
  ```

- **Sackgassen sind Ergebnisse.** Eine widerlegte Hypothese wird NICHT gelöscht,
  sondern mit Hypothese-Blatt + Messwerten + Verwerfungsgrund abgelegt (Eintrag in
  `toadapt-failure-archaeology` bzw. deren Chronik-Format). Sonst schlägt die
  nächste Person dieselbe Schlacht noch einmal.

---

## 4. Woher gute Ideen hier historisch kamen

Prüfe neue Ideen gegen diese Herkunftsmuster — sie sind die empirisch belegten
Quellen echter Verbesserungen in diesem Repo:

| Quelle | Beispiel im Repo | Beleg |
|---|---|---|
| **Blind-Review-Empirie** (was Lehrende real bestrafen/belohnen) | Kalibrierungsanker q1–q4 im Judge-Prompt — direkt aus Lehrer-Rationales destilliert | Commit `9a8077f`; `_format_calibration_notes` in `backend/evaluator/rubric_evaluator.py` |
| **Deploy-Schmerz** (wiederholtes Blind-Debugging) | `/health/diagnostics`-Endpoint entstand aus der Mongo-Debugging-Saga gegen Railway | Commits `464bbca` ("Expose Mongo env diagnostics"), `dbc92f2` |
| **Lehrpersonen-Feedback** (Unterstützungs-Doktrin) | Review-Flags (`needs_human_review`) als explizite "hier soll ein Mensch draufschauen"-Signale | Report-Schlusssatz: "Review-Flags markieren Stellen, an denen der Judge die Lehrkraft unterstuetzen und nicht ersetzen soll." |

**Anti-Quelle: Framework-Moden.** "Lasst uns Agent-Framework X / Prompt-Technik Y
einbauen, weil es gerade alle tun" hat in diesem Repo keine einzige belegte
Verbesserung erzeugt — wohl aber teure Umbauten (siehe die WebSocket- und
SDK-Wechsel-Kapitel in `toadapt-failure-archaeology`). Eine Idee, die nicht an
einer konkreten Beobachtung (Datenpunkt, Schmerz, Feedback) hängt, bekommt kein
Hypothese-Blatt und keinen Lauf.

---

## 5. Publikations- und Claim-Standard

### Was behauptet werden DARF

- **Nur blind validierte Metriken, immer mit Scope-Angabe n.** Korrekt: "Auf dem
  eingefrorenen Blind-Review-Scope (16 Submissions, 64 Frage-Zeilen, Stand
  2026-05-31) erreicht der kalibrierte Judge Pearson r = 0.796 bei MAE 2.711 und
  systematischer Unterbewertung (Mean Diff −2.07; Teacher höher in 48/64 Fällen)."
  "Blind" heißt: Die Lehrkraft vergab ihre Punkte im Blind-Workbook, OHNE die
  Judge-Scores zu sehen (das Blind-Workbook enthält per Konstruktion keine
  Judge-Spalten — prüfbar in `_write_blind_workbook`,
  `scripts/export_review_workbooks.py`).
- Beschreibungen des Systems und der Methodik (Architektur, Blind-Review-Protokoll,
  konservativer Judge mit Review-Flags) — als Design-Beitrag, nicht als
  Wirksamkeitsbeweis.

### Was NICHT behauptet werden darf

| Verbotener Claim | Warum |
|---|---|
| "ToAdapt verbessert Lernleistung / Transferkompetenz" | Keine Kontrollgruppe, kein Prä-Post-Design. Wirksamkeits-Claims erfordern ein kontrolliertes Studiendesign, das es (Stand: 2026-07-08) nicht gibt. |
| "Der Judge ersetzt die Lehrkraft" / "automatisiertes Grading" | Projektdoktrin ist **unterstützen, nicht ersetzen** — im Judge-System-Prompt kodiert ("Du unterstützt Lehrende bei der Bewertung", `EVALUATOR_SYSTEM` in `backend/evaluator/rubric_evaluator.py`) und im Alignment-Report festgehalten. Review-Flags + konservative Punktvergabe sind Feature, nicht Schwäche. |
| Aggregat-Metriken ohne die Gegenmetrik (nur r ohne Mean Diff, nur MAE ohne Per-Frage-Split) | Lüge durch Auslassung — siehe Abschnitt 1. |
| Zahlen aus nicht eingefrorenen / nachträglich umgeschnittenen Scopes | Scope-Shopping macht jede Metrik manipulierbar. |
| Irgendetwas unter Nennung echter Teilnehmer-IDs oder -Antworten | PII (personenbezogene Daten); siehe unten. |

### Reproduzierbarkeit — die vier Anker

1. **SHA-256-Manifeste beim Import.** `scripts/import_prolific_runs.py` kopiert
   Rohdaten nach `data/prolific_runs/raw/<batch>/` und schreibt
   `data/prolific_runs/manifests/<batch>.json` mit Dateiliste, Größen und
   SHA-256-Hash pro Datei. Das Skript verweigert Überschreiben existierender
   Batches (FileExistsError) — Batches sind append-only. So ist später beweisbar,
   auf welchen Bytes eine Analyse lief.
2. **Eingefrorene Scopes mit stabilen IDs.** Jede Frage-Zeile hat eine
   `review_item_id` im Format `{case_id}:{question_id}:{nnn}` (dreistellig
   laufend, erzeugt in `scripts/export_review_workbooks.py`). Der Vergleich joint
   ausschließlich über diese IDs; das **Lehrer-Workbook ist kanonisch** —
   Rubric-Zeilen ohne Lehrer-Match werden by design ausgeschlossen (verhindert,
   dass bereinigte Testuser zurück in die Analyse rutschen; dokumentiert im
   Docstring von `scripts/compare_teacher_rubric_scores.py`).
3. **Benennung und Zeitstempel.** Alle Pipeline-Artefakte tragen UTC-Timestamps
   (`YYYYMMDDTHHMMSSZ`) im Dateinamen; Details und Report-Namenskonventionen:
   `toadapt-docs-and-writing`.
4. **Daten bleiben privat.** `data/prolific_runs/**` ist per Root-`.gitignore`
   vollständig von Git ausgeschlossen (nur das README ist getrackt). Echte
   Teilnehmerdaten liegen seit 2026-07-08 AUSSERHALB des Repos unter
   `~/ToAdapt_sensitive_data/` und werden NIEMALS zurückkopiert, committet oder
   in Skills/Fixtures zitiert (DSGVO- und Prolific-ToS-Pflichten; Hintergrund des
   PII-Vorfalls: `toadapt-failure-archaeology`). Für Tests und Beispiele:
   ausschließlich synthetische Daten.

**Achtung, echter LLM-Verbrauch:** `scripts/retry_technical_fallback_scores.py`
macht ohne `--dry-run` echte Judge-Calls. In der Planung eines Laufs als Kosten
budgetieren (Hypothese-Blatt, Feld "Kosten des Laufs").

---

## 6. Wohin mit konkreten Forschungsfragen

Diese Skill definiert die Disziplin. Die **konkreten offenen Probleme** (mit
SOTA-Lücke, vorhandenen Projekt-Assets, ersten Schritten und falsifizierbaren
Meilensteinen) leben in `toadapt-research-frontier`. Das härteste lebende Problem —
systematische q4/Bloom-6-Unterbewertung (MAE ~4.97 auf dem 64-Zeilen-Scope) — hat
eine eigene executable Kampagne: `toadapt-judge-alignment-campaign`.

---

## Provenance und Wartung

Erstellt: 2026-07-08, verifiziert gegen den Repo-Stand desselben Tages
(Branch main, HEAD `141bb63`, nach dem filter-repo-Rewrite vom 2026-07-08).

Re-Verifikations-Kommandos für drift-anfällige Fakten (vom Repo-Root ausführen):

| Fakt | Kommando |
|---|---|
| Alignment-Report existiert, Scope 16/64 | `grep -n "Eindeutige Submissions\|Teacher-Items" docs/teacher_alignment_report_20260531_17submissions.md` |
| Metriken r/MAE/MeanDiff vor→nach | `grep -n "Pearson r\|Mean Diff\|MAE" docs/teacher_alignment_report_20260531_17submissions.md` |
| Kalibrierungsanker noch hartkodiert q1–q4 | `grep -n "_format_calibration_notes" backend/evaluator/rubric_evaluator.py` |
| Unterstützen-nicht-ersetzen im Judge-Prompt | `grep -n "Du unterstützt Lehrende" backend/evaluator/rubric_evaluator.py` |
| SHA-256-Manifest im Import-Skript | `grep -n "sha256\|manifest" scripts/import_prolific_runs.py` |
| review_item_id-Format | `grep -n "review_item_id = f" scripts/export_review_workbooks.py` |
| Lehrer-Workbook kanonisch / Rubric-only ausgeschlossen | `sed -n '1,6p' scripts/compare_teacher_rubric_scores.py` |
| Blind-Workbook ohne Judge-Spalten | `grep -n -A 14 "def _write_blind_workbook" scripts/export_review_workbooks.py` |
| data/prolific_runs gitignored | `grep -n "prolific" .gitignore` |
| retry-Skript macht echte LLM-Calls | `sed -n '1,2p' scripts/retry_technical_fallback_scores.py && grep -n "dry-run" scripts/retry_technical_fallback_scores.py` |
| Ideen-Herkunfts-Commits existieren | `git log --oneline --all \| grep -E "9a8077f\|464bbca"` |
| Sensible Daten außerhalb des Repos | `ls ~/ToAdapt_sensitive_data` |
