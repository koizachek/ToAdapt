# Rollout-Workflow: To:Adapt für ~2.000 Studierende + 40 Tutor:innen

Stand: 2026-07-09. Gate-basierter Ablauf — eine Phase gilt erst als
abgeschlossen, wenn ihr GATE messbar erfüllt ist. Verantwortlich:
**[O]** = Ownerin (extern/orga), **[C]** = Code-Session (Claude/Entwicklung),
**[G]** = gemeinsam. Hintergrund und Historie: ROLLOUT_PLAN.md;
Betriebs-Runbooks: `.claude/skills/toadapt-run-and-operate` u.a.

Bereits erledigt (Code, Stand heute): Security-Härtung, Mongo-Stores,
LLM-Härtung, Rate-Limiting, CI, Case-Editor mit Freigabe-Gate, Case-Pakete
(eingebettete Rubrics, Glossar, Guidance, Wortlimits), Fehlerquellen- und
Gruppen-Dashboard, Pseudonymisierung, Tutor-Einzelcodes, TP-Progression,
formative Live-Unterstützung + Paste-Telemetrie, Tutor-Antwort-Evaluation
(NAACL-Taxonomie), Skill-Library.

---

## W0 — Produktion scharf schalten  [O]  (~1–2 h)

- [ ] Railway-Variablen setzen:
      `STUDENT_ACCESS_CODE` (Kohorten-Code), `PSEUDONYM_SECRET`,
      `RESEARCH_API_KEY`, `ENVIRONMENT=production`,
      `ALLOWED_ORIGINS=https://<prod-frontend-domain>`,
      optional `SENTRY_DSN`.
      Secrets erzeugen: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Tutor-Codes erzeugen und in Vercel setzen:
      `python scripts/generate_tutor_codes.py --count 40 --csv tutor_codes.csv`
      → `TEACHER_ACCESS_CODES` (Vercel, server-only). CSV sicher ablegen
      (~/ToAdapt_sensitive_data/), alten `TEACHER_ACCESS_CODE` entfernen.
- [ ] Deploy abwarten, dann verifizieren:
      `bash .claude/skills/toadapt-diagnostics-and-tooling/scripts/smoke_backend.sh https://<railway-url> <TOADAPT_API_KEY>`
- [ ] `GET /health/diagnostics` (mit X-API-Key): `mongo_logging_enabled=true`?
      Startup-Log: `pseudonymization_enabled=true`, KEIN `student_flow_open`,
      KEIN `pseudonymization_disabled`.
- [ ] Erst DANACH: `WEB_CONCURRENCY=2` setzen (Sessions liegen sonst nur im
      Worker-Speicher → Chat-404s).
- [ ] OpenRouter: Budget-Alert im Provider-Dashboard setzen.

**GATE W0:** Smoke-Skript 6/6 PASS gegen Produktion; Diagnostics zeigt
Mongo verbunden; Startup-Log ohne die zwei Warnungen.

---

## W1 — Staging + Lasttest  [G]  (~2–3 Tage)

- [ ] [O] Staging anlegen: zweites Railway-Environment + Vercel-Preview,
      eigene Mongo-DB (`MONGODB_DATABASE=toadapt_staging`), eigener
      OpenRouter-Key MIT hartem Budget-Limit.
- [ ] [C] Mongo-Indexe anlegen (Skript schreiben + in Staging ausführen):
      `sessions.session_id`, `submission_states.submission_id`,
      `dashboard_results.{submission_id, matrikelnummer, group_code}`,
      `cases.case_id`, `experiment_events.{event_type, created_at}`.
- [ ] [C] Lasttest-Skript (z.B. locust): 300 gleichzeitige Studierende
      (Session anlegen → 5 Chat-Turns → Antworten speichern → Submit),
      LLM gemockt via Staging-Env `OPENROUTER_BASE_URL` auf Stub ODER
      kleines `LLM_MAX_CONCURRENCY`; zusätzlich 20 reale Submits als
      Quota-/Kosten-Probe. Parallel: 40 Tutor-Sessions auf
      `/dashboard/groups` (Dashboard lädt alle Ergebnisse pro Request —
      beobachten, ggf. Caching nachrüsten).
- [ ] [G] Ergebnisse dokumentieren: p95-Latenz Chat < 10 s, Submit < 30 s,
      keine 5xx-Serie, Rate-Limiter greift wie konfiguriert, Kosten pro
      simuliertem Studierenden notieren (Hochrechnung × 2.000).

**GATE W1:** Lasttest-Protokoll liegt vor, alle Schwellen eingehalten oder
Gegenmaßnahme umgesetzt und Test wiederholt.

---

## W2 — Content-Readiness: Case-Pool  [G]  (~1 Woche, parallel zu W1)

- [ ] [C] `--case-id`-Filter für `scripts/export_review_workbooks.py`
      (Blind-Nachkalibrierung pro neuem Case in einem Befehl).
- [ ] [O] Pro TP mindestens 2 Cases generieren + im Editor kuratieren
      (Prüfkriterien/Keywords/Glossar sind der Review-Gegenstand, nicht nur
      der Fließtext!) + freigeben. Validator-Warnungen ernst nehmen
      (fehlende Canvas-Blöcke = Alpes-Fallback; Glossar-Begriffe müssen
      wörtlich im Text stehen).
- [ ] [O] Pro neuem Case Nachkalibrierung: 5–10 echte/Pilot-Antworten blind
      bewerten (Workbook-Pipeline), Judge-Abweichung prüfen; bei
      systematischer Abweichung nur die case-spezifischen
      `calibration_notes` im Editor nachschärfen (Klasse B: danach
      Vergleich erneut rechnen).

