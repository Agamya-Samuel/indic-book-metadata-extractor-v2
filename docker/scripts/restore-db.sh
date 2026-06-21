#!/bin/bash
# Restore database from a backup file
# Usage:
#   docker compose exec postgres pg_restore -U postgres -d indic_books --clean --if-exists /backups/FILENAME.dump
# Or from host:
#   docker/scripts/restore-db.sh ./backups/indic_books_20240101_120000.dump

set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <backup-file.dump>"
    echo "Example: $0 ./backups/indic_books_20240101_120000.dump"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will overwrite the current database!"
echo "Restoring from: $BACKUP_FILE"
echo "Press Ctrl+C to cancel, or wait 5 seconds..."
sleep 5

docker compose exec -T postgres pg_restore -U postgres -d indic_books --clean --if-exists < "$BACKUP_FILE"

echo "Database restored successfully from: $BACKUP_FILE"
