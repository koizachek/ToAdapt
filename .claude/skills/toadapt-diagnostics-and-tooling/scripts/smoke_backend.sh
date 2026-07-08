#!/usr/bin/env bash
# Smoke-Test gegen eine laufende ToAdapt-Backend-Instanz (lokal oder Railway).
#
# Verhalten: nur lesende GET-Requests plus zwei bewusst abgewiesene Requests
# (PATCH ohne Key, POST auf nicht existenten Case). Erzeugt KEINE Daten und
# KEINE LLM-Kosten.
#
# Usage:
#   ./smoke_backend.sh <BASE_URL> [API_KEY] [STUDENT_ACCESS_CODE]
# Beispiele:
#   ./smoke_backend.sh http://localhost:8000
#   ./smoke_backend.sh https://<app>.up.railway.app "$TOADAPT_API_KEY"
#
# Exit-Code 0 = alle Checks bestanden, 1 = mindestens ein FAIL.
set -u

BASE_URL="${1:?Usage: smoke_backend.sh <BASE_URL> [API_KEY] [STUDENT_ACCESS_CODE]}"
API_KEY="${2:-}"
STUDENT_CODE="${3:-}"

PASS=0
FAIL=0

# check "<Beschreibung>" "<erlaubte Statuscodes, kommagetrennt>" <curl-Argumente...>
check() {
  local desc="$1"; shift
  local expected="$1"; shift
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@")
  if [[ ",$expected," == *",$status,"* ]]; then
    echo "PASS  [$status] $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL  [$status, erwartet: $expected] $desc"
    FAIL=$((FAIL + 1))
  fi
}

echo "== ToAdapt Backend Smoke-Test: $BASE_URL =="

# 1. Öffentlicher Health-Check (Railway healthcheckPath)
check "GET /health -> 200" "200" "$BASE_URL/health"

# 2. Diagnostics ohne Key: 401 (Key konfiguriert) oder 503 (kein Key = fail-closed)
check "GET /health/diagnostics ohne Key -> 401/503" "401,503" "$BASE_URL/health/diagnostics"

# 3. Dashboard ohne Key: ebenfalls geschützt
check "GET /dashboard/overview ohne Key -> 401/503" "401,503" "$BASE_URL/dashboard/overview"

# 4. Case-Liste (lesend, bewusst ungeschützt)
check "GET /admin/cases -> 200" "200" "$BASE_URL/admin/cases"

# 5. Schreibender Admin-Endpunkt ohne Key muss abgewiesen werden
check "PATCH /admin/cases/smoke-test ohne Key -> 401/503" "401,503" \
  -X PATCH -H 'Content-Type: application/json' -d '{}' \
  "$BASE_URL/admin/cases/smoke-test"

# 6. Studenten-Flow: Session auf nicht existenten Case.
#    404 = Flow erreichbar, Case unbekannt (kein Datensatz wird angelegt).
#    401 = STUDENT_ACCESS_CODE aktiv und kein/falscher Code übergeben.
if [[ -n "$STUDENT_CODE" ]]; then
  check "POST /sessions (Case nicht existent, mit Access-Code) -> 404" "404" \
    -X POST -H 'Content-Type: application/json' \
    -H "X-Student-Access-Code: $STUDENT_CODE" \
    -d '{"user_id":"smoke-test","case_id":"smoke-test-nonexistent"}' \
    "$BASE_URL/sessions"
else
  check "POST /sessions (Case nicht existent, ohne Access-Code) -> 404/401" "404,401" \
    -X POST -H 'Content-Type: application/json' \
    -d '{"user_id":"smoke-test","case_id":"smoke-test-nonexistent"}' \
    "$BASE_URL/sessions"
fi

# 7./8. Geschützte Endpunkte mit Key (nur wenn API_KEY übergeben)
if [[ -n "$API_KEY" ]]; then
  check "GET /health/diagnostics mit Key -> 200" "200" \
    -H "X-API-Key: $API_KEY" "$BASE_URL/health/diagnostics"
  check "GET /dashboard/overview mit Key -> 200" "200" \
    -H "X-API-Key: $API_KEY" "$BASE_URL/dashboard/overview"
  echo "-- /health/diagnostics Payload --"
  curl -s --max-time 15 -H "X-API-Key: $API_KEY" "$BASE_URL/health/diagnostics" \
    | { jq . 2>/dev/null || cat; }
  echo
else
  echo "SKIP  Kein API_KEY übergeben — Diagnostics-/Dashboard-200-Checks übersprungen."
fi

echo "== Ergebnis: $PASS PASS, $FAIL FAIL =="
[[ $FAIL -eq 0 ]]
