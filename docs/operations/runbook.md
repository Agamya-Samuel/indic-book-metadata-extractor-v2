# Runbook

Symptom → diagnosis → action. For architecture, read
[pipeline-overview](../processing/pipeline-overview.md) first; this page assumes it.

---

## 1. First response

```bash
make status                        # container health
curl -s https://<host>/api/health  # dependency checks
make logs-backend                  # API errors
make logs-worker-ocr               # OCR/LLM errors (dev: also logs-worker-llm)
```

`GET /api/health` returns:

```json
{"status": "ok", "checks": {"postgres": "ok", "redis": "ok", "ollama": "ok"}}
```

It returns `503` with `status: "degraded"` when any dependency fails, and the failing check says why.

> **Note:** the worker container does not serve HTTP. Its health is judged by task throughput and
> logs, not by `/health`.

---

## 2. Books stuck in a running state

### Symptom

Book sits at `ocr_running` or `llm_running` indefinitely; the UI shows no progress movement.

### Diagnose

```sql
SELECT id, job_type, status, progress, started_at, last_progress_at
FROM jobs
WHERE book_id = '<book_id>'
ORDER BY created_at DESC;
```

- `last_progress_at` recent → the job is alive but slow. Extraction can legitimately take 40+ minutes
  on CPU.
- `last_progress_at` older than `STALE_JOB_MINUTES` (90) → the worker is gone.

### Act

1. **Wait** for the reaper. It runs every 300 s in the backend and fails any `running` job whose
   `coalesce(last_progress_at, started_at)` is past the threshold, releases the book, and notifies the
   owner.
2. **Or cancel now:** `POST /api/admin/jobs/{job_id}/cancel`. The cancel path commits `cancelled`
   first, then revokes, so it is safe even if the worker is wedged.
3. **Or restart the worker** — Celery redelivers unacked tasks (`acks_late`).

Never hand-edit `books.status`. It is derived from stage rows; edit stage rows or use the reset
endpoints, or the two state machines will permanently disagree.

---

## 3. OCR produced empty or garbage text

### Diagnose, in order

1. **Is there text at all?**
   `SELECT raw_text, cleaned_text, confidence, ocr_engine, ocr_route FROM ocr_results WHERE page_id='…';`
2. **Did the engine fall back?** `pages.ocr_error` starting with
   `Telugu line OCR fell back to Tesseract:` means the line model failed and Tesseract ran instead.
3. **Was the script routed?** `ocr_route` = `latin_page_reroute` or `dominant_script_reroute` means the
   page was re-OCR'd. Absence is fine.
4. **Is the language right?** `books.language` drives the Tesseract language string. A Hindi book
   marked `tel` will produce noise. Fix with `PATCH /api/books/{id}/language` and re-run OCR.
5. **Is the image usable?** Open `/api/pages/{page_id}/image`. If preprocessing destroyed it, check
   `preprocessing_config` — binarization and denoise are the usual culprits on Indic scripts.

### Act

| Finding | Action |
| --- | --- |
| Wrong `books.language` | Correct it, then re-run OCR |
| Line model failing | Check `/app/storage/models/telugu-ocr-ft` exists; fallback is automatic |
| Binarization enabled | Set `binarization: null` for that page |
| Very low confidence, readable image | Accept and correct manually in OCR review |
| Image genuinely corrupt | Re-render the page |

---

## 4. Every page failed OCR

The job fails with `All pages failed: …` and the stage fails. This is different from a partial failure,
which completes the stage.

Common causes:

| Cause | Check |
| --- | --- |
| `STORAGE_PATH` mismatch | Rendered files exist but the worker looks elsewhere |
| Tesseract binary missing | `docker compose exec worker tesseract --version` |
| tessdata missing a language | `tesseract --list-langs` |
| Rendered images are 0 bytes | Disk full |

The book is released to `pages_selected`, so it can be re-run once fixed.

---

## 5. Extraction returns all nulls

### Diagnose

1. `SELECT status, error_log FROM jobs WHERE id='<job>';` — `All batches failed` vs `LLM returned no
   values`.
2. `SELECT batch_config, raw_response FROM llm_runs WHERE job_id='<job>';` — the raw model output is
   stored per batch.
3. Is Ollama up? `curl http://localhost:11434/api/tags`.
4. Is the model present? `docker compose exec ollama ollama list`.

### Act

| Finding | Action |
| --- | --- |
| Ollama unreachable | Start it; check `mem_limit` |
| Model missing | `make download-model` |
| `raw_response` contains reasoning text | Thinking model went through `/v1`; set `LLM_NATIVE_ENDPOINT=true` |
| Timeouts | Raise `NATIVE_TIMEOUT_SECONDS` or reduce batch parallelism |
| OCR text empty | Fix OCR first — extraction cannot invent values |
| Genuinely absent fields | Expected; an all-null batch is a valid answer |

---

## 6. Redis unavailable

