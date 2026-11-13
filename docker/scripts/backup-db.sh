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
