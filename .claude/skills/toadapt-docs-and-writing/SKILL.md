---
name: toadapt-docs-and-writing
description: >
  Lade diese Skill, BEVOR du im ToAdapt-Repo Dokumentation liest, schreibst
  oder aktualisierst. Sie sagt dir, welchem Dokument du glauben darfst
  (ROLLOUT_CHECKLIST.md = operativer Gate-Workflow, ROLLOUT_PLAN.md =
  Hintergrund-Wahrheit; CLAUDE.md, TODO.md, dev-docs/ = Fossile;
  README.md = Einstieg mit bekannten Fehlern), wie Forschungs-Reports und
  Pipeline-Artefakte benannt werden (teacher_alignment_report_*, review_item_id,
  UTC-Timestamps), und welchen Haus-Stil das Projekt hat (Deutsch primär,
  Commit-Messages ohne AI-Attribution, DE/EN-Sprachobjekte synchron halten).
  Trigger: "ist CLAUDE.md aktuell?", "wo steht der Projektstatus?",
  "README stimmt nicht mit dem Code überein", "wie benenne ich diesen Report?",
  "Commit-Message schreiben", "Doku nach meiner Änderung aktualisieren",
  "neuen UI-Text hinzufügen", "Skill-Library pflegen", Widersprüche zwischen
  Doku und Code, Statusblock im Rollout-Plan, i18n / Übersetzung / Locale.
---

# ToAdapt Doku & Schreiben — Was gilt, was ist Fossil, wie wird geschrieben

Kontext in einem Satz: ToAdapt ist ein Einzel-Transfer-Trainer (FastAPI-Backend
auf Railway, Next.js-Frontend auf Vercel) für den BWL-A-Kurs der Universität
St.Gallen — das Repo enthält aber Dokumente aus einer **verworfenen früheren
Architektur** (Gruppen-Echtzeit-System), die nie nachgezogen wurden. Wer Doku
liest, muss zuerst wissen, welches Dokument die Wahrheit sagt. Wer Doku
schreibt, folgt den Konventionen hier.

## Wann diese Skill NICHT gilt

- Du willst wissen, ob/wie du eine Änderung machen darfst (Commits, Push,
  Deploy, Gates) → `toadapt-change-control`. Dort steht auch die Regel-Liste
  mit Rationale; hier steht nur der Schreibstil.
- Du willst verstehen, WARUM CLAUDE.md/dev-docs zu Fossilen wurden
  (Pivot-Geschichte, Commits) → `toadapt-failure-archaeology`.
- Du willst die Ist-Architektur statt der Doku-Hierarchie →
  `toadapt-architecture-contract`.
- Du suchst Env-Variablen oder Magic Numbers → `toadapt-config-and-flags`.
- Du willst die Alignment-Pipeline AUSFÜHREN (nicht ihre Artefakte benennen)
  → `toadapt-run-and-operate` bzw. `toadapt-judge-alignment-campaign`.
- Du willst BWL-Fachbegriffe (Bloom, TP, Scaffolding, Canvas) verstehen →
  `bwl-scaffolding-reference`.
- Du willst ein wissenschaftliches Manuskript sprachlich verbessern → das ist
  Paper-Prosa, nicht Repo-Doku; nutze die persönliche Skill der Autorin
  (`manuscript-review`), nicht diese.

---

## 1. Dokumente-der-Wahrheit-Hierarchie

Regel Nummer eins: **Bei Widerspruch zwischen Dokumenten gewinnt für den
operativen Rollout-Ablauf ROLLOUT_CHECKLIST.md, sonst ROLLOUT_PLAN.md.
Bei Widerspruch zwischen Doku und Code gewinnt der Code.**

