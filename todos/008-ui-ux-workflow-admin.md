# 008 — UI/UX Workflow + Admin Overhaul: Execution Checklist

Companion to `plans/006-ui-ux-workflow-admin.md` (decisions, root causes,
file map, risks) and `learnings/007-ui-ux-workflow-admin-audit.md` (findings,
methodology). Work top-to-bottom; do not skip the exit criteria.

> **Implementation status (2026-11-11):** Phases 0 and 1 are implemented and
> unit-verified (`vitest` 191 green, `tsc --noEmit`, `eslint` 0 errors).
> Backend reliability items 3.3/3.4/3.5/3.8 are implemented. Phase 4 layout +
> PageHeader + progress-scale fixes are implemented; the table rewrite and
> operations aggregation are not. Phase 2 polish, 3.2 (bulk preprocessing) and
> 3.7 (page-extraction job) remain. The local Docker stack did not finish
> coming up during this pass, so the "reproduce on a real book" and Playwright
> steps are **not yet done**.

## Environment

- [x] Core stack up: postgres, redis, ollama, backend, worker-ocr, worker-llm
      healthy. Wikibase/flower still restart (MySQL root password was missing
      from `.env`; added `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD`,
      `POSTGRES_PASSWORD`, `WIKIBASE_*` — `.env` is gitignored. `wikibase` has
      no compose healthcheck, so `--wait` reports it).
- [x] `make migrate` (alembic at head); `/health` returns 200
- [x] Ollama model present: `qwen2.5:7b` (4.7 GB)
- [ ] Pick a real scanned Telugu/Hindi PDF (≤20 MB) — ground-truth corpus:
      `backend/tests/fixtures/ground_truth/manifest.jsonl`
- [ ] Note: worktree carries **unrelated uncommitted backend work (auth/RBAC)**.
      Commit only files this checklist touches.

## Phase 0 — Foundations (no visible change) — DONE

- [x] `frontend/src/lib/workflow-state.ts` + `.test.ts` (derivation table in plan §4.1)
- [x] Extend `frontend/src/lib/workflow-resume.ts` instead of duplicating it
      (`resumeTargetForState`)
- [x] `frontend/src/hooks/use-job-progress.ts` (job scoping; plan §3.1 fix)
- [x] `frontend/src/hooks/use-unsaved-changes.ts`
- [x] `frontend/src/components/shared/save-bar.tsx`
- [x] `frontend/src/components/shared/job-progress-card.tsx` + canonical
      `progress.tsx` (0–100 contract, labeled/indeterminate)
- [x] Fix `use-sse.ts`: consume `snapshot`/`connected`/`heartbeat`, real
      `connectionMode` (`sse`/`polling`/`idle`), stale-stream watchdog
- [x] `button.tsx` size scale; `error-handler.ts` `toastError()`
- [x] Exit: `pnpm vitest` green (191), `pnpm lint` (0 errors), `tsc --noEmit`

## Phase 1 — P0 defects (fix order) — IMPLEMENTED (verification pending)

- [x] 1. LLM config escape hatch (plan §5 Phase 1.1; root cause #1):
      form always rendered, `startedAt` job scoping, preflight, "Run again"
- [x] 2. OCR editor: `key`, dirty tracking, empty text, boxes read-only,
      unsaved guard, optimistic cache (root #2)
- [x] 3. Stepper rewrite driven by derived state + `workflow-shell.tsx`
      (root #3, #4); optimistic `setCompletedStep` calls removed from pages
- [x] 4. Re-run OCR backend guard (any post-upload status, resets downstream
      stages, keeps metadata) + confirm dialog + Celery revoke (root #5)
      — cancel uses the existing `POST /jobs/{job_id}/cancel`
- [x] 5. Preprocessing: per-page config seed, Preview (temp file) vs Apply,
      dirty/reset, defaults aligned, rotation controls, `has_processed_image`
      badge (root #5, #13, #14)
- [ ] Exit: each fix reproduced on a real book before moving on
      (**blocked on the local stack / real PDF**)

## Phase 2 — Workflow polish

- [ ] Upload: progress %, cancel, locked form, single error surface
- [ ] Select pages: lazy thumbnails, range select, sticky bar
- [ ] Page extraction job wired into `/extracting-pages?job=<id>` (needs Phase 3.7)
- [ ] Preprocessing: before/after + bulk apply (rotation/advanced done)
- [ ] OCR processing: `JobProgressCard`, phase labels, cancel, partial results
- [ ] OCR review: sticky toolbar, low-confidence nav, empty-OCR state, SaveBar
      (empty-OCR state + unsaved guard done)
- [ ] LLM config: per-book persistence, stale warning (batch count + preflight done)
- [ ] Metadata review: SaveBar, evidence UI, jump nav, "n of 52", field revert
      (explicit review-complete done)

## Phase 3 — Backend reliability

- [x] Threadpool for `run_pipeline` (preview + apply); thumbnails/metadata reads
      and the semaphore are still pending
- [ ] `POST /books/{id}/preprocessing` bulk endpoint with per-page progress
- [x] Cancel: `celery_app.control.revoke(..., terminate=False)` in
      `admin_service` (cancel + rerun/reset/delete); book-level cancel already
      exists as `POST /jobs/{job_id}/cancel`
- [x] `has_metadata` filter before pagination; correct `total`/`total_pages`
- [x] Rotation fields (`rotation`, `rotation_angle`) in `PreprocessingConfig`
      + `preprocessing.py` (coarse → tone → binarize → deskew → fine)
- [x] Regenerate processed image on apply (source image untouched)
- [ ] `JobType.PAGE_EXTRACTION` + `backend/app/tasks/page_tasks.py` +
      `POST /books/{id}/pages` async path (plan §5 Phase 3.7)
- [x] `PUT /metadata` stops auto-completing; `POST /books/{id}/review/complete`
      + frontend "Mark review complete" confirmation
- [x] `PageResponse.has_processed_image`

## Phase 4 — Admin restructure

- [x] `admin/layout.tsx` left sidebar (`lg:grid-cols-[240px_minmax(0,1fr)]`),
      mobile drawer; delete `admin-sidebar.tsx` top bar
- [x] `PageHeader` on Operations/Books/Jobs
- [ ] `/admin` → Operations: KPI strip + live queue exist; global failures and
      `has_metadata`-aware stats still derive from the 10-row page
- [ ] `/admin/books` and `/admin/jobs` onto `data-table.tsx`; per-row pending;
      `Link` not `window.location.href`
- [x] Fix `progress * 100` double scaling (admin + dashboard)
- [x] Keep `/admin/jobs` deep links working (no route deletions)

## Phase 5 — Verification + docs

- [x] Unit tests: `workflow-state`, job scoping, `useUnsavedChanges`,
      `text-editor`, stepper
- [ ] Playwright happy path on real book (plan §5 Phase 5.2 assertions)
- [ ] Failure paths: Ollama down, cancel OCR, cancel page extraction mid-render,
      re-run OCR over metadata, admin reset, `has_metadata` pagination,
      review-complete with empty fields
- [x] `pnpm lint && pnpm test && tsc --noEmit`; backend `pytest`/`ruff` still
      pending (full-repo ruff has pre-existing violations; changed files pass
      `F`/`E9`)
- [x] Update `docs/user-guide.md`, `docs/known-issues.md`
- [ ] Commits: logical increments, heading + body, no co-author lines
- [x] Update this checklist; `learnings/README.md` index already lists 007