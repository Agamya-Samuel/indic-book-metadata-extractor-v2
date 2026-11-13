# Operations Runbook

Everything here was executed on production (`oki`) on 2026-11-14 unless marked
otherwise. Host and credential locations are in `reference/` (gitignored).

- **Host:** `ssh oki`
- **Deploy unit:** Dokploy compose project `indic-book-metadata-extractor-app-isbfmc`
- **Checkout + generated env:** `/etc/dokploy/compose/indic-book-metadata-extractor-app-isbfmc/code/`
- **Deploy logs:** `/etc/dokploy/logs/indic-book-metadata-extractor-app-isbfmc/`
- **Public origin:** `https://indic-book-metadata-extractor.agamya.us.kg` (Cloudflare in front)
- **Local disk:** 193 GB, dumps under the `backup_data` volume

Container names follow `<app>-<service>-1`, e.g.
`indic-book-metadata-extractor-app-isbfmc-backend-1`.

## Health

| Check | Command | Expected |
|---|---|---|
| Liveness (public) | `curl -s -o /dev/null -w '%{http_code}' https://indic-book-metadata-extractor.agamya.us.kg/api/health` | `200` |
| Dependencies (internal) | `docker exec <backend> \\ /app/.venv/bin/python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').read())"` | JSON with postgres/redis/ollama `ok` |
| Containers | `docker ps --format '{{.Names}} {{.Status}}'` | frontend/backend/worker/postgres/redis/ollama healthy or up |

Point an external uptime monitor at `/api/health` (200 + body `{"status":"ok"}`).
It deliberately does not disclose dependency state.

## Deploy

Pushing to `main` auto-deploys. Watch it finish:

```bash
ssh oki 'LOG=$(ls -t /etc/dokploy/logs/indic-book-metadata-extractor-app-isbfmc/ | head -1); \
  tail -f "/etc/dokploy/logs/indic-book-metadata-extractor-app-isbfmc/$LOG"'
```

Success is the log's last line `Docker Compose Deployed: ✅`. The backend
entrypoint runs `alembic upgrade head`, so a migration applies on start; check
with:

```bash
ssh oki 'docker exec <backend> sh -lc "cd /app && uv run alembic current"'
```

An in-flight deploy holds Dokploy's lock — a second push before it finishes
starts nothing. Wait for the marker, then push again.

## Rollback

1. `git revert <bad-commit>` (one revert per commit, in reverse order) and push —
   the same path as a deploy.
2. Or use Dokploy's deployment history for this compose service and redeploy the
   previous build.

After either, confirm the log marker and `alembic current`. Reverting a commit
does **not** undo a migration; if the bad release added one, write a downgrade
migration rather than reverting the file.

## Restarting services

```bash
docker restart <container>        # keeps the restart policy active
docker stop <container>           # NOTE: a manual stop disables auto-restart
docker start <container>
```

`docker kill`/`docker stop` mark the container "manually stopped"; the
`unless-stopped` policy will **not** bring it back. Use `docker start` after an
intentional stop. A container that exits on its own is restarted by the policy.

## Stuck jobs

A worker crash can leave `jobs.status = 'running'` with the book locked in
`ocr_running`/`llm_running`.

- **Automatic:** the backend sweeps every 5 minutes and fails running jobs older
  than `STALE_JOB_MINUTES` (default 90), releases the book, and notifies the owner.
- **Manual:** the owner or an admin cancels from the Dashboard/Jobs page. Cancel
  rolls the book back and closes the stage; verified live 2026-11-14.

Check what is wedged:

```bash
docker exec <postgres> psql -U postgres -d indic_books -c \
  "select j.id, j.job_type, j.status, j.progress, j.started_at, b.status as book \
   from jobs j join books b on b.id=j.book_id \
   where j.status='running' order by j.started_at;"
```

## Backup and restore

Dumps are `pg_dump -Fc`, written daily and pruned to the newest
`BACKUP_KEEP` (default 7):

```bash
docker exec <backup> sh -lc 'ls -lh /backups'
```

Manual backup: `docker exec <backup> /backup-db.sh`.

**Restore drill (verified 2026-11-14):**

```bash
ssh oki
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
# clean up: dropdb indic_books_restore_check; rm /tmp/restore.dump
```

The dump carries `alembic_version` at the moment of the dump; the backend
entrypoint upgrades it on start.

**Known gap:** dumps live on the same host and disk as the database. Copy them
off-host (object storage or another machine) before launch — that needs a
destination and credentials from the operator.

## Accounts

- **Approve / reject:** Admin → Users, or the notification deep link.
- **First admin on a fresh install** (the image now ships `scripts/`):

```bash
docker exec -it <backend> sh -lc \
  "cd /app && uv run python scripts/create_admin.py \
   --email admin@example.com --display-name 'Admin'"
```

It prompts for the password, creates a verified, approved administrator.

## Logs

```bash
docker logs --since 30m <backend> | tail -100
docker logs --since 30m <worker>  | tail -100
```

Rotation is Docker's `json-file` at 3 × 10 MB per container. There is no log
shipping and no APM (`NEW_RELIC_ENABLED=false`); search container logs on the
host.

Useful lines:

- `Notification email delivery: X/Y sent, Z skipped by preference`
- `Failed to send '<subject>' email to <address>` — transport failure (today the
  SMTP host does not resolve; see below)
- `Reaped stale <type> job <id>` — the reaper acted

## Email

SMTP is configured through `SMTP_*` on both the backend and worker services (the
worker needs them too — it sends job notifications). With the host resolving:

1. Set `SMTP_*` in the Dokploy environment and redeploy.
2. Trigger one notification (e.g. approve a test account).
3. Confirm `Sent '<subject>' email to <address>` in the backend/worker log.

Until the mail host resolves, every send fails with `socket.gaierror` and the
in-app notification is unaffected.

## Outstanding security actions (operator, Cloudflare account)

1. **Close the origin.** `https://187.127.174.246/` currently serves the app
   directly, bypassing Cloudflare. Restrict ingress to Cloudflare IP ranges
   (firewall or Cloudflare Tunnel). Until then, edge WAF/rate rules and the
   proxy-derived client IP can be spoofed by a direct caller.
2. **Edge rules.** Add a Cloudflare rate-limit rule for `/api/auth/*` and a WAF
   managed ruleset.
3. **Alerting.** At minimum: site down (`/api/health` != 200), worker container
   not running, any `running` job older than 90 minutes, disk > 85%, and a backup
   older than 36 hours.

## Incident checklist

1. Is the site up? `/api/health`, `docker ps`.
2. Which service is unhealthy? `docker ps`, then its `docker logs --since 15m`.
3. Disk/RAM: `df -h /`, `free -h` (no swap — OOM kills are possible; Ollama is
   capped at 7 GB).
4. Deploy in progress or failed? Newest log in `/etc/dokploy/logs/<app>/`;
   rollback if it regressed.
5. Stuck queue? Check `running` jobs; the reaper clears anything older than 90
   minutes, otherwise cancel manually.
6. Data loss? Stop writes, identify the newest dump, restore into a scratch DB
   first (drill above), then decide between in-place restore and replay.