**GATE W2:** Für TP1 (Kursstart) ≥ 2 freigegebene, nachkalibrierte Cases;
Fahrplan für TP2–TP4 terminiert.

---

## W3 — Qualitäts-Baselines  [G]  (~2–3 Tage, parallel)

- [ ] [G] Tutor-Antwort-Evaluation Baseline: Event-Export ziehen, dann
      `python scripts/evaluate_tutor_responses.py --events <export> --limit 50`
      + `--annotation-workbook` für ~30 Turns Human-Spot-Check.
      Judge-vs-Mensch-Übereinstimmung dokumentieren; Desirability-Quoten
      pro Agent als Regressions-Baseline festhalten (v.a.
      revealing_of_the_answer).
- [ ] [O] q4-Judge-Kampagne terminieren (Skill:
      `toadapt-judge-alignment-campaign`) — nicht rollout-blockierend,
      aber der Judge speist studierendensichtbares Feedback.

**GATE W3:** Baseline-Zahlen (Tutor-Eval + Alignment) versioniert abgelegt
(docs/ bzw. data/prolific_runs/derived/), Regressionspflicht in
Change-Control damit scharf.

---

## W4 — Orga, Datenschutz, Onboarding  [O]  (parallel starten, längste Laufzeit!)

- [ ] Datenschutz-Klärung: Verarbeitung pseudonymisierter Studierenden-
      Daten + Antworttexte an OpenRouter (US) — Uni-Datenschutzstelle,
      Studierenden-Information, ggf. AVVs (Railway/Vercel/Atlas/OpenRouter).
      Altlast: Prolific-Meldepflicht-Entscheidung dokumentieren.
- [ ] Gruppenliste festlegen (Nummernschema G1…Gn) und an Studierende
      kommunizieren (Selbstauskunft beim Login — Tippfehler erscheinen als
      eigene Gruppe in der Tutor-Liste, Konvention klar kommunizieren!).
- [ ] Tutor-Onboarding (1 Seite + 15-min-Demo): Login mit Einzelcode,
      Gruppen-Dashboard lesen (Ampel, „x von y unter Schwelle",
      Paste-Anteil = HINWEIS nicht Beweis), Case-Editor + Freigabe-Gate.
- [ ] Studierenden-Kommunikation: Zugangscode, Gruppen-Nr., was das Tool
      ist/nicht ist (To:Adapt-Wording), Privacy-Zusage.
- [ ] Support-/Incident-Weg: wer reagiert, wo wird geschaut
      (Railway-Logs, /health/diagnostics, Sentry), Eskalation.

**GATE W4:** Datenschutz-Freigabe liegt vor (BLOCKIEREND für W6);
Onboarding-Material verteilt.

---

## W5 — Pilot  [G]  (~1 Woche, nach W0–W2)

- [ ] 2–3 echte Übungsgruppen (~15 Studierende) + 2–3 Tutor:innen für
      einen TP1-Case durch den vollen Zyklus: Login → Chat → Denkanstöße →
      Submit → Ergebnisseite → Gruppen-Dashboard → Präsenz-Assessment.
- [ ] Messen statt fragen: Kosten/Studierende:r, technical_fallback-Quote
      (< 5 %), guardrail_triggered-Rate, Denkanstoß-Nutzung,
      Session-Dauer; danach 3 Fragen an Pilot-Tutor:innen (War die
      Gruppen-Sicht handlungsleitend?).
- [ ] Befunde triagieren: Blocker fixen → Kurz-Retest; Rest ins Backlog.

**GATE W5:** Kein offener Blocker aus dem Pilot; Kosten-Hochrechnung
× 2.000 im Budget; Tutor:innen bestätigen Nutzbarkeit der Gruppen-Sicht.

---

## W6 — Breiter Rollout  [G]  (Kursstart 2026-09-14)

- [ ] Vorwoche: W0-Smoke erneut gegen Produktion; Mongo-Backup aktiv?
      Budget-Alerts scharf? Tutor-Codes verteilt (CSV → einzeln, nicht als
      Sammelmail)?
- [ ] Rollout gestaffelt, wenn möglich: erst ~5 Übungsgruppen (Tag 1–2),
      dann alle — die ersten 48 h täglich schauen:
      `llm_call_completed`-Kosten, 5xx/`chat_error`-Rate,
      `technical_fallback`-Quote, `student_flow_open` NIE im Log.
- [ ] Erste-Wochen-Routine: 1× täglich Smoke + Dashboard-Blick;
      wöchentlich Tutor-Eval-Stichprobe gegen W3-Baseline.
- [ ] Nach TP1-Abgabefenster: Retrospektive; TP2-Cases final freigeben
      (W2-Fahrplan).

**GATE W6 (= Erfolg):** TP1 durchlaufen ohne P1-Incident; Kosten im
Rahmen; Tutor:innen nutzen die Gruppen-Sicht in der Präsenzphase.

---

## Abhängigkeiten

```
W0 ──► W1 ──► W5 ──► W6
        ▲      ▲      ▲
W2 ─────┴──────┘      │
W3 ────────────┘      │
W4 (parallel, Datenschutz-Freigabe blockiert W6) ──┘
```

Offen aus Code-Sicht (in W1/W2 enthalten): Mongo-Index-Skript,
Lasttest-Skript, `--case-id`-Workbook-Filter, ggf. Dashboard-Caching.
Bewusst NICHT vor dem Rollout: Frontend-Sentry, globales Rate-Limiting
(Redis), Chat-Verlauf über Reload, q4-Kampagnen-Umsetzung (nach Baseline).
