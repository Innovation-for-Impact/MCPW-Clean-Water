#!/usr/bin/env bash
# End-to-end test for MCPW Clean Water API
# Usage: ./scripts/test_e2e.sh
set -euo pipefail

BASE="http://localhost:8000"
PASS=0
FAIL=0

check() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$actual" = "$expected" ]; then
    echo "  PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $desc (expected=$expected, got=$actual)"
    FAIL=$((FAIL + 1))
  fi
}

json_field() {
  python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))"
}

echo "============================================"
echo " MCPW Clean Water API — E2E Test Suite"
echo "============================================"

# ── 1. Health ──────────────────────────────────
echo ""
echo "1. Health Check (public)"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
check "GET /health returns 200" "200" "$STATUS"
DB=$(curl -s "$BASE/health" | json_field db)
check "DB is connected" "connected" "$DB"

# ── 2. Auth — unauthenticated access blocked ──
echo ""
echo "2. Auth — Unauthenticated Access"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/events")
check "GET /events without token returns 401" "401" "$STATUS"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/incidents" -H "Content-Type: application/json" -d '{}')
check "POST /incidents without token returns 401" "401" "$STATUS"

# ── 3. Auth — login ───────────────────────────
echo ""
echo "3. Auth — Login"
# Bad credentials
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"wrong"}')
check "Login with bad password returns 401" "401" "$STATUS"

# Good credentials — get tokens for each role
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | json_field access_token)
check "Admin login returns token" "true" "$([ -n "$ADMIN_TOKEN" ] && echo true || echo false)"

RESP_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" -d '{"username":"responder","password":"responder123"}' | json_field access_token)
check "Responder login returns token" "true" "$([ -n "$RESP_TOKEN" ] && echo true || echo false)"

VIEWER_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" -d '{"username":"viewer","password":"viewer123"}' | json_field access_token)
check "Viewer login returns token" "true" "$([ -n "$VIEWER_TOKEN" ] && echo true || echo false)"

# ── 4. RBAC — role enforcement ────────────────
echo ""
echo "4. RBAC — Role Enforcement"
# Viewer cannot create incidents
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/incidents" \
  -H "Authorization: Bearer $VIEWER_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.59,"lon":-82.90},"water_body":"clinton_river","material":"oil_fuel","quantity":10,"quantity_unit":"gal","quantity_gallons":10,"time_observed":"2026-10-13T12:00:00Z","reporter_name":"Test","reporter_phone":"555-0100"}')
check "Viewer cannot POST /incidents (403)" "403" "$STATUS"

# Viewer cannot run lookup
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/lookup" \
  -H "Authorization: Bearer $VIEWER_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.59,"lon":-82.90},"material":"oil_fuel"}')
check "Viewer cannot POST /lookup (403)" "403" "$STATUS"

# Viewer cannot manage webhooks
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/webhooks" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
check "Viewer cannot GET /webhooks (403)" "403" "$STATUS"

# Responder cannot manage webhooks
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/webhooks" \
  -H "Authorization: Bearer $RESP_TOKEN")
check "Responder cannot GET /webhooks (403)" "403" "$STATUS"

# Viewer CAN read events
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/events" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
check "Viewer can GET /events (200)" "200" "$STATUS"

# ── 5. Lookup ─────────────────────────────────
echo ""
echo "5. Spatial Lookup"
LOOKUP_RESP=$(curl -s -X POST "$BASE/lookup" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.5959,"lon":-82.9001},"material":"oil_fuel","quantity_gallons":50}')
STATUS=$?
JURISDICTIONS=$(echo "$LOOKUP_RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('jurisdictions',[])))")
check "Lookup finds jurisdictions" "true" "$([ "$JURISDICTIONS" -gt 0 ] && echo true || echo false)"
echo "    (found $JURISDICTIONS jurisdictions)"

# ── 6. Create Incident ────────────────────────
echo ""
echo "6. Create Incident"
INCIDENT_RESP=$(curl -s -X POST "$BASE/incidents" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "location": {"lat": 42.5959, "lon": -82.9001, "address": "123 Main St, Clinton Twp, MI"},
    "water_body": "clinton_river",
    "material": "oil_fuel",
    "material_detail": "Diesel fuel",
    "quantity": 100,
    "quantity_unit": "gal",
    "quantity_gallons": 100,
    "time_observed": "2026-10-13T14:30:00Z",
    "reporter_name": "E2E Test",
    "reporter_phone": "555-0199",
    "notes": "E2E test incident"
  }')
