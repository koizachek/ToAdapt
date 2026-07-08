---
name: toadapt-change-control
description: >
  Lade diese Skill, BEVOR du in ToAdapt irgendetwas änderst, committest, pushst
  oder deployst. Sie klassifiziert jede Änderung (studierendensichtbares
  Verhalten, Judge/Scoring, Infra/Deploy, Forschungs-Skripte) und nennt das
  jeweils verpflichtende Gate. Sie enthält die unverhandelbaren Regeln des
  Projekts mit Rationale und dem historischen Vorfall dahinter. Trigger:
  "darf ich das ändern?", Prompt-/Guardrail-/Evaluator-Änderung, Case-Freigabe,
  force/override, Commit-Message schreiben, git push, Deploy auf Railway/Vercel,
  Env-Variable scharf schalten, PII/Teilnehmerdaten, Auth-Änderung, Wortlimits,
  "quick fix auf main", --force push, Rebase/History-Umschreiben.
---

# ToAdapt Change-Control — Was darf wie geändert werden

Kontext in einem Satz: ToAdapt ist ein Einzel-Transfer-Trainer (FastAPI-Backend
auf Railway, Next.js-Frontend auf Vercel) für den BWL-A-Kurs der Universität
St.Gallen; Studierende bearbeiten AI-generierte Business-Cases, vier
Scaffolding-Agenten (Lernbegleiter, die Fragen stellen statt Antworten geben)
chatten mit ihnen, ein LLM-Judge (LLM, das Antworten nach Rubric bewertet)
vergibt Punkte. Ein Solo-Repo, direkte Pushes auf `main` — Disziplin ersetzt
Prozess. Diese Skill IST der Prozess.

## Wann diese Skill NICHT gilt

- Du willst einen Bug **diagnostizieren**, nicht ändern → `toadapt-debugging-playbook`.
- Du willst wissen, **warum** die Architektur so ist → `toadapt-architecture-contract`.
- Du willst wissen, welche **Tests/Evidenz** konkret zu schreiben sind → `toadapt-validation-and-qa`.
- Du willst die **Alignment-Kampagne** für den q4-Judge fahren → `toadapt-judge-alignment-campaign`.
- Du suchst **Env-Variablen/Flags** im Detail → `toadapt-config-and-flags`.
- Du willst die **Vorfälle in voller Chronik** → `toadapt-failure-archaeology`.
- Du willst **deployen/betreiben** (Schritt-für-Schritt) → `toadapt-run-and-operate`.

---

## 1. Änderungsklassen und ihre Gates

Klassifiziere JEDE Änderung zuerst. Bei Überschneidung gilt das strengste Gate.

| Klasse | Was fällt darunter | Gate (Pflicht, VOR Deploy) |
|---|---|---|
| **[A] Studierendensichtbares Verhalten** | Agent-System-Prompts (`backend/agents/orchestrator.py`: `AGENT_PROMPTS`, `AGENT_PROMPTS_EN`), Guardrail-Patterns (`guardrail_check`, ebd. Zeile ~113), Wortlimits (`frontend/app/cases/[id]/page.tsx` Zeilen ~311–313), Case-Inhalte/Case-Generator, Evaluator-Feedback-Text | Guardrail-Regressionstests grün (`tests/test_orchestrator_guardrails.py`) + manueller Lehrdesign-Check (Abschnitt 2.1) + bei Prompt-Änderung am Judge zusätzlich Gate B |
| **[B] Judge-/Scoring-Logik** | `backend/evaluator/rubric_evaluator.py` (`EVALUATOR_SYSTEM`, `EVALUATE_PROMPT`, Kalibrierungsanker in `_format_calibration_notes` Zeile ~155, Schwellwerte), `backend/config/rubrics/*.json`, Punkte/Bloom in Case-Fragen | Kompletter Durchlauf der Teacher-Alignment-Pipeline (Abschnitt 2.5) und Vergleich der Metriken gegen die Baseline, BEVOR die Änderung produktiv bewertet |
| **[C] Infra/Deploy** | `backend/main.py`, `railway.toml`, `Dockerfile`, `docker-compose.yml`, CI-Workflow, Env-Variablen, Auth (`backend/auth.py`), CORS, Mongo-Anbindung | CI grün + Smoke-Test gegen die laufende Instanz (`/health`, danach `/health/diagnostics` mit `X-API-Key`) |
| **[D] Forschungs-Skripte** | `scripts/*.py` (Import, Workbook-Export, Score-Vergleich, Publish, Retry) | Zugehörige Tests in `tests/` grün (es existieren Tests pro Skript, z.B. `tests/test_compare_teacher_rubric_scores.py`); bei Skripten mit echten LLM-Calls (`scripts/retry_technical_fallback_scores.py`) zuerst `--dry-run` |

