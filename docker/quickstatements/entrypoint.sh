#!/usr/bin/env bash
# QuickStatements entrypoint wrapper.
#
# The stock entrypoint renders config.json/oauth.ini and starts Apache. Before
# that, write the Toolforge-style DB credentials that its DB wrapper reads from
# /data/project/<user>/replica.my.cnf. The web user (www-data) must be able to
# read the file, so chown it to www-data.
set -e

if [ -n "${MYSQL_PASSWORD:-}" ]; then
  mkdir -p /data/project/nobody
  printf '[client]\nuser = wikibase\npassword = %s\n' "$MYSQL_PASSWORD" \
    > /data/project/nobody/replica.my.cnf
  chown www-data:www-data /data/project/nobody/replica.my.cnf
  chmod 600 /data/project/nobody/replica.my.cnf
fi

exec /bin/bash /entrypoint.sh