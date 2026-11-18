# Backup and Recovery

Two things need backing up: the PostgreSQL database and the storage volume. They must be restored
together — the database stores file **paths**, not files.

- Database backup: `docker/scripts/backup-db.sh`
- Restore: `docker/scripts/restore-db.sh`
- Storage backup: `docker/scripts/backup-storage.sh`
- Service: `backup` in every compose file

---

## 1. What is backed up automatically

The `backup` service runs a 24-hour loop:

```text
/backup-db.sh → pg_dump -Fc → /backups/indic_books_<timestamp>.dump → prune to newest 7
```

| Property | Value |
| --- | --- |
| Format | `pg_dump -Fc` (custom, compressed) |
| Destination | `backup_data` volume, `$BACKUP_PATH` (default `/backups`) |
| Retention | `BACKUP_KEEP` (default 7) |
| Failure handling | A failed dump is deleted and the script exits non-zero — a truncated file is never retained |

**Only the database is automatic.** `storage_data` — PDFs, rendered pages, processed images,
thumbnails, the fine-tuned OCR model — is **not** on a schedule. Losing it leaves every `pages` row
pointing at a missing file, and the pipeline cannot recover without the original PDFs.

---

## 2. Manual backups

```bash
make backup-db                              # database only
make backup-storage                         # storage volume only
make backup                                 # both
```

`make backup-db` shells into the running `backup` container, so it uses the same credentials and path
as the scheduled job.

---

## 3. Restore

```bash
make restore-db BACKUP=./backups/indic_books_20260101_120000.dump
```

The `BACKUP` argument is required — the target refuses to guess.

### Restore procedure

1. **Put the app in maintenance mode** (Admin → System) or stop `backend` and `worker`.
2. Take a safety dump of the current database first, even if it is broken.
3. Stop writers: `docker compose stop backend worker`.
4. Restore the dump.
5. Restore the storage volume to the matching point in time.
6. Run `make migrate` — the dump may predate the current schema.
7. Start services and verify `/health` and one book end to end.

### Restore drill (verified 2026-11-14)

Restore into a scratch database rather than over the live one:

```bash
docker cp <backup>:/backups/<dump>.dump /tmp/restore.dump
docker cp /tmp/restore.dump <postgres>:/tmp/restore.dump
docker exec <postgres> sh -lc '
  dropdb -U postgres --if-exists indic_books_restore_check &&
  createdb -U postgres indic_books_restore_check &&
  pg_restore -U postgres -d indic_books_restore_check --no-owner --no-privileges /tmp/restore.dump &&
  psql -U postgres -d indic_books_restore_check -c \
    "select (select count(*) from users) users, (select count(*) from books) books,
            (select count(*) from jobs) jobs, (select count(*) from pages) pages;"
'
# cleanup: dropdb -U postgres indic_books_restore_check; rm /tmp/restore.dump
```

Container names follow `<project>-<service>-1`. The dump carries `alembic_version` as of the dump, so
the authorised upgrade path is: restore, then let the backend entrypoint run `alembic upgrade head`.

### Why order matters

Migrations run only forward in practice. Restoring an older dump and starting the backend without
migrating leaves the schema behind the code; the backend entrypoint runs `alembic upgrade head`, so
starting it performs the migration — but do that deliberately, not accidentally during a rollback.

---

## 4. What is in the volumes

| Volume | Contents | Recreatable? |
| --- | --- | --- |
| `pgdata` | All relational state | No — must be backed up |
| `storage_data/uploads` | Original PDFs | **No** (unless re-uploaded) |
| `storage_data/pages` | Rendered page PNGs | Yes — re-render from PDF |
| `storage_data/processed` | Preprocessed images | Yes — re-preprocess |
| `storage_data/thumbnails` | Thumbnails and previews | Yes — regenerate |
| `storage_data/models/telugu-ocr-ft` | Fine-tuned checkpoint | Only from training artefacts |
| `backup_data` | Database dumps | No |
| `redis_data` | Queue state (AOF) | Effectively yes; queued work is lost |
| `ollama_data` | Model weights | Yes — pull again |
| `mysql_data`, `elasticsearch_data`, `wikibase_config`, `wikibase_data`, `quickstatements_data`, `openrefine_data` | Export stack | Yes, but data is lost |

So the **irreplaceable** set is: `pgdata`, `storage_data/uploads`, `storage_data/models`, and
`backup_data`.

---

## 5. Verification

A backup you have not restored is a hypothesis. Verify periodically:

1. Restore the newest dump into a scratch database.
2. `SELECT count(*) FROM books, pages, jobs, metadata;` — compare magnitudes with production.
3. Confirm `alembic_version` matches expectations.
4. Spot-check that a `pages.image_path` resolves to a real file in the storage backup.

The script guarantees the dump command exited zero; it cannot guarantee the dump is usable.

---

## 6. Recovery scenarios

| Scenario | Recovery |
| --- | --- |
| Bad migration | Restore the pre-deploy dump; migrations re-apply on start |
| Accidental book deletion | Restore DB **and** storage to before the delete |
| Corrupt storage volume | Restore storage; re-render pages if the backup predates them |
| Lost `pgdata` | Restore newest dump; storage volume is still valid |
| Lost `storage_data` only | Restore it; if unavailable, original PDFs must be re-uploaded and pages re-rendered |
| Redis lost | No restore needed; queued jobs are gone, re-dispatch them |
| Whole host lost | New host, restore `pgdata` + `storage_data`, pull the model, redeploy |

---

## 7. Retention and off-host copies

The default keeps 7 days **in the same Docker host**. That protects against logical errors (bad
delete, bad migration) but not against host loss.

For host-loss protection, copy dumps and the storage archive off the machine on a schedule. This is not
automated in the repository. If you add it:

- Copy, do not move — the local retention policy still applies.
- Encrypt at rest; dumps contain password hashes and user emails.
- Test a restore from the off-host copy at least once.

---

## 8. Security

- Dumps contain `users.password_hash` (Argon2), emails, and refresh-token hashes. Treat them as
  sensitive.
- Never commit a dump. `backup_data` is a volume, not a repository path.
- The `backup` container has the database password in its environment; it is on the internal network
  only.

---

## 9. Limitations

1. **No point-in-time recovery.** Only daily logical dumps.
2. **No automated storage backup.**
3. **No off-host replication.**
4. **Retention is count-based, not time-based** — 7 dumps, however old.
5. **No restore automation in CI.** Verification is manual.
