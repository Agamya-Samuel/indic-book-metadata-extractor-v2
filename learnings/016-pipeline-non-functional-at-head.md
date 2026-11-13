# 016 — The Pipeline Could Not Process a Book at HEAD (three defects)

- **Date:** 2026-11-11
- **Study context:** Produced while measuring the resource profile for [015](015-service-inventory-and-gating.md). Running a real book end to end was a prerequisite, and the pipeline could not complete. Also directly relevant to the serial single-book queue (one book fully processed before the next), which builds on this same stage machinery.
- **Status:** All three fixed and **verified end to end**. Commits `139fde7`, `b2b3fa4`, `050e9e0`.

## Summary

HEAD could not process a book at all. Three independent defects, each masking the next: the stage-tracking feature was broken five ways so **every** stage transition raised; a preprocessing guard matched the job that dispatched it so **OCR had not run since 2026-09-01**; and, once both were fixed, the LLM persistence path **self-deadlocked forever** with no error and no timeout. All three are fixed; a 30-page Telugu book now reaches `awaiting_review` with 8 `llm_runs` and a metadata row persisted.

## Key findings

### 1. Stage tracking was broken in five ways (`139fde7`)

| # | Defect | Effect |
|---|---|---|
| 1 | Six bare `get_stage(db, ...)` calls in `stage_manager.py` bound to the 3-arg function imported from `app.models.stage` instead of the static method | Arguments shift by one → `book_id`=<AsyncSession>, `attempt`='upload' → Postgres `operator does not exist: integer = character varying`. **Every** stage operation failed |
| 2 | `initiate_stage` → `complete_stage` without `start_stage`, at upload / human_review / completion | `complete_stage` requires `PROCESSING` → upload always failed |
| 3 | `page_selection` was only ever *completed*, never initiated | "Stage not found"; also blocked `ocr` via sequential validation |
| 4 | `BOOK_STATUS_MAP` had no `COMPLETED` entries for upload / page_selection | Book status **regressed to `uploaded`** after page selection, so `run-ocr` rejected it |
| 5 | `_derive_book_status` returned the **earliest** mapped stage | Progress after OCR completed was masked |

Also in the same fix: `admin_service.py` never imported `async_session_factory`/`StageStatus`, so reset and both rerun paths raised `NameError`; the rerun guards called `complete_stage` from `INITIATED` where it is always rejected (now `cancel_stage`); API handlers opened a **separate** DB session for stage writes, bypassing the request transaction and making the handlers untestable; `retry_extraction` allowed `COMPLETE` but delegated to a handler that only allowed `OCR_COMPLETE`; and `app/models/__init__.py` did not import `app.models.stage`, so the table only existed if some other module imported it first — making the suite import-order dependent.

Legacy books (no stage rows) are now allowed through sequential validation instead of being locked out. **This matters for production**: its 10 books predate the feature and have zero stage rows, so without it every operation on them would fail.

### 2. OCR had been dead since 2026-09-01 (`b2b3fa4`)

`_has_active_job_for_book` matched **the job that dispatched the task**. The API creates the OCR job as `QUEUED`, then dispatches preprocessing; preprocessing looked for "another active job", found itself, and returned — skipping both preprocessing and the chained OCR run.

Evidence: **every** job in the production database is dated on or before **2026-09-01**, which is exactly when this guard landed (`34e952e`). Fixed by excluding the dispatching job id.

### 3. LLM persistence self-deadlocked (`050e9e0`)

`_persist_extraction_results` opened its own session, flushed rows whose foreign keys reference `books` (taking a **KEY SHARE** lock on that row), then opened a **second** connection and requested `SELECT books ... FOR UPDATE` — which conflicts with KEY SHARE. Observed directly in `pg_stat_activity`:

```
15058  idle in transaction  ClientRead   SELECT ... FROM books WHERE id=$1
15059  active               Lock/transactionid  SELECT ... FROM books WHERE id=$1 FOR UPDATE
```