| Dokument | Status | Wofür verwenden | Wofür NIEMALS verwenden |
|---|---|---|---|
| `ROLLOUT_CHECKLIST.md` | **MASSGEBLICH, operativ** (Stand: 2026-07-09, Commit `64b62f9`) | Gate-basierter Rollout-Workflow W0–W6 (jede Phase erst abgeschlossen, wenn ihr GATE messbar erfüllt ist; Verantwortliche [O]/[C]/[G]) | — |
| `ROLLOUT_PLAN.md` | **MASSGEBLICH als Hintergrund-Referenz** (Stand: 2026-07-08) | Projektstatus (Status-Block), Roadmap (Phasen 0–3), Ist-Zustands-Beschreibung, offene Punkte; verweist seit 2026-07-09 in Zeile 3 auf ROLLOUT_CHECKLIST.md | — |
| `README.md` | Einstieg, **teilweise falsch** (s.u.) | Setup-Kommandos, Pipeline-Kurzanleitungen (Publish, Import, Export) | Architektur-/Tech-Stack-Aussagen ungeprüft übernehmen |
| `CLAUDE.md` | **FOSSIL** (gitignored, nur lokal) | Lehrdesign-Abschnitte (Constructive Alignment, Anti-Pattern-Design, Guardrail-Regeln 1–10) — die gelten weiter | Architektur, Verzeichnisstruktur, Datenmodelle, "Geklärte Design-Entscheidungen" — beschreibt ein NIE fertig gebautes Gruppen-System |
| `TODO.md` | **FOSSIL** (seit 2026-07-09 committet, Commit `d11ca96` — vorher untracked) | Historisches Security-Review-Transkript; Verständnis, warum Commit `8b21fc1` was härtete | Als aktuelle TODO-Liste — die Punkte sind großteils behoben (Reststand: ROLLOUT_PLAN.md "Noch offen aus dem Security-Review") |
| `dev-docs/phase1/*.md` | **FOSSIL** | Historische Bau-Journale (datiert 2026-04-07) der toten Gruppen-Architektur | Als Ist-Doku für Backend-Skeleton/Agenten/Orchestrator |
| `docs/` | Forschungsreports | Teacher-Alignment-Ergebnisse (derzeit genau eine Datei, s. Abschnitt 2) | — |
| `data/prolific_runs/README.md` | gültig | Ablage-Konvention für lokale (gitignorte) Forschungsdaten: `raw/<batch>/`, `manifests/`, `derived/` | — |
| `.claude/skills/*/SKILL.md` | gültig | Diese Skill-Library — BEHOBEN (2026-07-09): committet (`26eedc4` mit 15 Skills, `d11ca96` ergänzt `toadapt-knowledge-tracing` und `toadapt-tutor-response-evaluation` → 17 Skills) | — |

Begriffserklärung: "Fossil" = ein Dokument, das einen früheren, inzwischen
verworfenen Projektzustand beschreibt und absichtlich NICHT gepflegt wird.
Fossile werden weder gelöscht (historischer Wert) noch aktualisiert (das würde
sie als aktuell tarnen).

### Warum CLAUDE.md Fossil ist (Kurzfassung)

CLAUDE.md beschreibt ein WebSocket-Gruppenchat-System mit GroupMemory, RAG und
TP-Progression. Dieses System wurde am 2026-04-30 verworfen (Commit `8df4cfd`
"refactor: individual transfer trainer architecture"); heute ist ToAdapt ein
Single-User-Trainer ohne Gruppen, ohne WebSockets, ohne RAG. CLAUDE.md ist
zudem seit 2026-04-07 gitignored (`.gitignore` Zeile 8) — es existiert nur
lokal. **Ausnahme:** Die Lehrdesign-Abschnitte (keine Framework-Namen
studierendensichtbar, keine Musterlösungen, ON Running / NORDIC HOME tabu)
sind weiterhin harte Constraints des Projekts. Details zur Pivot-Geschichte:
`toadapt-failure-archaeology`.

### ROLLOUT_PLAN.md: die Status-Block-Konvention

