---
name: toadapt-tutor-response-evaluation
description: Pädagogische Qualitätsbewertung der LLM-Tutor-Antworten in ToAdapt nach der NAACL-2025-Taxonomie (Maurya et al., "Unifying AI Tutor Evaluation") - acht Dimensionen, LLM-as-Judge, Human-Validierung, Desirability-Quoten. Lade diese Skill, wenn du (a) messen willst, wie gut die Chat-Agenten oder Denkanstöße pädagogisch antworten ("verrät der Agent Lösungen?", "sind Antworten actionable?"), (b) scripts/evaluate_tutor_responses.py bedienen willst (Erhebung, Annotation-Workbook, Aggregation), (c) einen Agent-/Formative-Prompt geändert hast und den Pflicht-Regressionsnachweis brauchst, (d) ein TUTOR-Modell auswählen oder wechseln willst (OPENROUTER_MODEL) und Kandidaten vergleichen musst, oder (e) die Judge-Verlässlichkeit gegen menschliche Annotation validieren willst. Keywords - Tutor-Evaluation, NAACL, MRBench, Mistake Identification, Revealing of the Answer, Providing Guidance, Actionability, Tutor Tone, Humanlikeness, Desirability, Pedagogical Ability, LLM-as-Judge, Modellwahl.
---

# Tutor-Antwort-Evaluation (NAACL-2025-Framework)

Stand: 2026-07-09. Bewertet wird die Qualität der **LLM-Antworten an
Studierende** (Chat-Agenten + Denkanstöße) — nicht die Studierenden-
Leistung (dafür: `toadapt-judge-alignment-campaign`). Framework: Maurya
et al., NAACL 2025, "Unifying AI Tutor Evaluation" (Repo:
github.com/kaushal0494/UnifyingAITutorEvaluation, Guidelines CC BY-SA 4.0).
Implementierung: `backend/evaluator/tutor_eval.py` +
`scripts/evaluate_tutor_responses.py`. Alles läuft OFFLINE über geloggte
Events — kein Eingriff in den Live-Betrieb (Änderungsklasse D).

## Wann diese Skill NICHT gilt

- Punktevergabe an Studierende / Judge-Kalibrierung: `toadapt-judge-alignment-campaign`.
- Guardrail-Pattern-Tests (hartes Blocken von Framework-Namen etc.):
  `toadapt-proof-and-analysis-toolkit` Methode 4 — Guardrails verhindern
  Verstöße mechanisch, diese Skill MISST pädagogische Qualität graduell.
- Lernstand der Studierenden über Zeit: `toadapt-knowledge-tracing`.

## 1. Die acht Dimensionen (Original-Skalen)

| Dimension | Frage | Labels | Erwünscht |
|---|---|---|---|
| mistake_identification | Erkennt der Tutor den Fehler/die Fehlvorstellung? | Yes / To some extent / No / **Not applicable** | Yes |
| mistake_location | Zeigt er, WO genau das Denken hakt? | wie oben | Yes |
| revealing_of_the_answer | Verrät er die Lösung/Empfehlung? | Yes (and correct) / Yes (but incorrect) / No | **No** |
| providing_guidance | Gibt er korrekte, relevante Hilfestellung? | Yes / To some extent / No | Yes |
| actionability | Ist klar, was die Person als Nächstes tut? | wie oben | Yes |
| coherence | Passt die Antwort logisch zum Gespräch? | wie oben | Yes |
| tutor_tone | Ton der Antwort | Encouraging / Neutral / Offensive | Encouraging |
| humanlikeness | Klingt es natürlich, nicht templated? | Yes / To some extent / No | Yes |

Dokumentierte **Adaptionen** ans Scaffolding-Setting (im Modul-Docstring):
(1) `Not applicable` für die Mistake-Dimensionen — anders als MathDial
enthält nicht jede Studierenden-Nachricht einen Fehler; NA fließt NICHT in
die Desirability ein. (2) "Answer" = konkrete Lösung/Empfehlung/
Priorisierung zur Case-Aufgabe. (3) ToAdapt-Doktrin: JEDES Enthüllen ist
unerwünscht (desired = "No"), egal ob korrekt.

**Desirability-Quote** pro Dimension = Anteil erwünschter Labels an allen
gültigen (ohne NA/Invalid) — die zentrale Kennzahl, ausgewiesen gesamt und
pro Agent-Typ (metacognitive/strategic/conceptual/procedural/
formative_feedback).

## 2. Erhebung und Auswertung (Kommandos)

Datenquelle: Export der `experiment_events` (chat_turn_completed enthält
user_message + assistant_message + agent_type; formative_feedback_requested
enthält draft_text + feedback — draft_text wird seit 2026-07-09 geloggt).

