#!/bin/sh
# Fix stale MediaWiki schema from previous versions (< 1.38).
# This script runs BEFORE the standard MariaDB entrypoint.
# It detects the stale schema and clears it so MediaWiki can do a fresh install.
# After one successful boot, you can remove this script.

# Only check if the data directory already has data (not a fresh volume)
if [ -d "/var/lib/mysql/wikibase" ]; then
  echo "[fix-stale-schema] Existing database detected — checking schema version..."

  # Start MySQL in background (skip networking, skip grant tables for speed)
  docker-entrypoint.sh --skip-networking --skip-grant-tables &
  MYSQL_PID=$!

  # Wait for MySQL to be ready
  for i in $(seq 1 30); do
    if mysqladmin ping --silent 2>/dev/null; then
      break
    fi
    sleep 1
  done

  # Check the mw_core schema version
  SCHEMA_VERSION=$(mysql -u root -e "SELECT version FROM wikibase.mw_core WHERE version LIKE 'wikibase%';" 2>/dev/null | tail -1)
  echo "[fix-stale-schema] Schema version: '$SCHEMA_VERSION'"

  if echo "$SCHEMA_VERSION" | grep -qE '^wikibase (1\.(2[0-9]|3[0-7]))'; then
    echo "[fix-stale-schema] Stale schema detected (< 1.38). Dropping and recreating wikibase database..."
    mysql -u root -e "DROP DATABASE IF EXISTS wikibase; CREATE DATABASE wikibase CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON wikibase.* TO 'wikibase'@'%';"
    echo "[fix-stale-schema] Database cleared. MariaDB will do a fresh init."
  else
    echo "[fix-stale-schema] Schema version OK or not detected. Proceeding normally."
  fi

  # Stop the background MySQL
  kill $MYSQL_PID 2>/dev/null
  wait $MYSQL_PID 2>/dev/null
fi

# Hand off to the real entrypoint
exec docker-entrypoint.sh "$@"