Der Plan hat GENAU EINEN datierten Status-Block — ein Markdown-Blockquote
direkt unter der Überschrift "## Phase 0", der den Erledigungsstand ALLER
Phasen zusammenfasst. (Nicht verwechseln mit dem seit 2026-07-09
zusätzlichen Verweis-Blockquote in Zeile 3: "Operativer Ablauf zum breiten
Rollout: siehe ROLLOUT_CHECKLIST.md" — der ist kein Status-Block.)

```markdown
> **Status 2026-07-08 (abends):**
> - **Phase 0:** erledigt bis auf …
> - **Phase 1:** Code komplett (Commit 0248921). Offen: …
> - **Phase 2:** … erledigt. Offen: …
> - **Phase 3:** komplett offen …
```

Prüfe beim Aktualisieren:
1. Datum im Block UND in der Kopfzeile (`# ToAdapt — Rollout-Plan (Stand …)`)
   auf heute setzen.
2. Erledigte Punkte mit Commit-Hash belegen (Beobachtete Praxis: "Code
   komplett (Commit 0248921)").
3. Den Phasen-Fließtext darunter NICHT umschreiben — er beschreibt den Plan,
   der Block beschreibt den Stand.
4. Eigener Commit mit Präfix `Rollout-Plan:` (Beispiele in der Historie:
   `3ca3183 Rollout-Plan: Phase-0-Status ergänzt`, `2f7f15d Rollout-Plan:
   Status nach Phase 1+2-Teilumsetzung aktualisiert`).

### README.md: bekannte Fehler (Stand: 2026-07-09, alle weiterhin vorhanden)

Die README ist der Einstieg, enthält aber verifiziert falsche Aussagen.
Korrigiere sie, wenn du ohnehin in der README arbeitest — bis dahin: nicht
zitieren.

| README-Stelle | Behauptet | Wahr ist |
|---|---|---|
| Architektur-Diagramm ("REST + WebSocket") + API-Tabelle (`WS /ws/{session_id}`) | Es gibt einen WebSocket-Chat | Chat ist **HTTP POST** `/sessions/{id}/chat` (`backend/api/routes.py`, Kommentar Zeile 185: "zuverlässiger als WebSocket durch Railway-Proxy"). Das Feld `websocket_url` in `SessionResponse` (`backend/models/session.py:39`) ist tot — kein WS-Handler existiert. |
| Tech-Stack-Tabelle: "LLM: Anthropic API (claude-sonnet-4-6)" | Anthropic-SDK direkt | **OpenAI-SDK gegen OpenRouter** (`backend/llm.py`: `AsyncOpenAI`, Base-URL `openrouter.ai/api/v1`, Default-Modell `anthropic/claude-sonnet-4.5` via Env `OPENROUTER_MODEL`) |
| Abschnitt "Aktueller Stand": Pfade unter `data/prolific_runs/derived/aligned_rescores/…` | Dateien lägen dort | `data/prolific_runs/` ist komplett gitignored und wurde am 2026-07-08 geleert: echte Teilnehmerdaten liegen in `~/ToAdapt_sensitive_data/` (NIEMALS zurückkopieren/committen). Die README-Pfade sind auf einem frischen Clone tot. Gleiches gilt für den Default-Pfad in `scripts/retry_technical_fallback_scores.py` (Zeile ~20–27). |
| Tech-Stack: "Scoring Storage: JSON" / "Experiment Logging: Optional MongoDB" | Datei primär | Seit Phase 1 (Commit `0248921`) ist **MongoDB primärer Store** (wenn konfiguriert), Datei nur Dev-Fallback |

---

## 2. Report- und Artefakt-Konventionen (Forschungs-Pipeline)

### Alignment-Reports in `docs/`

Namensschema: `teacher_alignment_report_YYYYMMDD_<n>submissions.md`
— `<n>` = Anzahl Submissions im Scope.

**Warnbeispiel (real passiert):** Die einzige existierende Datei heißt
`docs/teacher_alignment_report_20260531_17submissions.md`, der Inhalt sagt
aber "16 vollstaendige Abgaben" und "Eindeutige Submissions im Scope: 16"
(eine Submission fiel beim Scope-Schnitt raus, der Dateiname wurde nicht
nachgezogen). Regel daraus: **Scope-Zahl in Dateiname, H1-Titel und
Scope-Abschnitt müssen identisch sein — prüfe alle drei vor dem Commit.**

Pflicht-Struktur eines Alignment-Reports (am Bestand orientiert):
`# Titel mit n` → `Stand: YYYY-MM-DD` → `## Scope` (Ein-/Ausschlusskriterien,
Item- und Submission-Zahl) → `## Gesamtvergleich` (Tabelle vor/nach:
Pearson r, MAE, RMSE, Mean Diff, within-1/2-Punkt) → `## Nach Frage`
(q1–q4 einzeln) → Signale (Review-Flags, technical_fallbacks, Confidence,
Score-Bands) → `## Interpretation`.

### IDs und Timestamps in Pipeline-Artefakten

| Konvention | Format | Quelle (verifiziert) |
|---|---|---|
| `review_item_id` | `{case_id}:{question_id}:{nnn}` — `nnn` = 3-stelliger, pro (Case, Frage)-Blatt laufender Zähler, z.B. `hsg-tp1-001:q3:007` | `scripts/export_review_workbooks.py:178` (`f"{case_id}:{question_id}:{sheet_counters[key]:03d}"`) |
| Datei-Timestamps | **UTC**, kompakt: `%Y%m%dT%H%M%SZ` (z.B. `20260531T140830Z`) | `export_review_workbooks.py:627`, `import_prolific_runs.py:34` |
| Metadaten-Timestamps | **UTC**, ISO: `datetime.now(timezone.utc).isoformat()` im Feld `exported_at_utc` bzw. `imported_at` | `export_review_workbooks.py:574`, `compare_teacher_rubric_scores.py:325` |
| Review-Workbooks | `{prefix}_{timestamp}_rubric.xlsx`, `…_blind.xlsx`, `…_chat_turns.xlsx` | `export_review_workbooks.py:628-630` |
| Vergleichs-Output | `{prefix}.xlsx` (5 Blätter) + `{prefix}_item_comparison.csv` — CSV ist **Semikolon-getrennt** | `compare_teacher_rubric_scores.py:393-394,468` |

Regeln:
- Neue Pipeline-Skripte verwenden IMMER `datetime.now(timezone.utc)` — nie
  lokale Zeit, nie das deprecatete `datetime.utcnow()`.
- `review_item_id` ist der Join-Schlüssel zwischen Blind-Workbook
  (Lehrkraft-Bewertung) und Rubric-Workbook (Judge-Scores) — niemals
  umbenennen oder das Format ändern, ohne beide Exportpfade UND
  `compare_teacher_rubric_scores.py` anzufassen.
- Das Lehrer-Workbook ist beim Vergleich KANONISCH: Zeilen, die nur im
  Rubric-Workbook existieren, werden by design ausgeschlossen (Docstring
  `compare_teacher_rubric_scores.py:4` — bereinigte Testuser sollen nicht
  zurückkehren).

---

## 3. Haus-Stil

### Sprache

| Textsorte | Sprache |
|---|---|
| Doku (README, ROLLOUT_PLAN, docs/, Skills) | **Deutsch** (Code/Kommandos/Fachbegriffe englisch, wo üblich) |
| Commit-Messages | **Deutsch**, beschreibend |
| Code-Kommentare & Docstrings | Deutsch (Beispiel: `backend/llm.py` Docstring, Kommentare in `api/routes.py`) |
| Code-Identifier | Englisch |
| Produkttexte (UI, Agenten-Prompts, Feedback) | **DE + EN**, umschaltbar (s.u.) |

### Quellen-Attribution im Code (harte Owner-Regel, seit 2026-07-09)

Jede Code-Datei, die eine Methode/ein Framework aus einer EXTERNEN Quelle
umsetzt, nennt die Quelle **oben im Modul-Docstring**: Paper (Autoren,
Venue, Jahr), Repo-URL, Lizenz — plus die Klarstellung, ob Code übernommen
oder nur die **Methode nachimplementiert** wurde (lizenzrelevant: z.B.
`github.com/Simon-tan/IKT` hat KEINE Lizenz → Methode frei, Code-Kopie
nicht). Rationale der Ownerin: "wir wollen nichts verschweigen" —
wissenschaftliche Redlichkeit, das Projekt zielt auf Publikationen.
Vorbilder: `backend/evaluator/tutor_eval.py`,
`scripts/evaluate_tutor_responses.py` (Maurya et al., NAACL 2025,
CC BY-SA 4.0).

### Commit-Messages

- Beschreibend-deutsch, Scope-Präfix wo sinnvoll (`CI:`, `Rollout-Plan:`,
  `Dashboard:`, `Phase 1:`, `Security-Härtung:`) — siehe `git log --oneline`.
- **KEINE AI-Attribution** (kein "Co-Authored-By: Claude", kein "Generated
  with…") — harte Owner-Regel, gilt für Commits UND PRs. Die Historie
  enthält genau einen Alt-Bestand-Treffer (`8b21fc1`, Security-Härtung
  2026-07-07, vor Einführung der Regel — kein Präzedenzfall); neue Commits
  bleiben attributionsfrei.
- Die Historie enthält abschreckende Gegenbeispiele (`.`, `fix cache`,
  `abgaben aktualisiert`) — NICHT imitieren; die neuere Konvention
  (beschreibend, seit Juli 2026) gilt.
- Gate-Fragen vor jedem Commit (welche Prüfung wann Pflicht ist):
  `toadapt-change-control`.

### i18n-Muster (DE/EN im Produkt)

Es gibt KEIN i18n-Framework (kein next-intl, keine JSON-Message-Dateien).
Das Muster ist handgerollt und dreiteilig:

1. **`frontend/lib/i18n.ts`** — Utilities: Typ `Locale = 'de' | 'en'`,
   `DEFAULT_LANGUAGE = 'de'`, sessionStorage-Persistenz
   (`LANGUAGE_STORAGE_KEY`), Custom-Event `toadapt:language-changed`,
   Ableitung der Sprache aus der Case-ID (`languageFromCaseId`: Suffix `-en`
   ⇒ Englisch).
2. **Per-Page-Copy-Objekte** — jede Seite/Komponente hält ihre Strings als
   `Record<Locale, …>`-Konstante im eigenen File (z.B. `NAV_TEXT` in
   `frontend/components/Nav.tsx:27`, `TP_LABEL` in
   `frontend/app/cases/page.tsx:20`, `AGENT_LABEL` und
   `BUSINESS_MODEL_CANVAS_BLOCKS` in `frontend/app/cases/[id]/page.tsx`).
   Aktive Sprache kommt aus dem Hook `useLanguage()`
   (`frontend/lib/useLanguage.ts`).
3. **Backend-Texte** — Agenten-System-Prompts existieren doppelt in
   `backend/agents/orchestrator.py`: `AGENT_PROMPTS` (DE) und
   `AGENT_PROMPTS_EN` (Zeile 190); Guardrail-Fallback-Texte via
   `_guardrail_fallback(agent_type, language)` (Zeile 315). Sprachwahl:
   EN wenn `experiment.metadata.language == "en"` ODER Case-ID auf `-en`
   endet.

**Die eine Regel:** Wer einen Text hinzufügt oder ändert, pflegt **beide
Sprachobjekte im selben Commit**. Es gibt keinen Compiler-Check, der fehlende
EN-Keys meldet (`satisfies Record<Locale, …>` prüft nur die Locale-Ebene,
nicht die Key-Parität der inneren Objekte bei getrennten Strukturen) —
Disziplin ersetzt Tooling. Studierendensichtbare Texte unterliegen zusätzlich
den Lehrdesign-Constraints (keine Framework-Namen, keine Musterlösungen) —
in BEIDEN Sprachen; Details: `bwl-scaffolding-reference`.

---

## 4. Checkliste: Doku nach einer Änderung

Führe nach jeder Code-Änderung diese Zuordnung durch:

| Du hast geändert… | Aktualisiere… |
|---|---|
| Einen Rollout-Phasen-Punkt erledigt | `ROLLOUT_PLAN.md` Status-Block (Datum + Commit-Hash), eigener `Rollout-Plan:`-Commit |
| Endpoint hinzugefügt/geändert/entfernt | README-API-Tabelle (und nutze die Gelegenheit, einen der bekannten README-Fehler aus Abschnitt 1 mit zu korrigieren) |
| Env-Variable neu/umbenannt/entfernt | `.env.example` + Provenance-Abschnitt der Skill `toadapt-config-and-flags` |
| Judge/Evaluator/Kalibrierungsanker | Alignment-Recheck fahren (Pflicht-Gate, s. `toadapt-change-control`), danach neuen Report in `docs/` nach Namensschema aus Abschnitt 2 |
| Agent-/Formative-Feedback-Prompt geändert | Pädagogischen Regressionsnachweis fahren (Pflicht, s. `toadapt-tutor-response-evaluation`); beide Sprachobjekte synchron halten |
| Forschungs-Skript (Verhalten/CLI) | Docstring im Skript + zugehörigen README-Abschnitt ("Review-Exporte", "Lokale Prolific-Exporte", "Bewertungen ins Lehrkräfte-Dashboard übertragen") |
| Studierendensichtbaren Text (UI/Prompt/Feedback) | Beide Sprachobjekte (DE+EN) synchron, im selben Commit |
| Eine Architektur-Entscheidung getroffen/revidiert | Skill `toadapt-architecture-contract` (Entscheidung + WARUM + Commit) |
| Etwas, das eine Skill-Aussage falsch macht | Betroffene Skill in `.claude/skills/` (s. Abschnitt 5) |
| **NIEMALS aktualisieren:** | `CLAUDE.md`, `TODO.md`, `dev-docs/phase1/` — Fossile bleiben eingefroren. Wenn ihre Existenz verwirrt: einen Fossil-Hinweis an den DATEIANFANG setzen ist erlaubt, Inhalt umschreiben nicht. |

---

## 5. Pflege dieser Skill-Library

Die Library liegt unter `.claude/skills/<skill-name>/SKILL.md`.
BEHOBEN (2026-07-09): Die zunächst untrackte Library ist committet —
`26eedc4` (15 Skills) und `d11ca96` (ergänzt `toadapt-knowledge-tracing`
für Lernverläufe/Mastery und `toadapt-tutor-response-evaluation` für die
NAACL-basierte Tutor-Antwort-Qualität; Stand: 17 Skills).

Prinzipien:
1. **Jeder Fakt hat genau EIN Zuhause.** Bevor du etwas in eine Skill
   schreibst, prüfe per Inventar (die Beschreibungen der Geschwister-Skills),
   ob der Fakt schon woanders lebt — dann querverweisen statt duplizieren.
2. **Jede Skill endet mit `## Provenance und Wartung`:** Erstellungsdatum
   plus pro drift-anfälligem Fakt ein einzeiliges
   Re-Verifikations-Kommando (grep/ls/git log).
3. **Wartungsroutine** (nach größeren Repo-Änderungen oder bei Verdacht auf
   Drift): Öffne die betroffene Skill, führe ihre Re-Verifikations-Kommandos
   aus, korrigiere abweichende Aussagen, aktualisiere den "Stand:"-Stempel
   der geänderten Fakten.
4. **Datums-Stempel:** Veränderliche Fakten tragen "Stand: YYYY-MM-DD";
   was ohne Stempel dasteht, muss zeitlos wahr sein (z.B. ein Dateiformat
   nur solange der Code-Verweis daneben steht).
5. **Ehrlichkeit:** Unverifiziertes als UNVERIFIZIERT markieren oder
   weglassen. Kein Fakt aus dem Gedächtnis — immer gegen das Repo prüfen.

---

## Provenance und Wartung

Erstellt: 2026-07-08. Alle Pfade, Zeilennummern und Behauptungen am
2026-07-08 gegen das Repo verifiziert.

Update 2026-07-09 (HEAD 64b62f9): ROLLOUT_CHECKLIST.md als massgebliches
operatives Dokument (Gate-Workflow W0–W6) in die Hierarchie aufgenommen,
ROLLOUT_PLAN.md als Hintergrund-Referenz eingestuft; Skill-Library und
TODO.md sind jetzt committet (`26eedc4`/`d11ca96`); zwei neue Skills
(`toadapt-knowledge-tracing`, `toadapt-tutor-response-evaluation`) im
Inventar; Prompt-Änderungs-Regressionsnachweis in Checkliste verlinkt;
README-Fehler re-verifiziert (alle weiterhin vorhanden, Zeilennummern
routes.py 166→185, session.py 37→39); Report-/i18n-Anker re-verifiziert
(unverändert).

Re-Verifikations-Kommandos (vom Repo-Root ausführen):

| Fakt | Kommando |
|---|---|
| ROLLOUT_PLAN-Status-Block existiert und ist datiert | `grep -n "^> \*\*Status" ROLLOUT_PLAN.md` |
| ROLLOUT_CHECKLIST: Gates W0–W6 + Verweis im Plan | `grep -n "^## W" ROLLOUT_CHECKLIST.md && grep -n "ROLLOUT_CHECKLIST" ROLLOUT_PLAN.md` |
| CLAUDE.md ist gitignored (Fossil, lokal) | `git check-ignore -v CLAUDE.md` |
| TODO.md ist committet (Fossil) | `git ls-files TODO.md` (erwartet `TODO.md`; committet seit `d11ca96`) |
| README-Fehler: toter WS-Endpoint | `grep -n "ws/{session_id}\|WebSocket" README.md backend/api/routes.py backend/models/session.py` |
| README-Fehler: Anthropic-SDK-Zeile vs. real OpenRouter | `grep -n "Anthropic" README.md && grep -n "OPENROUTER_BASE_URL\|AsyncOpenAI" backend/llm.py` |
| README-Fehler: tote aligned_rescores-Pfade | `grep -rn "aligned_rescores" README.md scripts/ && ls data/prolific_runs/` (erwartet: nur README.md) |
| Report-Namens-/Scope-Mismatch (17 vs. 16) | `head -1 docs/teacher_alignment_report_20260531_17submissions.md` |
| review_item_id-Format | `grep -n "review_item_id = f" scripts/export_review_workbooks.py` |
| UTC-Timestamp-Konvention | `grep -n "timezone.utc" scripts/export_review_workbooks.py scripts/import_prolific_runs.py scripts/compare_teacher_rubric_scores.py` |
| Keine AI-Attribution in Commits | `git log --format='%s%n%b' \| grep -ci "co-authored"` (erwartet 1 — nur Alt-Bestand `8b21fc1`; darf nicht steigen) |
| i18n: Locale-Utilities + Copy-Objekte | `grep -n "Locale" frontend/lib/i18n.ts && grep -rn "Record<Locale" frontend/app frontend/components` |
| Backend-Prompts DE/EN | `grep -n "AGENT_PROMPTS_EN\|_guardrail_fallback" backend/agents/orchestrator.py` |
| dev-docs weiterhin nur Phase-1-Fossile | `ls dev-docs/phase1/` |
| Skill-Library committet (17 Skills) | `git ls-files .claude/skills \| grep -c SKILL.md` (erwartet 17) und `git status --porcelain .claude/` (erwartet leer) |
