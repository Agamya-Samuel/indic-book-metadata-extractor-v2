#!/bin/bash
# Manual database backup
# Run via: docker compose exec backup /backup-db.sh
# Or automatically by the backup service in docker-compose.yml

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_PATH:-/backups}"
mkdir -p "$BACKUP_DIR"

FILENAME="indic_books_${TIMESTAMP}.dump"
echo "Creating database backup: $BACKUP_DIR/$FILENAME"

pg_dump -U "$PGUSER" -h "$PGHOST" -Fc "$PGDATABASE" > "$BACKUP_DIR/$FILENAME"

# Retain only last 7 backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/indic_books_*.dump 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 7 ]; then
    ls -t "$BACKUP_DIR"/indic_books_*.dump | tail -n +8 | xargs rm -f
    echo "Pruned old backups, kept last 7."
fi

echo "Backup created successfully: $BACKUP_DIR/$FILENAME"
