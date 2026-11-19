#!/bin/bash
# Manual database backup
# Run via: docker compose exec backup /backup-db.sh
# Or automatically by the backup service in docker-compose.yml

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_PATH:-/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-7}"
mkdir -p "$BACKUP_DIR"

FILENAME="indic_books_${TIMESTAMP}.dump"
echo "Creating database backup: $BACKUP_DIR/$FILENAME"

if ! pg_dump -U "$PGUSER" -h "$PGHOST" -Fc "$PGDATABASE" > "$BACKUP_DIR/$FILENAME"; then
    rm -f "$BACKUP_DIR/$FILENAME"
    echo "BACKUP FAILED: pg_dump did not complete for $PGDATABASE at $TIMESTAMP" >&2
    exit 1
fi

# Retain only the newest $BACKUP_KEEP dumps.
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/indic_books_*.dump 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt "$BACKUP_KEEP" ]; then
    ls -t "$BACKUP_DIR"/indic_books_*.dump | tail -n +$((BACKUP_KEEP + 1)) | xargs rm -f
    echo "Pruned old backups, kept last $BACKUP_KEEP."
fi

echo "Backup created successfully: $BACKUP_DIR/$FILENAME"

# Heartbeat: report success to Better Stack so a missing OR failing backup alerts.
# URL comes from the environment (Dokploy env var), never from the repo.
# The backup image is alpine (no curl) — fall back to busybox wget.
if [ -n "${BETTERSTACK_BACKUP_HEARTBEAT_URL:-}" ]; then
    if command -v curl >/dev/null 2>&1; then
        PING="curl -fsS -o /dev/null"
    else
        PING="wget -q -O /dev/null"
    fi
    if $PING "$BETTERSTACK_BACKUP_HEARTBEAT_URL"; then
        echo "Backup heartbeat pinged."
    else
        echo "WARNING: backup heartbeat ping failed (backup itself succeeded)." >&2
    fi
fi
