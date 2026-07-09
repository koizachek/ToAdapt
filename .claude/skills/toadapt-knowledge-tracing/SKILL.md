---
name: toadapt-knowledge-tracing
description: Knowledge Tracing und langfristige Kompetenzentwicklung der Lernenden in ToAdapt. Lade diese Skill, wenn du (a) Lernverläufe über Zeit auswerten willst ("wird Studierende:r X in 'wirkungskette' besser?", Lernkurven, Mastery, Kompetenzentwicklung über TP1–TP4), (b) wissen musst, welche Längsschnitt-Datenbasis existiert (Pseudonym-Stabilität, learning_objective_tags, Bloom-Stufen, Zeitstempel) und welche NICHT, (c) ein Mastery-Modell (BKT/EWMA/Lernkurven) für dieses Repo bauen oder bewerten sollst, (d) adaptive Scaffolding-Intensität auf Basis von Lernstand planst, oder (e) das mitgelieferte Trajektorien-Skript nutzen willst. Keywords - Knowledge Tracing, BKT, Mastery, Lernkurve, longitudinal, Skill Development, Kompetenz, Trajektorie, EWMA, learning_objective_tags, Verlauf, Fortschritt.
---

# Knowledge Tracing & langfristige Kompetenzentwicklung

Stand: 2026-07-09. **Ehrlicher Status: In ToAdapt existiert KEIN
Knowledge-Tracing-Modell im Produkt.** Diese Skill dokumentiert (1) was
Knowledge Tracing hier bedeutet, (2) welche Längsschnitt-Datenbasis bereits
erhoben wird, (3) das mitgelieferte deskriptive Werkzeug, (4) den gestuften
Ausbaupfad mit Gates, (5) die statistischen Grenzen, die man kennen muss,
bevor man Aussagen über einzelne Lernende trifft.

## Wann diese Skill NICHT gilt

- Qualität des Judge (Punktevergabe): `toadapt-judge-alignment-campaign`.
- Qualität der Tutor-Antworten: `toadapt-tutor-response-evaluation`.
- Momentaufnahme "wo hakt es JETZT" für Tutor:innen: das Gruppen-Dashboard
  (`/dashboard/groups`, siehe `toadapt-run-and-operate`).
- Forschungs-Disziplin (Hypothesen, Evidenz-Bar): `toadapt-research-methodology`.

## 1. Begriff, wie er HIER gemeint ist

Knowledge Tracing = aus einer Folge bewerteter Interaktionen den latenten
Kompetenzstand einer Person pro Fähigkeits-Dimension schätzen und dessen
Entwicklung verfolgen. Klassische Familien: **BKT** (Bayesian Knowledge
Tracing: pro Skill ein 2-Zustands-Modell gelernt/nicht-gelernt mit Lern-,
Rate- und Schlupfwahrscheinlichkeit), **Lernkurven** (Leistung über
Gelegenheiten), **DKT** (neuronale Varianten — für die hiesigen Datenmengen
ungeeignet, siehe §5). In ToAdapt sind die "Skills" der Lernenden:
**Lernziel-Tags** (`learning_objective_tags`, z.B. `wirkungskette`,
`trade-off`, `integration` — Herkunft: `BLOOM_TAGS` in
`backend/evaluator/rubric_evaluator.py` plus Judge-Vergabe) und
**Bloom-Stufen** (2–6). Die "Gelegenheiten" sind bewertete Fragen über
Cases und Touchpoints hinweg.

## 2. Vorhandene Längsschnitt-Datenbasis (verifiziert 2026-07-09)

| Quelle | Inhalt pro Messpunkt | Längsschnitt-Schlüssel |
|---|---|---|
| `dashboard_results` (Mongo) bzw. `backend/db/submissions/*.json` | pro Frage: `awarded_points/max_points`, `bloom_level`, `learning_objective_tags`, `canvas_alignment`, `evaluated_at`, `target_tp` | `matrikelnummer` = **stabiles Pseudonym** |
| `submission_states` | Antworttexte, `answer_stats` (Tipp-Telemetrie), `feedback_requests` | Pseudonym |
| `experiment_events` | jeden Chat-Turn (Agent-Typ, Texte), Denkanstöße, Timestamps | Pseudonym via `user_id` |

Voraussetzung für Verkettung über Zeit: **`PSEUDONYM_SECRET` unverändert
lassen** — das HMAC-Pseudonym (`backend/anonymize.py`) ist nur bei
konstantem Secret stabil. Secret-Rotation = alle Lernverläufe reißen ab.
Altdaten aus der Probephase (vor Aktivierung der Pseudonymisierung) verketten
sich NICHT mit neuen Daten derselben Person.

Was NICHT existiert: kein Mastery-Feld irgendwo im Produkt, keine
TP-übergreifenden Rückverweise im Scaffolding ("in TP1 hattet ihr X…" aus
CLAUDE.md ist unimplementierte Vision), keine adaptive
Scaffolding-Intensität, keine Lernkurven-Anzeige.

