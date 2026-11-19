#!/usr/bin/env bash
# host-watchdog — liveness checks for the Dokploy host (oki), every 5 minutes
# via a systemd timer. Reports to Better Stack via a heartbeat:
#
#   healthy  -> ping <HEARTBEAT_URL>              (heartbeat stays "up")
#   unhealthy-> ping <HEARTBEAT_URL>/fail         (instant alert)
#   unreachable (docker/df/psql errors) -> exit 1 (heartbeat times out -> alert)
#
# Failure signals also set a Redis key the backend relays to admins as an
# in-app notification (see backend/app/services/watchdog_service.py).
#
# Config: /etc/betterstack-watchdog.env (root-only), keys:
#   BETTERSTACK_WATCHDOG_HEARTBEAT_URL  required
#   WATCHDOG_FAIL_KEY_PREFIX            default watchdog:fail:
#   WATCHDOG_REDIS_CONTAINER            default indic-book-metadata-extractor-app-isbfmc-redis-1
#   WATCHDOG_PG_CONTAINER               default indic-book-metadata-extractor-app-isbfmc-postgres-1
set -euo pipefail

ENV_FILE="${BETTERSTACK_WATCHDOG_ENV_FILE:-/etc/betterstack-watchdog.env}"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${BETTERSTACK_WATCHDOG_HEARTBEAT_URL:?BETTERSTACK_WATCHDOG_HEARTBEAT_URL not set (put it in $ENV_FILE)}"
FAIL_KEY_PREFIX="${WATCHDOG_FAIL_KEY_PREFIX:-watchdog:fail:}"
REDIS_CONTAINER="${WATCHDOG_REDIS_CONTAINER:-indic-book-metadata-extractor-app-isbfmc-redis-1}"
PG_CONTAINER="${WATCHDOG_PG_CONTAINER:-indic-book-metadata-extractor-app-isbfmc-postgres-1}"

# Container names (compose service names) this host must keep running. Dokploy
# prefixes them (<project>-<service>-<n>), so match on the service segment.
CONTAINERS=(backend worker frontend proxy)
DISK_MOUNT="/"
DISK_PCT_LIMIT=85
JOB_STUCK_MINUTES=90

fail() {
    local reason="$1"
    echo "WATCHDOG FAIL: $reason" >&2
    # Best-effort in-app notification: the backend relay picks the key up and
    # notifies admins (see backend/app/services/watchdog_service.py).
    docker exec "$REDIS_CONTAINER" redis-cli SET "${FAIL_KEY_PREFIX}host-watchdog" "$reason" EX 86400 \
        >/dev/null 2>&1 || true
    if command -v curl >/dev/null 2>&1; then
        curl -fsS -o /dev/null --max-time 10 "${BETTERSTACK_WATCHDOG_HEARTBEAT_URL}/fail" \
            --data "$reason" || echo "watchdog: /fail ping failed" >&2
    fi
    exit 0
}

healthy() {
    docker exec "$REDIS_CONTAINER" redis-cli DEL "${FAIL_KEY_PREFIX}host-watchdog" >/dev/null 2>&1 || true
    curl -fsS -o /dev/null --max-time 10 "$BETTERSTACK_WATCHDOG_HEARTBEAT_URL" \
        || { echo "watchdog: heartbeat ping failed (url=$BETTERSTACK_WATCHDOG_HEARTBEAT_URL)" >&2; exit 1; }
    exit 0
}

# 1. Required containers running. docker errors count as unhealthy (exit 1:
#    the heartbeat itself then times out and Better Stack alerts).
if ! ps_out=$(docker ps --format '{{.Names}}' 2>&1); then
    echo "watchdog: docker ps failed: $ps_out" >&2
    exit 1
fi
for c in "${CONTAINERS[@]}"; do
    if ! grep -qE -- "-${c}-[0-9]+$" <<<"$ps_out"; then
        fail "container '${c}' is not running"
    fi
done

# 2. Disk usage on the data mount.
if ! df_out=$(df -P "$DISK_MOUNT" 2>&1); then
    echo "watchdog: df failed: $df_out" >&2
    exit 1
fi
disk_pct=$(awk 'NR==2 {gsub(/%/,"",$5); print $5}' <<<"$df_out")
if [ "${disk_pct:-0}" -gt "$DISK_PCT_LIMIT" ]; then
    fail "disk ${DISK_MOUNT} at ${disk_pct}% (limit ${DISK_PCT_LIMIT}%)"
fi

# 3. Jobs stuck 'running' past the stale-job threshold (defense in depth for
#    the in-app reaper in backend/app/main.py:_reaper_loop). Postgres runs in a
#    container on the production host, so reach it through docker exec.
PSQL="docker exec "$PG_CONTAINER" psql -U postgres -d indic_books -tAc"
if ! stuck=$($PSQL \
    "SELECT count(*) FROM jobs WHERE status='running' AND coalesce(last_progress_at, started_at) < now() - interval '${JOB_STUCK_MINUTES} minutes';" 2>&1); then
    echo "watchdog: psql failed: $stuck" >&2
    exit 1
fi
stuck=${stuck//[[:space:]]/}
if [ "${stuck:-0}" -gt 0 ]; then
    fail "$stuck job(s) running > ${JOB_STUCK_MINUTES} min (see jobs table)"
fi

healthy