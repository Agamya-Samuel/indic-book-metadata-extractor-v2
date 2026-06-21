#!/bin/bash
# Backup file storage (uploads, pages, thumbnails, processed images)
# Run from project root: bash docker/scripts/backup-storage.sh

set -euo pipefail

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_PATH:-./backups}"
STORAGE_DIR="${STORAGE_DIR:-./backend/storage}"
mkdir -p "$BACKUP_DIR"

FILENAME="storage_${TIMESTAMP}.tar.gz"
echo "Creating storage backup: $BACKUP_DIR/$FILENAME"

tar -czf "$BACKUP_DIR/$FILENAME" -C "$STORAGE_DIR" .

# Retain only last 5 backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/storage_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 5 ]; then
    ls -t "$BACKUP_DIR"/storage_*.tar.gz | tail -n +6 | xargs rm -f
    echo "Pruned old storage backups, kept last 5."
fi

echo "Storage backup created: $BACKUP_DIR/$FILENAME"