## 3. Mitgeliefertes Werkzeug: deskriptive Trajektorien (Stufe 1)

```bash
python .claude/skills/toadapt-knowledge-tracing/scripts/objective_trajectories.py \
  <verzeichnis-mit-ergebnis-jsons> --out trajektorien.csv
```

Input: Dashboard-Ergebnis-JSONs (lokal `backend/db/submissions/`, in
Produktion ein Export der Mongo-Collection `dashboard_results` als
Einzeldateien). Output pro (Pseudonym × Tag): Messpunktzahl, erste/letzte
Leistung in %, Delta, **EWMA-Mastery** (exponentiell gewichteter Schnitt,
`--alpha 0.4` = jüngste Messung zählt 40 %). Kein LLM, keine Kosten.

**Datenschutz:** Das CSV enthält pseudonymisierte EINZELDATEN → Forschungs-
Kontext (`RESEARCH_API_KEY`-Sphäre). Tutor:innen bekommen ausschließlich
Gruppen-Aggregate — niemals dieses CSV weitergeben.

## 4. Ausbaupfad (gestuft, jede Stufe mit Gate)

| Stufe | Was | Änderungsklasse (change-control) | Gate |
|---|---|---|---|
| 1 | Deskriptive Trajektorien (Skript, §3) | D (Forschung, offline) | läuft — Ergebnisse nur intern |
| 2 | Gruppen-Entwicklung im Tutor-Dashboard ("Gruppe verbessert sich in `wirkungskette` über TPs": Δ des Gruppen-Mittels pro Tag zwischen TP-Fenstern) | C/A (neuer Endpoint + UI; nur Aggregate!) | Tests analog `tests/test_groups_and_privacy.py`; keine Einzelkennungen im Response |
| 3 | EWMA-/BKT-Mastery pro (Pseudonym × Tag) als Forschungs-Endpoint hinter `X-Research-Key` | D | Vorhersagegüte: Mastery bei TP n sagt Leistung bei TP n+1 besser voraus als der einfache Mittelwert (Held-out-Vergleich) |
| 4 | Adaptive Scaffolding-Intensität (Agent-Verhalten hängt vom Lernstand ab) | **A + B** (studierendensichtbar, Prompt-Wirkung) | siehe `toadapt-research-frontier` Problem 4; NIE ohne Guardrail-Regression + Wirksamkeits-Design |

Stufe 4 ist Forschungsprojekt, nicht Feature-Ticket: Hypothese und
Messplan zuerst (`toadapt-research-methodology`), sonst entsteht ein
adaptives System, dessen Wirkung niemand belegen kann.

## 5. Statistische Grenzen — vor jeder Aussage lesen

- **Wenige Messpunkte:** Pro Lerner:in und Tag typischerweise 1–2 Fragen
  pro Case, wenige Cases pro TP, 4 TPs. Individuelle "Lernkurven" haben
  oft n=3–6 Punkte — DKT/neuronale Modelle sind damit ausgeschlossen,
  selbst BKT-Parameter werden instabil. EWMA + Delta ist das ehrliche
  Auflösungsniveau.
- **Judge-Rauschen > kleine Lerneffekte:** Der Judge hat MAE ≈ 2.7 Punkte
  gegen Lehrerurteil (Alignment-Studie 2026-05-31), bei q4 ≈ 5. Ein
  Anstieg von 60 %→70 % bei einer 10-Punkte-Frage liegt in der
  Rausch-Größenordnung. Individual-Aussagen brauchen mehrere konsistente
  Messpunkte; **Gruppen-Mittel sind robuster** (Rauschen mittelt sich).
- **Konfundierung:** Zwischen TPs ändern sich Case, Fragenformat, Bloom-
  Stufe UND Schwierigkeit — ein Leistungsabfall TP1→TP2 ist kein
  Kompetenzverlust. Vergleiche innerhalb desselben Tags über Cases
  GLEICHER Bloom-Stufe, oder berichte Bloom-getrennt.
- **Selektionseffekte:** Wer den Denkanstoß nutzt, unterscheidet sich
  systematisch von wem nicht (Logging: `formative_feedback_requested`) —
  für Wirksamkeitsfragen randomisieren oder zumindest kontrollieren.

## Provenance und Wartung

Erstellt 2026-07-09 (HEAD 64b62f9), verifiziert gegen den Code; das
Skript wurde mit synthetischen Längsschnittdaten getestet (3 Messpunkte
40→70→90 % ⇒ Delta 50.0, EWMA(0.4) 67.2).

Re-Verifikation bei Drift:
- Ergebnis-Felder: `grep -n "evaluated_at\|learning_objective_tags\|group_code" backend/api/routes.py`
- Pseudonym-Mechanik: `grep -n "def pseudonymize" backend/anonymize.py`
- Tags-Herkunft: `grep -n "BLOOM_TAGS" backend/evaluator/rubric_evaluator.py`
- Skript-Selbsttest: synthetische JSONs nach /tmp, dann Aufruf wie in §3.
