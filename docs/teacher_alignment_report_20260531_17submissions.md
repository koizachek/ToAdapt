# Teacher Alignment Report - 17 Abgaben

Stand: 2026-05-31

## Scope

- Kanonische Stichprobe: 17 Abgaben aus dem Lehrer-Workbook.
- Auswahl: `q1`-Teacher-Zeilen `002` bis `018`; daraus wurden die zugehoerigen Submission-IDs gemappt.
- Nicht enthalten: `dianatest`, `DavidSonnabend`, zusaetzliche Zeile `020` und alle nicht im 17er-Scope liegenden Rescore-Zeilen.
- Teacher-Items im 17er-Scope: 62 bewertete Frage-Zeilen.
- Eindeutige Submissions im Scope: 17.

## Gesamtvergleich

| Metrik | Vor Alignment | Nach Alignment |
|---|---:|---:|
| Items | 60 | 62 |
| Teacher Mean | 14.4 | 14.153 |
| Rubric Mean | 14.133 | 12.234 |
| Mean Diff Rubric-Teacher | -0.267 | -1.919 |
| Median Diff | 0.5 | -1.5 |
| MAE Punkte | 3.017 | 2.742 |
| RMSE Punkte | 4.722 | 3.944 |
| Mean Abs Diff %-Punkte | 11.571 | 10.397 |
| Pearson r | 0.632 | 0.789 |
| Rubric hoeher n | 32 | 13 |
| Teacher hoeher n | 26 | 45 |
| Gleich n | 2 | 4 |
| Within 1 Punkt n | 19 | 20 |
| Within 2 Punkte n | 30 | 36 |
| Within 10 %-Punkte n | 35 | 39 |

## Nach Frage

| Frage | n | MAE vorher | MAE nach | Diff vorher | Diff nach | Pearson vorher | Pearson nach |
|---|---:|---:|---:|---:|---:|---:|---:|
| q1 | 17 | 2.133 | 2.353 | 0.533 | -1.118 | 0.904 | 0.888 |
| q2 | 15 | 2.367 | 2.6 | 1.567 | -0.933 | 0.888 | 0.744 |
| q3 | 15 | 2.2 | 1.033 | 2.2 | -0.7 | 0.901 | 0.878 |
| q4 | 15 | 5.367 | 5.033 | -5.367 | -5.033 | 0.643 | 0.791 |

## Alignment-Signale im neuen Judge

- Review-Flags auf Frage-Ebene: 43
- Evaluation Status: ok=59, technical_fallback=3
- Judge Confidence: high=19, low=3, medium=40
- Score Bands: low=9, partial=42, solid=5, strong=3, unscored=3

## Interpretation

- Der 17er-Scope bleibt strikt an die Lehrerbewertung gebunden; bereinigte/testartige Abgaben werden nicht zur Dashboard- oder Alignment-Metrik hinzugezogen.
- Das Alignment verbessert nicht jede Kennzahl gleichzeitig. Relevant ist deshalb nicht nur der Mittelwert, sondern auch Richtung, Ausreisser, Review-Flags und Frageebene.
- Die Review-Flags markieren genau die Stellen, an denen der Judge die Lehrkraft nicht ersetzen, sondern gezielt auf unsichere oder technisch auffaellige Bewertungen hinweisen soll.