Both sessions from the same worker container. Session A held the lock waiting on Python; Python awaited session B; neither progressed. The job sat at `running 100%` with 8 successful LLM calls, **`llm_runs=0` and `metadata=0`** — a silent hang, not an error.

Fixed by running stage transitions on the caller's session, so the lock is self-owned and the stage write commits atomically with the data it describes. The same latent defect existed in the OCR finalisation path and was fixed alongside; it survived only because its transaction had not flushed a book-referencing write before that point.

### 4. Why all three stayed hidden

- Defects 1 and 2 are both in the deployed revision `861ce25`, but production's `book_stage_status` has **zero rows** and no book has been created since 2026-09-08 — so neither path was ever exercised there.
- Defect 3 was **created by fixing defects 1–2**: with the broken stage call, `complete_stage` raised immediately instead of blocking. Each fix exposed the next.
- The stage feature shipped with **no test coverage at all**, which is how five defects landed together.

### 5. Verification

- `test_api_books.py`: **15 failed → 19 passed**. `test_api_extraction.py`: **5 failed → 6 passed**. Full suite: **236 passed, 1 skipped**.
- Added 9 unit tests for the stage machinery (transitions, derived status, guards, sequential validation, legacy path) — there was previously zero coverage.
- End to end on a 4 vCPU / 16 GB node: upload → page selection → OCR (30 pages) → extraction → **`awaiting_review`**, with `8 llm_runs` and `1` metadata row persisted.
- **Reproduced independently by re-delivery**: restarting the worker caused Celery (`acks_late`) to re-queue and re-run the hung task, which then completed cleanly — confirming the fix rather than a lucky run.

### 6. Related finding worth keeping

`OCR_THREAD_WORKERS` / `OCR_BATCH_SIZE` are declared in `config.py` and passed in all three compose files, but **no code reads them**. The comment claiming the worker is "optimized with thread-based parallelism" is stale — pages are processed strictly sequentially. Dead config that misleads resource planning.

## Recommendation

- **Push `139fde7`, `b2b3fa4`, `050e9e0`** before any redeploy. Production currently cannot process a book; note `autoDeploy=true` with `triggerType=push`, so a push deploys. `origin/main` was still at the broken `861ce25` at the time of writing.
- **Treat stage transitions as caller-session-only.** Do not reintroduce a second session inside a caller's open transaction — it is the same deadlock shape.
- **Pin `think:false` for thinking-capable models** (recorded separately in [005](005-llm-model-evaluation.md)) — a comparable silent-empty failure mode.
- Before the serial single-book queue (`plans` decision 2a), note it depends on this stage machinery, which is now trustworthy for the first time.

## Next steps

1. Push the three fix commits (user decision; `autoDeploy` makes this a production deploy).
2. Consider a **backfill migration** for the 10 legacy production books: the current shim lets them through, but they have no stage history. Alternative chosen deliberately — inferring history would mean inventing timestamps.
3. Remove the dead `OCR_THREAD_WORKERS` / `OCR_BATCH_SIZE` config, or wire it up.
4. Separate sweep for CI debt: `ruff format --check` wanted to reformat **39 files** at HEAD, plus pre-existing lint errors — left alone so this fix was not buried.

## References

- Commits: `139fde7` (stage), `b2b3fa4` (OCR guard), `050e9e0` (deadlock)
- Raw profile and phase timings: [`backend/reports/pipeline-profile-oki.json`](../backend/reports/pipeline-profile-oki.json)
- Related: [015](015-service-inventory-and-gating.md) · [005](005-llm-model-evaluation.md) · [013](013-verified-shortlist-and-ocr.md)
- Code: [`stage_manager.py`](../backend/app/services/stage_manager.py) · [`ocr_tasks.py`](../backend/app/tasks/ocr_tasks.py) · [`llm_tasks.py`](../backend/app/tasks/llm_tasks.py)
