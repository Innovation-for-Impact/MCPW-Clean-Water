#!/usr/bin/env bash
# WS3 End-to-end tests — layers endpoint, spatial lookup, input validation
# Requires: API running at localhost:8000 with PostGIS and migrations applied
# Usage: ./scripts/test_e2e_ws3.sh
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
echo " WS3 — Layers & Spatial Lookup E2E Tests"
echo "============================================"

# ── Auth setup ────────────────────────────────
ADMIN_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | json_field access_token)

RESP_TOKEN=$(curl -s -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"responder","password":"responder123"}' | json_field access_token)

if [ -z "$ADMIN_TOKEN" ] || [ -z "$RESP_TOKEN" ]; then
  echo "FATAL: Could not obtain auth tokens"
  exit 1
fi

# ── 1. List Layers ────────────────────────────
echo ""
echo "1. List Layers"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "GET /layers/ returns 200" "200" "$STATUS"

RESP=$(curl -s "$BASE/layers/" -H "Authorization: Bearer $ADMIN_TOKEN")
LAYER_COUNT=$(echo "$RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('layers',[])))")
check "Returns 6 layer names" "6" "$LAYER_COUNT"

HAS_MUNI=$(echo "$RESP" | python3 -c "import sys,json; print('municipality' in json.load(sys.stdin).get('layers',[]))")
check "Includes municipality layer" "True" "$HAS_MUNI"

HAS_DRAIN=$(echo "$RESP" | python3 -c "import sys,json; print('drain_district' in json.load(sys.stdin).get('layers',[]))")
check "Includes drain_district layer" "True" "$HAS_DRAIN"

# ── 2. Get Layer (GeoJSON) ───────────────────
echo ""
echo "2. Get Municipality Layer"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality?limit=5" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "GET /layers/municipality returns 200" "200" "$STATUS"

RESP=$(curl -s "$BASE/layers/municipality?limit=5" -H "Authorization: Bearer $ADMIN_TOKEN")
TYPE=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('type',''))")
check "Returns FeatureCollection" "FeatureCollection" "$TYPE"

HAS_FEATURES=$(echo "$RESP" | python3 -c "import sys,json; print('features' in json.load(sys.stdin))")
check "Response has features array" "True" "$HAS_FEATURES"

HAS_COUNT=$(echo "$RESP" | python3 -c "import sys,json; print('total_count' in json.load(sys.stdin))")
check "Response includes total_count" "True" "$HAS_COUNT"

# ── 3. Invalid Layer ─────────────────────────
echo ""
echo "3. Invalid Layer"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/bogus" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "Unknown layer returns 404" "404" "$STATUS"

# ── 4. Input Validation ──────────────────────
echo ""
echo "4. Input Validation (limit/offset)"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality?limit=0" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "limit=0 returns 422" "422" "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality?limit=-1" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "limit=-1 returns 422" "422" "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality?offset=-1" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "offset=-1 returns 422" "422" "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality?limit=501" \
  -H "Authorization: Bearer $ADMIN_TOKEN")
check "limit=501 returns 422" "422" "$STATUS"

# ── 5. Auth Required ─────────────────────────
echo ""
echo "5. Auth Required"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/")
check "GET /layers/ without auth returns 401" "401" "$STATUS"

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/layers/municipality")
check "GET /layers/{name} without auth returns 401" "401" "$STATUS"

# ── 6. Spatial Lookup — In-County ────────────
echo ""
echo "6. Spatial Lookup (in-county point)"
LOOKUP=$(curl -s -X POST "$BASE/lookup" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.5959,"lon":-82.9001},"material":"oil_fuel","quantity_gallons":50}')

HAS_FLAGS=$(echo "$LOOKUP" | python3 -c "import sys,json; d=json.load(sys.stdin); print('outside_county' in d.get('flags',{}))")
check "Lookup response has spatial flags" "True" "$HAS_FLAGS"

OUTSIDE=$(echo "$LOOKUP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('flags',{}).get('outside_county',None))")
check "In-county point not flagged outside" "False" "$OUTSIDE"

JCOUNT=$(echo "$LOOKUP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('jurisdictions',[])))")
check "In-county point has jurisdictions" "true" "$([ "$JCOUNT" -gt 0 ] && echo true || echo false)"
echo "    (found $JCOUNT jurisdictions)"

HAS_PATH=$(echo "$LOOKUP" | python3 -c "import sys,json; print('downstream_path' in json.load(sys.stdin))")
check "Response includes downstream_path" "True" "$HAS_PATH"

HAS_UPSTREAM=$(echo "$LOOKUP" | python3 -c "import sys,json; print('upstream_counties' in json.load(sys.stdin))")
check "Response includes upstream_counties" "True" "$HAS_UPSTREAM"

# ── 7. Spatial Lookup — Outside County ───────
echo ""
echo "7. Spatial Lookup (outside-county point)"
LOOKUP_OUT=$(curl -s -X POST "$BASE/lookup" \
  -H "Authorization: Bearer $RESP_TOKEN" -H "Content-Type: application/json" \
  -d '{"location":{"lat":42.65,"lon":-83.25},"material":"oil_fuel"}')

OUTSIDE_FLAG=$(echo "$LOOKUP_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('flags',{}).get('outside_county',None))")
check "Oakland County point flagged outside_county" "True" "$OUTSIDE_FLAG"

JCOUNT_OUT=$(echo "$LOOKUP_OUT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('jurisdictions',[])))")
check "Outside-county returns 0 jurisdictions" "0" "$JCOUNT_OUT"

# ── 8. Spatial Lookup — Response Shape ───────
echo ""
echo "8. Lookup Response Shape"
# Verify all expected top-level keys exist
KEYS=$(echo "$LOOKUP" | python3 -c "
import sys, json
d = json.load(sys.stdin)
expected = ['jurisdictions','drain','nearest_water','first_major_drain_downstream',
            'next_intercept_point','downstream_path','upstream_counties','flags',
            'response_contacts','regulatory_contacts']
missing = [k for k in expected if k not in d]
print(','.join(missing) if missing else 'none')
")
check "Lookup has all expected fields" "none" "$KEYS"

# ── Results ──────────────────────────────────
echo ""
echo "============================================"
echo " WS3 Results: $PASS passed, $FAIL failed"
echo "============================================"
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
