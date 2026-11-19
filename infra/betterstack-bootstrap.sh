#!/usr/bin/env bash
# Better Stack Uptime bootstrap — create the OpenBookMap monitors and heartbeats.
#
# Idempotent: lists existing monitors/heartbeats first and skips anything that
# already exists by name. Requires a Uptime API token (team-scoped):
#
#   Better Stack → Settings → API tokens → Team-based tokens → team "OKI Team"
#
# Usage:
#   echo 'YOUR_TOKEN' > reference/betterstack   # gitignored
#   chmod 600 reference/betterstack
#   ./infra/betterstack-bootstrap.sh
#
# After creating the heartbeats, copy the printed ping URLs into:
#   - Dokploy env var BETTERSTACK_BACKUP_HEARTBEAT_URL (daily-backup)
#   - /etc/betterstack-watchdog.env on the host (host-watchdog)
# Never commit those URLs — they are secrets.
set -euo pipefail

TOKEN_FILE="${BETTERSTACK_TOKEN_FILE:-reference/betterstack}"
API="https://uptime.betterstack.com/api/v2"
BASE_URL="${BETTERSTACK_BASE_URL:-https://openbookmap.oki-india.org}"

[ -s "$TOKEN_FILE" ] || { echo "missing token file: $TOKEN_FILE" >&2; exit 1; }
TOKEN=$(cat "$TOKEN_FILE")
AUTH="Authorization: Bearer $TOKEN"
CT="Content-Type: application/json"

exists() {  # exists <kind: monitors|heartbeats> <name>
    curl -s -H "$AUTH" "$API/$1" | grep -q "\"name\": \"$2\""
}

create_monitor() {  # create_monitor <json>
    local out
    out=$(curl -s -X POST "$API/monitors" -H "$AUTH" -H "$CT" -d "$1")
    if grep -q '"errors"' <<<"$out"; then
        echo "  FAILED: $out" >&2
        return 1
    fi
    grep -o '"id": "[0-9]*"' <<<"$out" | head -1
}

create_heartbeat() {  # create_heartbeat <json> <label>
    local out
    out=$(curl -s -X POST "$API/heartbeats" -H "$AUTH" -H "$CT" -d "$1")
    if grep -q '"errors"' <<<"$out"; then
        echo "  FAILED: $out" >&2
        return 1
    fi
    echo "$2 ping URL (copy into env, keep secret):"
    grep -o '"url": "https://uptime.betterstack.com/api/v1/heartbeat/[a-zA-Z0-9]*"' <<<"$out" | cut -d'"' -f4
}

echo "==> Monitors"
if exists monitors "OpenBookMap API health"; then
    echo "  skip (exists): OpenBookMap API health"
else
    echo -n "  create: OpenBookMap API health ... "
    create_monitor "{
      \"monitor_type\": \"keyword\",
      \"url\": \"$BASE_URL/api/health\",
      \"pronounceable_name\": \"OpenBookMap API health\",
      \"required_keyword\": \"\\\"status\\\":\\\"ok\\\"\",
      \"check_frequency\": 180,
      \"request_timeout\": 15,
      \"email\": true
    }"
fi
if exists monitors "OpenBookMap login page"; then
    echo "  skip (exists): OpenBookMap login page"
else
    echo -n "  create: OpenBookMap login page ... "
    create_monitor "{
      \"monitor_type\": \"status\",
      \"url\": \"$BASE_URL/login\",
      \"pronounceable_name\": \"OpenBookMap login page\",
      \"expected_status_codes\": [200],
      \"check_frequency\": 180,
      \"request_timeout\": 15,
      \"email\": true
    }"
fi
if exists monitors "OpenBookMap homepage"; then
    echo "  skip (exists): OpenBookMap homepage"
else
    echo -n "  create: OpenBookMap homepage ... "
    create_monitor "{
      \"monitor_type\": \"status\",
      \"url\": \"$BASE_URL/\",
      \"pronounceable_name\": \"OpenBookMap homepage\",
      \"expected_status_codes\": [200],
      \"check_frequency\": 180,
      \"request_timeout\": 15,
      \"email\": true
    }"
fi

echo "==> Heartbeats"
if exists heartbeats "daily-backup"; then
    echo "  skip (exists): daily-backup"
else
    echo "  create: daily-backup"
    create_heartbeat "{
      \"name\": \"daily-backup\",
      \"period\": 86400,
      \"grace\": 43200,
      \"email\": true
    }" "daily-backup"
fi
if exists heartbeats "host-watchdog"; then
    echo "  skip (exists): host-watchdog"
else
    echo "  create: host-watchdog"
    create_heartbeat "{
      \"name\": \"host-watchdog\",
      \"period\": 600,
      \"grace\": 300,
      \"email\": true
    }" "host-watchdog"
fi

echo "Done. Verify in Better Stack → Uptime → Monitors / Heartbeats."