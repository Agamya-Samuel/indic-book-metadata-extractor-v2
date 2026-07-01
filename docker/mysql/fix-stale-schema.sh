#!/bin/sh
# Fix stale MediaWiki schema from previous versions (< 1.38).
# If the wikibase database directory exists, remove it so MariaDB
# performs a fresh initialization on startup.
# After one successful boot, remove this script and redeploy.

if [ -d "/var/lib/mysql/wikibase" ]; then
  echo "[fix-stale-schema] Found existing wikibase database — removing for fresh install..."
  rm -rf /var/lib/mysql/wikibase
  echo "[fix-stale-schema] Removed. MariaDB will reinitialize."
fi

exec docker-entrypoint.sh "$@"