**Symptoms:** SSE clients freeze; rate limiting silently stops; Celery stops consuming; the pipeline
lock fails open.

1. `docker compose ps redis`
2. `docker compose logs redis`
3. Restart it. AOF persistence means queued tasks survive.

The application degrades rather than failing requests, which is deliberate — but it also means "no
progress" may be a Redis problem, not a pipeline problem.

---

## 7. Disk full

Storage grows with every rendered page, processed page and preview.

```bash
docker system df
du -sh /var/lib/docker/volumes/* | sort -h
```

Safe to delete: cached previews (`thumbnails/*/previews`), processed images that can be regenerated.
**Not safe:** `pgdata`, `storage_data/uploads`, `backup_data`.

Then re-render or re-preprocess as needed.

---

## 8. Maintenance mode

Enable from **Admin → System**, or `PUT /api/admin/maintenance`.

- Non-admin API traffic returns `503`.
- Admins keep access, so you can turn it off.
- The state is cached and reconciled every 10 s; changes are not instantaneous for every request.
- An optional `maintenance_until` auto-expires it.

Use it before a migration or a model swap, not as a substitute for stopping the stack.

---

## 9. Login and session problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| `403 CSRF validation failed` on every mutation | Frontend and API on different origins | Serve both on one host with `/api` |
| Immediately logged out | `COOKIE_SECURE=true` without HTTPS | Fix TLS, or set `false` locally |
| `401 Invalid or expired session` after a password change | `token_version` bumped | Expected — sign in again |
| Pending user sees the holding screen forever | Awaiting admin approval | **Admin → Users → Approve** |
| Verification email never arrives | SMTP disabled or misconfigured | Check `SMTP_*`; in-app notifications still work |
| Password reset link invalid | Expired (60 min) or already used | Request a new one |

---

## 10. Queue backed up

```sql
SELECT job_type, status, count(*) FROM jobs GROUP BY 1,2 ORDER BY 1,2;
```

Remember: **one worker, concurrency 1**, and a single global pipeline lock. A backlog is normal when a
long extraction is running; it is not parallelism you can scale horizontally without changing the lock.

To inspect live: Flower on the internal network (`FLOWER_BASIC_AUTH` required).

---

## 11. Escalation checklist

Before escalating, capture:

1. `GET /api/health` output.
2. `make status`.
3. The `jobs` row(s) for the affected book.
4. The `book_stage_status` rows for that book (all attempts).
5. Worker log excerpt around the failure.
6. `llm_runs.raw_response` if extraction is involved.

That set answers almost every "why is this book stuck" question without reproducing anything.

---

## 12. Better Stack alerts

Hosted monitoring (Better Stack, free tier). Alerts arrive by email from Better Stack itself, so they
work even when the app's SMTP is down.

| Alert | Fires when | First action |
| --- | --- | --- |
| **OpenBookMap API health** | `/api/health` missing `"status":"ok"` for 3 min | `make status`, then §11 capture set; if the host is down, `docker compose up -d` |
| **OpenBookMap login page** | `/login` not 200 for 3 min | Check `frontend` container and proxy routing (`make logs-frontend`) |
| **OpenBookMap homepage** | `/` not 200 for 3 min | Full CF → Traefik → app path broken; check proxy and origin reachability |
| **daily-backup** | No heartbeat ping for 36 h (period 24 h + grace 12 h) | Check `docker compose logs backup` and `ls -la` the backup volume; a failed `pg_dump` never pings, so this also catches silent failures |
| **host-watchdog** | Watchdog `/fail` ping (worker/backend/frontend/proxy container down, disk > 85 %, or jobs running > 90 min) or missed 5-min ping | `make status` for container states, `df -h` for disk, `SELECT * FROM jobs WHERE status='running'` for stuck jobs; restarts: `docker compose up -d <service>` |

Failures from the watchdog also create an **admin in-app notification** ("Host watchdog alert") via
the backend relay (`backend/app/services/watchdog_service.py`), so the alert survives a dead SMTP.

Both heartbeats must only be pinged on success. The URLs live in: Dokploy env
`BETTERSTACK_BACKUP_HEARTBEAT_URL` (backup service) and `/etc/betterstack-watchdog.env`
(`BETTERSTACK_WATCHDOG_HEARTBEAT_URL`) on the host — never in the repo.

Verification drill (real, not simulated): `docker compose stop worker`, wait ≤ 10 min, confirm the
host-watchdog alert email arrives, then `docker compose start worker`.

---

## 13. Known-good recovery state

A healthy book at rest looks like:

| Check | Expected |
| --- | --- |
| `books.status` | matches the last stage |
| `book_stage_status` | one latest attempt per stage, no `processing` left behind |
| `jobs` | no `queued`/`running` older than a few minutes |
| `pages` | one row per rendered page, `image_path` set |
| `ocr_results` | one row per OCR'd page |
| `metadata` | present once extraction has run |
