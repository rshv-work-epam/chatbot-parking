#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"

if [[ -z "$BASE_URL" ]]; then
  echo "BASE_URL is required (e.g., https://<app>.azurecontainerapps.io)" >&2
  exit 2
fi

if [[ -z "$ADMIN_TOKEN" ]]; then
  echo "ADMIN_TOKEN is required (admin UI token / x-api-token)" >&2
  exit 2
fi

curl -fsSL "$BASE_URL/chat/ui" >/dev/null
curl -fsSL "$BASE_URL/admin/ui" >/dev/null

THREAD="smoke-$(date +%s)-$RANDOM"

post() {
  local msg="$1"
  curl -fsSL -X POST "$BASE_URL/chat/message" \
    -H 'Content-Type: application/json' \
    -d "{\"message\":\"${msg}\",\"thread_id\":\"${THREAD}\"}"
}

expect_eq() {
  local got="$1"
  local expected="$2"
  local label="$3"
  if [[ "$got" != "$expected" ]]; then
    echo "Expected $label=$expected, got $got" >&2
    exit 1
  fi
}

resp="$(post "I want to reserve a spot")"
expect_eq "$(echo "$resp" | jq -r '.mode')" "booking" "mode"
expect_eq "$(echo "$resp" | jq -r '.pending_field')" "name" "pending_field"

post "John" >/dev/null
post "Doe" >/dev/null
post "AA-1234" >/dev/null

resp="$(post "2026-02-20 09:00 to 2026-02-20 10:00")"
expect_eq "$(echo "$resp" | jq -r '.status')" "review" "status"

resp="$(post "confirm")"
request_id="$(echo "$resp" | jq -r '.request_id')"
if [[ -z "$request_id" || "$request_id" == "null" ]]; then
  echo "Expected request_id in response, got: $resp" >&2
  exit 1
fi

curl -fsSL -X POST "$BASE_URL/admin/decision" \
  -H "x-api-token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"request_id\":\"${request_id}\",\"approved\":true,\"notes\":\"ok\"}" >/dev/null

resp="$(post "status")"
expect_eq "$(echo "$resp" | jq -r '.status')" "approved" "status"

echo "Smoke test OK (thread_id=$THREAD request_id=$request_id)"

