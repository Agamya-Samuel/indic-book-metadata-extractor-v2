# 008 — UI/UX Workflow + Admin Overhaul: Execution Checklist

Companion to `plans/006-ui-ux-workflow-admin.md` (decisions, root causes,
file map, risks) and `learnings/007-ui-ux-workflow-admin-audit.md` (findings,
methodology). Work top-to-bottom; do not skip the exit criteria.

## Environment

- [ ] `make up` and confirm `make status`; stack is currently **down**
      (only unrelated `algogini-*` postgres/redis containers are running)
- [ ] `make migrate`; ensure Ollama model present (`make download-model` if not)
- [ ] Pick a real scanned Telugu/Hindi PDF (≤20 MB) — ground-truth corpus:
      `backend/tests/fixtures/ground_truth/manifest.jsonl`
- [ ] Note: worktree carries **unrelated uncommitted backend work (auth/RBAC)**.
      Commit only files this checklist touches.

## Phase 0 — Foundations (no visible change)

- [ ] `frontend/src/lib/workflow-state.ts` + `.test.ts` (derivation table in plan §4.1)
- [ ] Extend `frontend/src/lib/workflow-resume.ts` instead of duplicating it
- [ ] `frontend/src/hooks/use-job-progress.ts` (job scoping; plan §3.1 fix)
- [ ] `frontend/src/hooks/use-unsaved-changes.ts`
- [ ] `frontend/src/components/shared/save-bar.tsx`
- [ ] `frontend/src/components/shared/job-progress-card.tsx` + `Progress` variants
- [ ] Fix `use-sse.ts`: consume `snapshot`, real `connectionMode`, fallback banner
- [ ] `button.tsx` size scale; `error-handler.ts` `toastError()`
- [ ] Exit: `pnpm vitest` green, `pnpm lint`, `tsc --noEmit`, no visual change

## Phase 1 — P0 defects (fix order)

- [ ] 1. LLM config escape hatch (plan §5 Phase 1.1; root cause #1)
- [ ] 2. OCR editor: `key`, dirty tracking, empty text, boxes read-only (root #2)
- [ ] 3. Stepper rewrite driven by `/books/{id}/stages` (root #3, #4)
- [ ] 4. Re-run OCR backend guard + confirm dialog + `POST /books/{id}/jobs/{job_id}/cancel`
- [ ] 5. Preprocessing: per-page config seed, Preview (temp file) vs Apply (root #5)
- [ ] Exit: each fix reproduced on a real book before moving on

## Phase 2 — Workflow polish

- [ ] Upload: progress %, cancel, locked form, single error surface
- [ ] Select pages: lazy thumbnails, range select, sticky bar
- [ ] Page extraction job wired into `/extracting-pages?job=<id>` (needs Phase 3.7)
- [ ] Preprocessing: rotation UI, Advanced section, before/after, bulk apply
- [ ] OCR processing: `JobProgressCard`, phase labels, cancel, partial results
- [ ] OCR review: sticky toolbar, low-confidence nav, empty-OCR state, SaveBar
- [ ] LLM config: real `batch_group` counts, preflight, persistence, stale warning
- [ ] Metadata review: SaveBar, evidence UI, jump nav, "n of 52", field revert

## Phase 3 — Backend reliability

- [ ] Threadpool for `run_pipeline` (preview + apply), thumbnails; semaphore
- [ ] `POST /books/{id}/preprocessing` bulk endpoint with per-page progress
- [ ] Cancel: `celery_app.control.revoke(job.celery_task_id)` in
      `admin_service.cancel_job` + book-level cancel
- [ ] `has_metadata` filter before pagination; correct `total`/`total_pages`
- [ ] Rotation fields (`rotation`, `rotation_angle`) in `PreprocessingConfig`
      + `preprocessing.py` (order: coarse → tone → binarize → deskew → fine)
- [ ] `JobType.PAGE_EXTRACTION` + `backend/app/tasks/page_tasks.py` +
      `POST /books/{id}/pages` async path (plan §5 Phase 3.7)
- [ ] `PUT /metadata` stops auto-completing; `POST /books/{id}/review/complete`
- [ ] `PageResponse.has_processed_image`

## Phase 4 — Admin restructure

- [ ] `admin/layout.tsx` left sidebar (`lg:grid-cols-[240px_minmax(0,1fr)]`),
      drawer on mobile; delete `admin-sidebar.tsx` top bar
- [ ] `PageHeader` on Operations/Books/Jobs
- [ ] `/admin` → Operations: KPI strip, live queue, global failures, auto-refresh
- [ ] `/admin/books` and `/admin/jobs` onto `data-table.tsx`; single chrome;
      per-row pending; `Link` not `window.location.href`
- [ ] Fix `progress * 100` double scaling (one place, `Progress` component)
- [ ] Keep `/admin/jobs` deep links working (no route deletions)

## Phase 5 — Verification + docs

- [ ] Unit tests: `workflow-state`, job scoping, `useUnsavedChanges`,
      `text-editor`, admin progress rendering
- [ ] Playwright happy path on real book (plan §5 Phase 5.2 assertions)
- [ ] Failure paths: Ollama down, cancel OCR, cancel page extraction mid-render,
      re-run OCR over metadata, admin reset, `has_metadata` pagination,
      review-complete with empty fields
- [ ] `pnpm lint && pnpm test && tsc --noEmit`; backend `pytest`, `ruff`
- [ ] Update `docs/user-guide.md`, `docs/known-issues.md`
- [ ] Commits: logical increments, heading + body, no co-author lines
- [ ] Update this checklist and `learnings/README.md` index when done