INCIDENT_ID=$(echo "$INCIDENT_RESP" | json_field id)
INCIDENT_STATUS=$(echo "$INCIDENT_RESP" | json_field status)
check "Incident created with status 'open'" "open" "$INCIDENT_STATUS"
check "Incident has UUID id" "true" "$([ ${#INCIDENT_ID} -eq 36 ] && echo true || echo false)"
echo "    incident_id=$INCIDENT_ID"

# ── 7. Get Incident ───────────────────────────
echo ""
echo "7. Retrieve Incident"
GET_RESP=$(curl -s "$BASE/incidents/$INCIDENT_ID" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
GET_LAT=$(echo "$GET_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['location']['lat'])")
GET_MATERIAL=$(echo "$GET_RESP" | json_field material)
check "GET returns correct lat" "42.5959" "$GET_LAT"
check "GET returns correct material" "oil_fuel" "$GET_MATERIAL"

# Viewer can read incidents
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/incidents/$INCIDENT_ID" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
check "Viewer can GET /incidents/{id} (200)" "200" "$STATUS"

# ── 8. Events ─────────────────────────────────
echo ""
echo "8. Event Stream"
EVENTS=$(curl -s "$BASE/events?limit=1" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
EVENT_TYPE=$(echo "$EVENTS" | python3 -c "import sys,json; e=json.load(sys.stdin); print(e[0]['event_type'] if e else '')")
EVENT_INCIDENT=$(echo "$EVENTS" | python3 -c "import sys,json; e=json.load(sys.stdin); print(e[0]['incident_id'] if e else '')")
CREATED_BY=$(echo "$EVENTS" | python3 -c "import sys,json; e=json.load(sys.stdin); print(e[0]['data'].get('created_by','') if e else '')")
check "Latest event is incident.created" "incident.created" "$EVENT_TYPE"
check "Event references correct incident" "$INCIDENT_ID" "$EVENT_INCIDENT"
check "Event has audit trail (created_by)" "true" "$([ -n "$CREATED_BY" ] && echo true || echo false)"

# Filter by incident_id
FILTERED=$(curl -s "$BASE/events?incident_id=$INCIDENT_ID" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
FILTERED_COUNT=$(echo "$FILTERED" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
check "Event filter by incident_id works" "1" "$FILTERED_COUNT"

# ── 9. Webhooks (Admin) ──────────────────────
echo ""
echo "9. Webhooks (Admin Only)"
# Create webhook
WH_RESP=$(curl -s -X POST "$BASE/webhooks" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/webhook"}')
WH_ID=$(echo "$WH_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))")
check "Admin can create webhook" "true" "$([ -n "$WH_ID" ] && echo true || echo false)"

# List webhooks
WH_LIST=$(curl -s "$BASE/webhooks" -H "Authorization: Bearer $ADMIN_TOKEN")
WH_COUNT=$(echo "$WH_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
check "Admin can list webhooks" "true" "$([ "$WH_COUNT" -gt 0 ] && echo true || echo false)"

# Delete webhook
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$BASE/webhooks/$WH_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "Admin can delete webhook (204)" "204" "$STATUS"

# ── 10. SSRF Protection ──────────────────────
echo ""
echo "10. SSRF Protection"
# Private IP
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/webhooks" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "http://192.168.1.1/hook"}')
check "Private IP webhook rejected (422)" "422" "$STATUS"

# Localhost
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/webhooks" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:9999/hook"}')
check "Localhost webhook rejected (422)" "422" "$STATUS"

# ── 11. Validation ────────────────────────────
echo ""
echo "11. Input Validation"
# Bad enum values
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/incidents" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.59,"lon":-82.90},"water_body":"ocean","material":"oil_fuel","quantity":10,"quantity_unit":"gal","quantity_gallons":10,"time_observed":"2026-10-13T12:00:00Z","reporter_name":"Test","reporter_phone":"555"}')
check "Invalid water_body enum rejected (422)" "422" "$STATUS"

# Missing required fields
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/incidents" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.59,"lon":-82.90}}')
check "Missing required fields rejected (422)" "422" "$STATUS"

# 404 for nonexistent incident
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/incidents/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer $VIEWER_TOKEN")
check "Nonexistent incident returns 404" "404" "$STATUS"

# ── 12. Admin — Register User ────────────────
echo ""
echo "12. User Registration (Admin)"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}')
check "Admin can register new user (201)" "201" "$STATUS"

# Duplicate username
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass123"}')
check "Duplicate username rejected (409)" "409" "$STATUS"

# Non-admin cannot register
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/auth/register" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"testuser2","password":"testpass123"}')
check "Non-admin cannot register users (403)" "403" "$STATUS"

# ── Results ───────────────────────────────────
echo ""
echo "============================================"
echo " Results: $PASS passed, $FAIL failed"
echo "============================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