```bash
# 1) Sichten, was bewertet würde (keine LLM-Calls, keine Kosten)
python scripts/evaluate_tutor_responses.py --events <events.json> --include-feedback --dry-run

# 2) Kostenprobe, dann voller Judge-Lauf (echte LLM-Calls!)
python scripts/evaluate_tutor_responses.py --events <events.json> --limit 50
python scripts/evaluate_tutor_responses.py --events <events.json> --include-feedback

# 3) Nur neu aggregieren (aus vorhandener JSONL, kostenlos)
python scripts/evaluate_tutor_responses.py --aggregate-only <tutor_eval_*.jsonl>
```

Outputs (Default `data/prolific_runs/derived/tutor_eval/`, gitignored):
`tutor_eval_<ts>.jsonl` (pro Turn: Labels + Ein-Satz-Begründungen),
`_summary.json` + `_summary.csv` (Semikolon; Desirability je Dimension ×
Scope). Ungültige Judge-Labels werden als `Invalid` gezählt und im
Skript-Output gemeldet — viele Invalids = Judge-Modell wechseln, nicht
Daten schönreden.

## 3. Judge-Verlässlichkeit: Human-Validierung (Pflicht vor Vertrauen)

Bevor Desirability-Quoten als Evidenz gelten, den LLM-Judge gegen
menschliche Annotation prüfen — dasselbe Blind-Protokoll wie beim
Teacher-Alignment:

```bash
python scripts/evaluate_tutor_responses.py --events <events.json> --annotation-workbook
```

erzeugt `tutor_annotation_<ts>_blind.xlsx` (Sheet `annotation` mit leeren
Label-Spalten, Sheet `labels` mit Definitionen und erlaubten Werten).
~30 Turns von Hand labeln, Join über die stabile `tutor_item_id`
(`{session}:{nnn}` bzw. `{submission}:{qid}:{n}`), prozentuale
Übereinstimmung pro Dimension rechnen (Metrik-Disziplin:
`toadapt-proof-and-analysis-toolkit`). Faustregel aus dem Paper-Kontext:
Dimensionen mit schwacher Mensch-Judge-Übereinstimmung nur mit
Human-Stichprobe berichten, nicht automatisiert.

## 4. Einsatz 1 — Regressionspflicht bei Prompt-Änderungen (Klasse A)

Jede Änderung an Agent-Prompts (`backend/agents/orchestrator.py`), am
formativen Prompt (`backend/evaluator/formative_feedback.py`) oder an
Guardrail-Fallback-Texten braucht neben der Guardrail-Regression den
Tutor-Eval-Vergleich:

1. Fixes Sample einfrieren (z.B. 100 Turns, dieselbe Events-Datei).
2. Baseline-Quoten VOR der Änderung (liegt nach Rollout-Workflow W3 vor).
3. Nach der Änderung: Transkripte mit neuem Prompt erzeugen (Staging),
   identisch bewerten, Quoten vergleichen.
4. Nicht verhandelbar: `revealing_of_the_answer`-Desirability darf nicht
   sinken. Verschlechtert sich eine Dimension deutlich (> ~5 Punkte),
   zurück ans Prompt — "liest sich besser" zählt nicht.

## 5. Einsatz 2 — Modellwahl fürs Tutor-LLM (OPENROUTER_MODEL)

Kandidaten-Vergleich, bevor das produktive Tutor-Modell gewechselt wird:

1. Festes Prompt-Set (z.B. 50 Studierenden-Nachrichten aus echten Events).
2. Pro Kandidat in Staging Antworten erzeugen (`OPENROUTER_MODEL` setzen).
3. Alle Transkripte mit DEMSELBEN Judge-Modell bewerten (Skript-Flag
   `--model` erlaubt umgekehrt auch Judge-Vergleiche — nie beides
   gleichzeitig variieren!).
4. Entscheidung entlang: Desirability-Profil (Reveal-Disziplin zuerst,
   dann Guidance/Actionability), Guardrail-Trigger-Rate, Kosten/Turn
   (`llm_call_completed`-Tokens), Latenz.
5. Modellwechsel ist Klasse A **und** — falls dasselbe Modell auch der
   Bewertungs-Judge ist — Klasse B (Alignment-Recheck, siehe
   `toadapt-judge-alignment-campaign`).

## Provenance und Wartung

Erstellt 2026-07-09 (HEAD 64b62f9). Taxonomie, Skalen und Adaptionen gegen
`backend/evaluator/tutor_eval.py` verifiziert; Skript-Modi gegen
`scripts/evaluate_tutor_responses.py` (Dry-Run + Workbook mit synthetischen
Events getestet; Tests: `tests/test_tutor_eval.py`, 8 Stück).

Re-Verifikation bei Drift:
- Dimensionen/Labels: `grep -n "TUTOR_EVAL_DIMENSIONS\|desired" backend/evaluator/tutor_eval.py | head`
- Skript-CLI: `python scripts/evaluate_tutor_responses.py --help`
- Event-Felder: `grep -n "draft_text\|assistant_message" backend/api/routes.py`
- Limit Denkanstöße: `grep -n "MAX_FEEDBACK_PER_QUESTION" backend/evaluator/formative_feedback.py`
