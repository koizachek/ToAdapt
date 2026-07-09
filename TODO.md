"""Rubric-Evaluator — Bewertet Studierenden-Antworten gegen Bloom-Lernziele.
Kritisch

1. Das Backend hat keinerlei Authentifizierung.
Kein einziger FastAPI-Endpoint prüft Credentials — es gibt im gesamten Backend kein Depends, keinen API-Key, nichts. Der Teacher-Login (frontend/middleware.ts) schützt nur die Next.js-Seiten, aber das Frontend ruft das Backend direkt über NEXT_PUBLIC_API_URL auf (frontend/lib/api.ts:1) — die Railway-API ist also öffentlich. Jeder im Internet kann:
- /dashboard/students aufrufen und alle Matrikelnummern/Prolific-IDs samt Scores abziehen (backend/dashboard/routes.py:257)
- /admin/cases/generate aufrufen und auf deine Kosten LLM-Calls auslösen sowie Cases approven/löschen (backend/admin/routes.py:37)
- fremde Submissions per ID überschreiben und einreichen (backend/api/routes.py:224)

2. Echte Prolific-Teilnehmerdaten liegen im öffentlichen GitHub-Repo.
data/submission_states.json (24 Teilnehmer, Prolific-PIDs + vollständige Freitextantworten), data/experiment_events.json (~16.000 Zeilen Event-Logs) und backend/db/dashboard_seed/teacher_alignment_20260531_17submissions.json (16 PIDs + Scores) sind committet — seit Commit e722310. Prolific-PIDs sind personenbezogene Daten (DSGVO), und Prolifics ToS verbieten deren Veröffentlichung explizit. Der spätere .gitignore-Eintrag hilft nicht: Die Dateien müssen aus dem Repo UND aus der Git-History entfernt werden (z.B. git filter-repo), sonst bleiben sie über die Commit-Historie abrufbar.

3. Docker-Image enthält alle Secrets.
Es gibt keine .dockerignore, und das Dockerfile macht COPY . . — damit landen .env (OpenRouter-Key, MongoDB-Credentials), .git/ und alle Datenfiles im Image. Railway baut zwar per Nixpacks, aber jedes lokal gebaute und irgendwohin gepushte Image leakt alles.

Hoch

4. Teacher-Authentifizierung ist trivial umgehbar. Der Zugang ist ein einzelner Code aus .env (TEACHER_ACCESS_CODE), Fallback ist "0000" (frontend/app/teacher-login/route.ts:8). Das gesetzte Cookie ist statisch teacher_access=true — jeder kann es ohne Code selbst setzen und ist „eingeloggt". Kein Signieren, kein Session-Token.

5. CORS erlaubt jeden Origin bei aktivierten Credentials. allow_origins=["*"] zusammen mit allow_credentials=True (backend/main.py:62). In Kombination mit Punkt 1 macht das jede fremde Website zum vollwertigen Client deiner API.

6. Next.js 16.2.4 hat 13 bekannte Advisories (npm audit), darunter mehrere hochstufige Middleware-/Proxy-Bypässe — direkt relevant, weil dein einziger Seitenschutz auf der Middleware beruht. Fix: next@16.2.10 (npm audit fix --force). Zusätzlich moderate XSS-Lücke in transitivem postcss.

Mittel

7. Interne Fehler werden an den Client durchgereicht. Der globale Handler gibt str(exc) als Detail zurück (backend/main.py:81), ebenso /chat (api/routes.py:170). Das leakt Stacktrace-Interna, Pfade, ggf. Verbindungsstrings.

8. Startup- und /health-Diagnostik ist zu geschwätzig. /health ist unauthentifiziert und verrät MongoDB-Host-Setup, Env-Key-Namen und Feldlängen (main.py:86); der Startup-Log schreibt api_key_prefix (erste 12 Zeichen des OpenRouter-Keys) ins Log (main.py:46).

9. SECRET_KEY in .env ist nur 23 Zeichen und wird aktuell nirgends verwendet — falls du Sessions/JWT einführst, vorher durch einen zufälligen 32-Byte-Wert ersetzen. Da .env je im Verlauf lag: rotiere OpenRouter-Key und MongoDB-Passwort zur Sicherheit (die History-Treffer zu mongodb+srv:// sind zwar Code-Templates, kein Klartext-Credential — aber die .env selbst war nie getrackt, das ist gut).

Niedrig

- datetime.utcnow() ist in Python 3.13 deprecated (mehrfach, z.B. api/routes.py:159).
- In-Memory-Session-Store (_sessions) geht bei jedem Neustart verloren und skaliert nicht über mehrere Worker — für die geplanten ~2.000 User ein Problem.
- .pytest_cache, .DS_Store und __pycache__ sind teils getrackt.

Empfohlene Sofortmaßnahmen (Reihenfolge)

1. Repo auf privat stellen, bis 2 und 1 behoben sind.
2. Teilnehmerdaten aus History entfernen (git filter-repo) und Prolific-Meldepflicht prüfen.
3. Backend-Auth einführen — mindestens ein Shared-Secret-Header (X-API-Key via Depends) auf /admin/* und /dashboard/*, das das Frontend serverseitig (Route Handler / API-Proxy), nicht über NEXT_PUBLIC_*, mitschickt.
4. CORS auf die konkrete Frontend-Domain einschränken.
5. .dockerignore anlegen (.env, .git, data/, backend/db/) und Secrets rotieren.
6. npm audit fix --force für Next.js.

Soll ich mit einem davon anfangen? Am schnellsten umsetzbar und mit dem größten Effekt wären .dockerignore + CORS-Einschränkung + der Next.js-Fix; die Backend-Auth ist der wichtigste, aber größere Eingriff.

⏺ Fable 5's safeguards flagged this message. The safeguards are intentionally broad right now and may flag safe and routine coding, cybersecurity, or biology work. These measures let us bring you Mythos-level capabilities sooner, and we're working to refine them. Switched to Opus 4.8. Send feedback with /feedback or learn more
  ⎿  Tip: You can configure model switch behavior in /config

✻ Sautéed for 4m 14s

❯ ja fange damit dockerignoer

Ich lege eine .dockerignore an, die Secrets, Git, Daten und Build-Artefakte vom Image ausschließt.

  Read 1 file

⏺ Write(.dockerignore)
Wrote 38 lines to .dockerignore
 Secrets & environment
envHandler / API-Proxy), nicht über NEXT_PUBLIC_*, mitschickt.
4. CORS auf die konkrete Frontend-Domain einschränken.
5. .dockerignore anlegen (.env, .git, data/, backend/db/) und Secrets rotieren.
6. npm audit fix --force für Next.js.