Prüfe die Klassifikation praktisch: Wenn ein Studierender die Änderung im
Browser oder im Judge-Feedback bemerken KÖNNTE, ist es Klasse A (ggf. +B).

### Gate-Kommandos (copy-paste, vom Repo-Root)

```bash
# Backend-Tests (48 Tests, Stand 2026-07-08; asyncio_mode=auto via pyproject.toml)
.venv/bin/python -m pytest tests/ -q

# Nur Guardrail-Regression (Gate A)
.venv/bin/python -m pytest tests/test_orchestrator_guardrails.py -q

# Lint wie in CI (ruff ist NICHT in der lokalen venv — einmalig installieren)
.venv/bin/pip install ruff && .venv/bin/ruff check .

# Frontend wie in CI
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

---

## 2. Die Unverhandelbaren

Jede Regel hier hat einen realen Vorfall hinter sich. Keine ist verhandelbar,
auch nicht "nur für einen Test" oder "nur im Experiment-Branch".

### 2.1 Lehrdesign-Constraints — der Validator erzwingt sie, du auch

**Regel:** In studierendensichtbarem Text (Cases, Agent-Antworten,
Judge-Feedback) niemals: (a) BWL-Framework-Namen (z.B. "Porter", "VRIO",
"Five Forces" — die Modelle sollen implizit über Denkfragen vermittelt
werden), (b) Musterlösungen oder direkte Antworten, (c) Bezüge auf die
kurs-reservierten Cases **ON Running** und **NORDIC HOME** (NORDIC HOME ist
der geheime Klausur-Case).

**Rationale:** Das Lehrdesign (Constructive Alignment, pfadoffene Rubrics)
bricht zusammen, wenn das Tool Modellnamen droppt oder Lösungen liefert —
dann trainiert es Auswendiglernen statt Denken, und die Klausur-Validität
ist beschädigt.

**Enforcement im Code:** `backend/cases/validator.py` prüft beim
Case-Approve alle sichtbaren Texte gegen `forbidden_framework_names` aus
`backend/config/tp_configs.py` (plus fragen-eigene Verbotslisten) und gegen
`RESERVED_CASE_TERMS = ["ON Running", "NORDIC HOME"]`. Fehler blockieren
`POST /admin/cases/{id}/approve` mit **422 + Issue-Report**. Ein Override ist
nur bewusst möglich (`force: true` im Request-Body) und wird protokolliert:
Log-Event `case_approved` mit `forced=true` plus Vermerk
"[Freigabe trotz Validierungsfehlern erzwungen]" in den Review-Notes
(`backend/admin/routes.py`, approve-Endpoint). **Nutze `force` nie, um einen
Lehrdesign-Fehler durchzuwinken** — es existiert für Fälle, in denen der
Validator falsch-positiv anschlägt.

Agent-Antworten werden zur Laufzeit von `guardrail_check()`
(`backend/agents/orchestrator.py`) gefiltert; bei Treffer wird die Antwort
komplett durch einen Fallback-Text ersetzt und `guardrail_triggered` geloggt.
Bekannte Lücke (Stand 2026-07-08): `TP_CONFIGS[4]` hat keinen
`forbidden_framework_names`-Key — in TP4 greifen nur die globalen Patterns.
Diese Lücke ist offen dokumentiert, nicht als Freibrief zu verstehen.

### 2.2 PII-Regel — echte Teilnehmerdaten niemals ins Repo

**Regel:** Echte Teilnehmerdaten (Prolific-IDs, Matrikelnummern, echte
Freitext-Antworten) kommen NIEMALS ins Repo: nicht in Commits, nicht in
Test-Fixtures, nicht in Skills, nicht in Doku-Beispielen. Verwende
synthetische Daten. Der dokumentierte Ablageort sensibler Daten ist
`~/ToAdapt_sensitive_data/` (außerhalb des Repos).

**Der Vorfall:** Echte Prolific-Daten (Teilnehmer-IDs + Antworten) lagen in
der Git-History des zeitweise öffentlichen Repos. Am 2026-07-08 musste die
gesamte History mit `git filter-repo` über alle Branches umgeschrieben und
force-gepusht werden; die Daten wurden nach `~/ToAdapt_sensitive_data/`
verschoben (dort liegt auch das Backup-Bundle
`ToAdapt_backup_pre_filter_2026-07-08.bundle`). **Restrisiko, verifiziert am
2026-07-08:** Der GitHub-PR-Ref `refs/pull/1/head` zeigt weiterhin auf einen
Commit der alten, ungefilterten History (lokal nicht mehr auflösbar; remote
via `git ls-remote origin 'refs/pull/*'` sichtbar). Deshalb bleibt das Repo
privat, bis die PII-Fragen final geklärt sind — **das Repo nicht public
schalten.** DSGVO-/Prolific-Meldepflicht-Klärung ist organisatorisch offen.

**Praktisch:** `data/prolific_runs/**` ist gitignored (nur `README.md`
getrackt). Vor jedem Commit mit neuen Datendateien: `git status` lesen und
fragen "könnte das von einer echten Person stammen?". Niemals Inhalte aus
`~/ToAdapt_sensitive_data/` zurück ins Repo kopieren.

### 2.3 Fail-closed Auth — nie wieder offene Endpunkte

**Regel:** Geschützte Endpunkte müssen fail-closed sein: Fehlt die
Konfiguration, wird abgelehnt, nicht durchgelassen. Keine hartkodierten
Fallback-Codes, keine Default-Passwörter, kein API-Key im Browser-Bundle.

**Der Vorfall:** Bis zur Security-Härtung (Commit `8b21fc1`, 2026-07-07)
hatte das Teacher-Login einen hartkodierten Fallback-Code `'0000'`.
Chronologie (alle via `git log -S` verifizierbar): eingeführt in Commit
`8b776b0` (2026-05-31) als `const TEACHER_ACCESS_CODE = '0000'` in
`frontend/app/page.tsx` (client-seitig); `b9d8523` (gleicher Tag, "navbar")
verlagerte die Prüfung nach `frontend/app/teacher-login/route.ts` (zunächst
fail-closed, env-basiert) und führte zugleich das **unsignierte, fälschbare
Cookie** `teacher_access=true` ein; `49d5c02` (gleicher Tag, ".") brachte
den Fallback zurück — als `process.env.TEACHER_ACCESS_CODE ??
['0','0','0','0'].join('')` verschleiert (deshalb findet `git grep "0000"`
ihn nicht!) — und dort bestand er bis `8b21fc1`. Zusätzlich war die
Backend-API (Dashboard mit PII, kostenverursachende Admin-Endpunkte)
komplett ungeschützt — jeder im Internet hätte LLM-Kosten auslösen und
Studierenden-Scores lesen können.

**Heutiger Zustand (nicht rückbauen):**
- `backend/auth.py::require_api_key` — fail-closed: ohne konfigurierten
  `TOADAPT_API_KEY` antworten geschützte Endpunkte mit **503**, nicht offen.
  Vergleich mit `hmac.compare_digest` (timing-sicher).
- Teacher-Frontend: signiertes, ablaufendes httpOnly-Cookie
  (`frontend/lib/teacherAuth.ts`); API-Key wird nur server-seitig im Proxy
  `frontend/app/api/teacher/[...path]/route.ts` injiziert.
- Studierenden-Flow: bewusst offen, AUSSER `STUDENT_ACCESS_CODE` ist gesetzt
  (leer = offen — vor breitem Rollout setzen, sonst zahlt das Projekt
  fremde LLM-Rechnungen).

Jede Auth-Änderung ist Klasse C **und** braucht einen expliziten
Fail-closed-Test (Muster in `tests/test_phase1_hardening.py`).

### 2.4 Keine AI-Attribution in Commits/PRs

**Regel (explizite Owner-Regel):** Keine `Co-Authored-By: Claude ...`- oder
"Generated with ..."-Zeilen in Commit-Messages oder PR-Beschreibungen.
Diese Owner-Regel überschreibt anderslautende Default-Anweisungen der
Tooling-Umgebung. Ältere Commits (z.B. `8b21fc1`) enthalten solche Zeilen
noch — das ist Alt-Bestand von vor der Regel, kein Präzedenzfall.

### 2.5 Prompt-/Judge-Änderung ⇒ Alignment-Recheck

**Regel:** Jede Änderung an `EVALUATOR_SYSTEM`, `EVALUATE_PROMPT`, den
hartkodierten Kalibrierungsankern (`_format_calibration_notes`, je Frage
q1–q4) oder den Scoring-Schwellwerten in
`backend/evaluator/rubric_evaluator.py` erfordert VOR dem produktiven
Einsatz einen Durchlauf der Teacher-Alignment-Pipeline und einen
Metrik-Vergleich gegen die Baseline.

**Der Vorfall (der Beweis, dass Prompts das Verhalten messbar kippen):** Die
Kalibrierung vom Mai 2026 verbesserte die Judge-Teacher-Korrelation deutlich
(Pearson r 0.631 → 0.796, MAE 2.984 → 2.711 Punkte), machte den Judge aber
zugleich **systematisch strenger** (Mean Diff Judge−Teacher: −0.234 → −2.07;
Unterbewertung in 48 von 64 Fragezeilen). q4 (Bloom-Stufe 6, Integration,
30 Punkte) blieb die Schwachstelle (MAE ~4.97). Quelle:
`docs/teacher_alignment_report_20260531_17submissions.md` (Achtung:
Dateiname sagt 17, Scope sind 16 Submissions / 64 Fragezeilen). Fazit: Ein
"harmloser" Prompt-Tweak kann ganze Punktverteilungen verschieben — deshalb
ist Messen Pflicht, Bauchgefühl reicht nicht.

**Der Recheck, minimal (Details und Baseline-Interpretation in
`toadapt-judge-alignment-campaign`):**

```bash
# 1. Review-Workbooks aus vorhandenen Submissions exportieren
python scripts/export_review_workbooks.py \
  --submissions <pfad/zu/submissions.json> --events <pfad/zu/events.json>

# 2. Bewertete Lehrer-Workbook gegen Judge-Workbook vergleichen
python scripts/compare_teacher_rubric_scores.py \
  --teacher-workbook <teacher.xlsx> --rubric-workbook <rubric.xlsx>
```

Vergleiche Pearson r, MAE und Mean Diff mit den Baseline-Werten oben. Wird
irgendein Wert schlechter, geht die Änderung nicht live.

---

## 3. Solo-Workflow: main-Pushes, CI als einziges technisches Gate

Fakten (verifiziert 2026-07-08): Solo-Autorin, direkte Pushes auf `main`,
keine Branch Protection (auf privaten Free-Plan-Repos technisch gar nicht
verfügbar), keine PR-Pflicht. Einziges automatisches Gate ist die CI
(`.github/workflows/ci.yml`, läuft bei jedem Push auf `main` und bei PRs):
Backend ruff + pytest (Python 3.11, `PYTHONPATH=.`), Frontend eslint +
`tsc --noEmit` + `next build` (Node 22).

Was das an Disziplin bedeutet:

1. **CI nie rot lassen.** Es gibt niemanden, der einen roten `main` bemerkt
   außer dir. Nach jedem Push den Actions-Status prüfen:
   `gh run list --limit 3`. Rot = sofort fixen oder revert
   (`git revert <sha>`), nichts obendrauf stapeln.
2. **Lokal das laufen lassen, was CI läuft** (Kommandos in Abschnitt 1) —
   CI ist das Gate, nicht der Testrunner.
3. **Kein `git push --force` auf `origin`.** Einzige dokumentierte Ausnahme
   war die filter-repo-History-Bereinigung am 2026-07-08 (Abschnitt 2.2).
   Eine erneute History-Umschreibung braucht denselben Anlass (PII/Secrets
   in der History) und vorher ein Backup-Bundle
   (`git bundle create <ziel>.bundle --all`).
4. **Kein History-Umschreiben bereits gepushter Commits** (Rebase/Amend nur
   lokal vor dem Push). Der Rebase-Unfall vom Juni 2026 hat duplizierte
   Commits in der History hinterlassen (via Merge `764e89a` / PR #2
   aufgelöst) — nicht wiederholen.
5. **Riskante Mehrtages-Arbeiten** (z.B. Judge-Umbau) dürfen auf einen
   Branch; gemergt wird trotzdem nur mit grüner CI und erfülltem Klassen-Gate.

---

## 4. Checkliste: Vor jedem Push

Führe aus bzw. prüfe, in dieser Reihenfolge:

- [ ] Änderung klassifiziert (A/B/C/D)? Strengstes zutreffendes Gate erfüllt?
- [ ] `git status` + `git diff --stat` gelesen: keine echten Teilnehmerdaten,
      keine Secrets/`.env`, keine Dateien aus `~/ToAdapt_sensitive_data/`?
- [ ] `.venv/bin/python -m pytest tests/ -q` → alles grün (48 Tests, Stand 2026-07-08)
- [ ] `.venv/bin/ruff check .` → sauber (E402-Ignores für `backend/main.py`
      und `backend/db/submission_store.py` sind beabsichtigt — `load_dotenv`
      muss dort vor den Imports laufen; nicht "aufräumen")
- [ ] Bei Frontend-Änderung: `cd frontend && npm run lint && npx tsc --noEmit && npm run build`
- [ ] Bei Klasse A: `tests/test_orchestrator_guardrails.py` grün + Selbstfrage
      "kann irgendein sichtbarer Text jetzt Framework-Namen, Lösungen oder
      ON Running/NORDIC HOME enthalten?"
- [ ] Bei Klasse B: Alignment-Recheck gelaufen, Metriken nicht schlechter (Abschnitt 2.5)
- [ ] Commit-Message: Deutsch (Projektkonvention), beschreibt das WARUM,
      **keine AI-Attribution** (Abschnitt 2.4)
- [ ] Nach dem Push: `gh run list --limit 1` → CI grün abwarten

## 5. Checkliste: Vor jedem Deploy-scharf-schalten

"Scharf schalten" = eine Env-Variable in Railway/Vercel setzen/ändern oder
einen Deploy in eine Umgebung bringen, die echte Nutzer trifft.

- [ ] CI auf dem zu deployenden Commit grün?
- [ ] `TOADAPT_API_KEY` in Backend (Railway) **und** Frontend (Vercel,
      server-only) identisch gesetzt? (Ohne Key: geschützte Endpunkte
      antworten 503 — fail-closed, aber Dashboard/Admin sind dann tot.)
- [ ] `STUDENT_ACCESS_CODE` gesetzt, wenn die Instanz öffentlich erreichbar
      ist? (Leer = jeder kann LLM-Kosten auslösen.)
- [ ] `ALLOWED_ORIGINS` auf die echte Frontend-Domain gesetzt (leer =
      nur localhost)?
- [ ] MongoDB konfiguriert und erreichbar? Railway-Dateisystem ist EPHEMER —
      ohne Mongo sind Submissions nach dem nächsten Redeploy weg.
- [ ] `WEB_CONCURRENCY` > 1 NUR wenn Mongo verifiziert läuft (sonst
      Session-404s zwischen Workern; Warnung steht in `railway.toml`).
- [ ] Smoke-Test nach Deploy:
      ```bash
      curl -fsS https://<backend-host>/health
      curl -fsS -H "X-API-Key: $TOADAPT_API_KEY" https://<backend-host>/health/diagnostics
      ```
      Diagnostics muss den Mongo-Status als verbunden zeigen.
- [ ] Ein studierendensichtbarer Klick-Test im Frontend: Case öffnen, eine
      Chat-Nachricht senden, prüfen dass die Antwort eine Frage ist (kein
      Lösungstext, kein Framework-Name).
- [ ] Bei Klasse-A/B-Änderung im Deploy: die jeweiligen Gates waren VOR dem
      Deploy erfüllt, nicht "wird nachgeholt".

---

## Provenance und Wartung

Erstellt: 2026-07-08, gegen den damaligen Stand des Repos verifiziert
(Tests: 48 grün; CI-Workflow, Validator, Auth, Alignment-Report,
Git-History-Fakten einzeln geprüft). Drift-anfällige Fakten und ihr
Re-Verifikations-Kommando (vom Repo-Root):

| Fakt (Stand 2026-07-08) | Re-Verifikation |
|---|---|
| 48 Backend-Tests, alle grün | `.venv/bin/python -m pytest tests/ -q` |
| Approve-Gate: 422 + `force`-Override, geloggt | `grep -n "force\|422\|case_approved" backend/admin/routes.py` |
| Reservierte Case-Namen im Validator | `grep -n "RESERVED_CASE_TERMS" backend/cases/validator.py` |
| `require_api_key` fail-closed (503) | `grep -n "503\|SERVICE_UNAVAILABLE" backend/auth.py` |
| TP4 ohne `forbidden_framework_names` (Lücke) | `grep -c "forbidden_framework_names" backend/config/tp_configs.py` (3 = Lücke besteht) |
| Kalibrierungsanker hartkodiert q1–q4 | `grep -n "_format_calibration_notes" backend/evaluator/rubric_evaluator.py` |
| Alignment-Baseline r 0.631→0.796, q4-Schwäche | `grep -n "Pearson\|q4" docs/teacher_alignment_report_20260531_17submissions.md` |
| CI-Schritte (ruff/pytest/eslint/tsc/build) | `cat .github/workflows/ci.yml` |
| Wortlimits im Frontend (Zeilen ~311–313) | `grep -n "minWords" "frontend/app/cases/[id]/page.tsx"` |
| Alter PR-Ref zeigt noch auf Pre-Filter-History | `git ls-remote origin 'refs/pull/*'` und Hash lokal mit `git cat-file -t <hash>` prüfen (Fehler = Ref hängt noch an alter History) |
| `data/prolific_runs` gitignored | `grep -n "prolific" .gitignore` |
| Keine Branch Protection möglich/aktiv | `gh api repos/koizachek/ToAdapt/branches/main/protection` (403/404 = keine) |
