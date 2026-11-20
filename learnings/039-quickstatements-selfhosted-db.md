# 039 — QuickStatements on a Self-Hosted Stack: mysqli, Local DB, Batch Mode

**Date:** 2026-11-20

## Study Context

QuickStatements was the last manual/broken piece of the export stack. `run_single_command`
worked, but `run_batch` and `get_token` failed with `Could not complete the request.` The stock
`wikibase/quickstatements:1` image targets Wikimedia Toolforge, not a self-hosted MariaDB.

## Summary

QuickStatements now runs fully self-hosted: the custom image adds the missing `mysqli` extension,
repoints the Toolforge DB wrapper at the compose `mysql` service, and the compose provisions the
`wikibase__quickstatements_p` / `wikibase__quickstatements_auth` schemas on first boot. Verified
`get_token` → token, `run_batch` → `batch_id 1`, `run_single_command` → item created.

## Key Findings

### Why it was broken

1. **No `mysqli`.** `php -m` showed only `mysqlnd`/`PDO`; every `ToolforgeCommon::openDBtoolInternal`
   call failed with `Class "mysqli" not found`. The stock image's PHP build does not include it.
2. **Toolforge endpoints.** `ToolforgeCommon.php` defaulted to `tools.db.svc.wikimedia.cloud`
   (and `tools-readonly...`), which are unreachable from the compose network.
3. **No DBs.** The QS wrapper opens `quickstatements_p` / `quickstatements_auth`; neither existed in
   MariaDB. The `schema.sql` is not auto-imported.
4. **MariaDB rejects the stock schema.** `KEY user (user(191))` and `KEY user_2 (user(160), ...)`
   apply prefix lengths to an `int` column. MariaDB 10.11 returns
   `ERROR 1089 ... Incorrect prefix key`. Removing the `(191)`/`(160)` prefixes fixes it.
5. **Credential file permissions.** The wrapper reads `/data/project/nobody/replica.my.cnf`
   (`get_current_user()` is the script owner `nobody`), but Apache runs as `www-data`; a root-owned
   `0600` file is unreadable, so QS saw empty credentials
   (`Access denied for user ''@... (using password: NO)`). The entrypoint must `chown www-data`.

### Fix

- `docker/quickstatements/Dockerfile`: multi-stage build — compile `mysqli` with
  `docker-php-ext-install mysqli` from `php:8.3-apache`, copy the `.so` into the QS image, enable it,
  and `sed` `ToolforgeCommon.php` to use `mysql` instead of the Toolforge host.
- `docker/quickstatements/entrypoint.sh`: writes the `replica.my.cnf` from `MYSQL_PASSWORD`,
  `chown www-data`, then execs the stock `/entrypoint.sh`.
- `docker/mysql/02-init-quickstatements.sql` + `quickstatements-schema.sql`: create the two schemas,
  grant the existing `wikibase` MySQL user, and import the MariaDB-compatible schema on first boot.
- Compose (prod/staging): QS `build:` + `image: app-jb5tjz-quickstatements`, `entrypoint` override,
  `MYSQL_PASSWORD` env, entrypoint bind-mount, `depends_on: mysql`; mysql mounts the two init files.

### Verification

- `php -m` → `mysqli`.
- `get_token` → `{"status":"OK","data":{"token":"$2y$..."}}`.
- `run_batch` → `{"status":"OK","batch_id":1}`.
- `run_single_command` → `status: done`, item created and read back.
- Test items Q167–Q169 and the batch/user rows were deleted after verification.

## Recommendation

Keep the custom QS image. The manual QS setup (bot account, OAuth consumer, `oauthbot` group) is
still needed once per Wikibase; the batch DB and image are now deploy-time concerns, not operator
steps. A fresh deploy with an empty `mysql_data` gets the schemas automatically; an existing volume
needs the SQL in `02-init-quickstatements.sql` applied once (as was done here).

## Next Steps

- Optionally fold the QS bot/consumer bootstrap into the planned `bootstrap` service (Phase 1).
- Add a `verify-deployment.sh` check for `wikibase__quickstatements_*` tables and a QS login.

## References

- `docker/quickstatements/Dockerfile`, `docker/quickstatements/entrypoint.sh`
- `docker/mysql/02-init-quickstatements.sql`, `docker/mysql/quickstatements-schema.sql`
- `docker-compose.production.yml`, `docker-compose.staging.yml`
- `learnings/033-wikibase-oauth-quickstatements.md` (OAuth consumer)
- `docs/operations/quickstatements-setup.md`