# 006 — UI/UX Overhaul: Book Workflow + Admin Operations

**Status:** Approved — ready to implement.
**Owner:** user · **Study record:** `learnings/007-ui-ux-workflow-admin-audit.md`
**Task checklist:** `todos/008-ui-ux-workflow-admin.md`
**Date:** 2026-11-11

## 1. Goal

Make the seven-stage book workflow coherent and honest about its state,
eliminate defects that lose or misapply data, and restructure the admin area
around an Operations page. Every long operation gets real feedback (progress,
phase, cancel, failure with recovery). No new dependencies, no rebuilds.

## 2. Decisions agreed with the user

| Topic | Decision |
|---|---|
| Sequencing | P0 defects → workflow polish → admin |
| Backend changes | Allowed, targeted only (no rewrites) |
| Rotation | Manual rotation: 90° steps + fine angle, applied before deskew |
| Save model | Explicit save + sticky action bar + unsaved-changes guard |
| Processing screens | Keep `/ocr-processing` and `/extracting-pages`; stepper shows them as running sub-states of their owning stage |
| Re-run OCR with metadata | Warn with named impact, keep metadata text, mark `needs_review`, reset downstream stage status |
| OCR correction | Textarea is the single source of truth; bounding boxes read-only ("original OCR") |
| Admin | Restructure around an Operations page; Books and Jobs stay separate routes |
| Admin navigation | True left sidebar (sticky, drawer on mobile); duplicate admin top bar removed |
| Book completion | Metadata save keeps `awaiting_review`; explicit "Mark review complete" completes the workflow |
| Preprocessing preview | Temp preview file; nothing committed until Apply |
| Page extraction | Moves to a Celery job with per-page progress and cancel |
| Verification | Local stack (`make up`) + real book + lint/typecheck/unit/e2e |

## 3. Root causes (verified, file:line)

1. `frontend/src/app/books/[bookId]/llm-config/page.tsx:201` — progress screen
   gated on `isPolling || isComplete`; `useJobPolling` falls back to
   `filteredJobs[0]` (jobs ordered `created_at.desc()` in `backend/app/api/books.py:336`)
   so a completed run makes the config form permanently unreachable;
   "Back to Config" (`setActiveJobId(null)`) cannot escape.
2. `frontend/src/components/ocr/text-editor.tsx:63` — `editedText || displayText`
   blocks clearing text; `ocr-review/page.tsx` renders `<OcrTextEditor>` without
   a `key`, so `editedText`/`editMode` bleed across pages; saving on page 5 can
   write page 4's text.
3. `frontend/src/components/shared/workflow-stepper.tsx:96,122` — stage lookup
   `label.toLowerCase().replace(/ /g,"_")` yields `select_pages`/`ocr_review`/
   `llm_config`/`metadata_review`; backend stages are `page_selection`/`ocr`/
   `llm_extraction`/`human_review`/`completion`. The `stages` prop is never passed.
4. `frontend/src/stores/workflow-store.ts` — `STEP_MAP` maps `ocr_running → 3`,
   `ocr_complete → 5`; pages write `completedStep` optimistically
   (`preprocessing/page.tsx:98`, `extracting-pages/page.tsx:81`, `llm-config/page.tsx:150`).
5. `backend/app/api/books.py:230` — `run_ocr` only accepts `pages_selected`;
   re-run from the workflow 400s. Admin bypasses via `admin_service.rerun_ocr`.
6. `frontend/src/app/books/[bookId]/preprocessing/page.tsx` — one `config` state
   for all pages, never seeded from `page.preprocessing_config`; "Preview
   Current Page" calls `updatePreprocessing` (persists PNG + config);
   "Apply to All" fires N parallel blocking PUTs.
7. `backend/app/api/pages.py:33` — `preprocessing.run_pipeline` (OpenCV) runs on
   the event loop; `books.py` upload/`select_pages` render PDFs synchronously.
8. `backend/app/services/admin_service.py:130` — cancel flips DB status only;
   `Job.celery_task_id` exists but is never revoked.
9. `backend/app/api/admin.py` + `admin_service` — `has_metadata` filter applied
   after pagination; `total` overwritten with `len(items)`.
10. `frontend/src/app/admin/page.tsx:204,208`, `admin/jobs/page.tsx:209,213` —
    `job.progress * 100` on a 0–100 value (double-scaled).
11. `frontend/src/hooks/use-sse.ts` — `snapshot` event ignored;
    `use-book-status.ts` `connectionMode` only ever `"sse"`/`"idle"`, so the
    polling-fallback warning is unreachable.
12. `backend/app/api/metadata.py:89` — any metadata save while `AWAITING_REVIEW`
    completes `human_review` + `completion` (premature "complete").
13. Hidden preprocessing ops the UI can't see or disable: `upscale_to_300dpi`,
    `remove_borders`, `sauvola_window/k`, `auto_preprocess` (schema drops them;
    `run_pipeline` merges backend defaults). Frontend default (`denoise: true`,
    strength 7) disagrees with backend default (`denoise: false`, strength 10).
14. No rotation control exists anywhere; `preprocessing.py:187` only auto-rotates
    inside `deskew()`.

## 4. Target architecture (frontend)

### 4.1 One workflow state model

New pure module `frontend/src/lib/workflow-state.ts` (unit-tested):

```ts
type StepKey = "upload" | "pages" | "preprocessing" | "ocr" | "ocr_review" | "llm" | "review";
type StepState = "not_started" | "current" | "complete" | "failed" | "stale";

deriveWorkflowState({ book, stages, pages, jobs }): {
  steps: Record<StepKey, { state: StepState; detail?: string; href: string }>;
  currentStep: StepKey;
  processing: null | { kind: "page_extraction" | "ocr" | "llm"; job?: JobResponse };
}
```

Derivation rules (single source of truth):

| Step | complete when | running when |
|---|---|---|
| upload | book exists | — |
| pages | `pages.length > 0` | page-extraction job queued/running |
| preprocessing | every page has `preprocessing_config` | — |
| ocr | latest `ocr` stage `completed` | OCR job queued/running |
| ocr_review | `llm_extraction` stage initiated, or any `corrected_text` exists | — |
| llm | `llm_extraction` stage completed (metadata exists) | LLM job queued/running |
| review | `human_review` stage completed | — |

`lib/workflow-resume.ts` already maps stages → resume targets and is extended,
not duplicated. `stores/workflow-store.ts` is reduced to UI-only state
(selection index, drafts); all `setCompletedStep` calls are removed.

### 4.2 Shared workflow shell

`components/shared/workflow-shell.tsx` (client): takes `bookId` + optional
step, fetches `getBook` + `getBookCurrentStages` via React Query (deduped with
page queries), renders `<WorkflowStepper>` (7 steps, real states, links,
failure/stale markers) and a contextual back link. Stage pages keep their own
`PageContainer`/`PageHeader`.

### 4.3 Shared primitives (reuse-first)

- `useJobProgress` hook — wraps `useJobPolling` with job scoping
  (job must belong to the current run), phase label, elapsed, cancel.
- `SaveBar` — sticky bottom bar: dirty count, Save, Discard, unsaved guard.
- `useUnsavedChanges(active)` — `beforeunload` + in-app link interception.
- `Progress` — labeled + indeterminate variants, one 0–100 contract.
- `JobProgressCard` — phase, %, item counter ("page 12 / 84"), elapsed, cancel,
  failure with retry.
- Admin `data-table.tsx` replacing the four copies of
  `div.overflow-x-auto > table` chrome.
- Fix `button.tsx` size scale (remove `min-h-11` from `sm`; one height per size).

## 5. Phases

### Phase 0 — Foundations (no visible change)

1. `workflow-state.ts` + tests; extend `workflow-resume.ts`.
2. `useJobProgress`, `SaveBar`, `useUnsavedChanges`, `JobProgressCard`,
   `Progress` variants.
3. Fix `useSSE`: consume `snapshot` (seed book/jobs caches), derive
   `connectionMode = "sse" | "polling" | "idle"` from real events (`connected`,
   `error`, heartbeat timeout), surface the fallback banner.
4. Normalize error copy in `error-handler.ts`; add `toastError(err, fallback)`.

Exit criteria: `vitest` green, no visual change, lint/typecheck clean.

### Phase 1 — P0 workflow defects

1. **LLM config escape hatch.** Job scoping (only jobs started during the
   current run count), progress rendered as a banner above the form instead of
   an exclusive screen, explicit "Run again" when a prior run exists,
   preflight `GET /models` check ("Ollama unreachable" state).
2. **OCR editor.** `key={currentPage.id}`; dirty tracking; save disabled when
   clean; empty text allowed; boxes labelled "original OCR, not updated by
   edits"; unsaved guard on page switch and nav; optimistic cache update.
3. **Stepper.** Derived model; pass `stages`; processing routes shown as the
   owning stage's running sub-state; remove optimistic writes.
4. **Re-run OCR.** Backend: allow from `ocr_complete`, `llm_running`,
   `awaiting_review`, `complete`; reset `ocr`/`llm_extraction`/`human_review`
   stage status, set `needs_review = true`, keep metadata content; return an
   impact summary. Frontend: confirm dialog listing what becomes stale. Add
   `POST /books/{id}/jobs/{job_id}/cancel` (workflow-side cancel).
5. **Preprocessing correctness.** Seed controls from `page.preprocessing_config`;
   Preview (temp file + URL, no DB write) split from Apply (writes image +
   config); dirty indicator; Reset to defaults; align frontend defaults with
   the backend schema; per-page "processed" badge (`PageResponse` gains
   `has_processed_image: bool`).

Exit criteria: all five reproduced-then-fixed on a real book; regression tests
for `deriveWorkflowState`, job scoping, editor state.

### Phase 2 — Workflow polish

**Upload** — `onUploadProgress` % + AbortController cancel, size guidance,
413 message, post-upload summary, no duplicate toast+inline error, form locked
while uploading with the chosen file still visible.

**Select pages** — lazy/virtualized thumbnail grid (IntersectionObserver,
`unoptimized` only for visible cells), "N of M selected", shift range-select,
sticky selection bar. Submit → `POST /books/{id}/pages` creates a
**page-extraction job**; navigate to `/extracting-pages?job=<id>` (no
`sessionStorage` handoff, refresh-safe). `/extracting-pages` shows
`JobProgressCard` ("Rendering page 12 of 48"), elapsed, cancel, partial-result
summary, retry on failure.

**Preprocessing** — rotation controls (↺/↻ 90°, reset, fine-angle slider, shown
before deskew, detected deskew angle displayed); "Advanced" section exposing
upscale-to-300dpi, border removal, Sauvola window/k; before/after comparison
with a "preview is not saved" notice; Apply-to-all via one bulk endpoint with
per-page progress and partial-failure report; wider preview, sticky thumbnail
rail header, no nested 600px scroll trap.

**OCR processing** — `JobProgressCard` with page counter, cancel, elapsed,
phase labels (preprocessing → OCR), "view results so far" when terminal.

**OCR review** — sticky toolbar (page nav, confidence filter,
"next low-confidence", save state); empty-OCR state with link back; page list
with per-page status; SaveBar + unsaved guard.

**LLM config** — real batch count from `fieldDefs` grouped by `batch_group`;
per-batch progress; per-book config persistence (localStorage) with reset;
prompt editors collapsed by default; token/pages estimate; stale-metadata
warning when re-running.

**Metadata review** — sticky SaveBar with dirty count, discard, and "Mark
review complete"; evidence UI (confidence chip + source page link into OCR
review at that page + expandable snippet + explicit "no evidence" styling);
section jump nav; "n of 52 filled"; field search; per-field revert to
extracted value.

**Cross-cutting** — every mutation: pending state on its own control,
duplicates disabled, success confirmation, error with recovery; skeletons on
first load, subtle refetch indicator after.

### Phase 3 — Backend reliability

1. `run_in_threadpool` for `preprocessing.run_pipeline` (preview + apply),
   thumbnails, and storage-touching metadata reads; bound with a semaphore.
2. Bulk endpoint `POST /books/{id}/preprocessing` (all pages or `page_ids`),
   sequential with progress via job/SSE; returns per-page results.
3. Cancel: `celery_app.control.revoke(job.celery_task_id, terminate=False)` in
   `admin_service.cancel_job` and the new book-level cancel endpoint; guard
   against late workers writing status back (tasks already re-read the job —
   verify and patch).
4. Admin `has_metadata` filter pushed into SQL before pagination; correct
   `total`/`total_pages`.
5. Rotation: `rotation: int` (0/90/180/270) + `rotation_angle: float` (−15…15)
   in `PreprocessingConfig`; coarse rotation then fine rotation before deskew;
   persisted in `preprocessing_config` JSON (no migration).
6. Regenerate the processed image when config changes; source image untouched.
7. **Page extraction job:** add `JobType.PAGE_EXTRACTION = "page_extraction"`
   (string column, no migration) + `backend/app/tasks/page_tasks.py`;
   `POST /books/{id}/pages` validates the selection, cancels any active
   page-extraction job, creates the job, enqueues rendering; the task renders
   each page, updates `job.progress` per page, publishes SSE `job_progress`,
   replaces previous pages, completes the `page_selection` stage
   (initiated → processing → completed); failure marks the stage failed with
   the render error, partial pages stay usable; book status → `pages_selected`
   only on success; add `page_extraction` to the admin job-type filter.
8. **Review completion:** `PUT /books/{id}/metadata` keeps `awaiting_review`
   and only sets `human_review` to `processing`; new
   `POST /books/{id}/review/complete` requires metadata to exist and no running
   jobs, then completes `human_review` + `completion` and sets `complete`
   (idempotent); frontend exposes it in the save bar with a confirmation
   listing empty/low-confidence fields.

### Phase 4 — Admin restructure

**Navigation** — delete `components/admin/admin-sidebar.tsx` as a top bar.
`admin/layout.tsx` becomes `lg:grid-cols-[240px_minmax(0,1fr)]`, sidebar sticky
at `top-[var(--nav-height)]`, Operations/Books/Jobs with `aria-current`, mobile
drawer (focus-trapped). Global `AppNavbar` stays; `PageContainer` adjusted so
gutters are not doubled. `PageHeader` (title, count, last-updated, refresh) on
all three pages.

**`/admin` — Operations** — KPI strip (total books, with metadata, running,
queued, failed 7d, success rate); Live queue (all queued/running jobs with real
progress, elapsed, cancel, open book); Recent failures (global latest 5 failed
jobs from its own query, not derived from a 10-row page, each with error
excerpt + recovery link); auto-refresh toggle with "updated 12s ago", pauses
when the tab is hidden.

**`/admin/books`** — one chrome (no Card-inside-Card), shared table primitive,
sticky header. Columns: book, language, pages, status, metadata, updated,
actions. Actions (open, reset, re-run OCR, re-run extraction, delete) each with
own pending state and confirm copy naming exactly what is destroyed. Fix
pagination counts; "no results" with filter reset.

**`/admin/jobs`** — shared table, filters with "clear", real progress, cancel
per row (only that row pending), `Link` instead of `window.location.href`,
auto-refresh while any job is live, empty state.

**Cross-cutting** — progress scale fixed once; consistent `StatusBadge`,
timestamps, truncation with title, row actions.

### Phase 5 — Verification and documentation

1. Unit tests: `workflow-state`, `useJobProgress` scoping, `useUnsavedChanges`,
   `text-editor` empty/dirty behaviour, admin progress rendering.
2. Playwright happy path on the local stack with a real Telugu book:
   upload → select → preprocess (rotate) → OCR → correct → LLM → metadata save,
   asserting stepper states and no console errors.
3. Failure paths: kill Ollama mid-run; cancel OCR; cancel page extraction
   mid-render; re-run OCR over existing metadata; admin reset; pagination with
   `has_metadata`; review-complete with empty fields.
4. `pnpm lint`, `tsc --noEmit`, `vitest`, backend `pytest`, `ruff`.
5. Update `docs/user-guide.md` (new controls, save semantics),
   `docs/known-issues.md`, commit in logical increments (heading + body, no
   co-author lines).

## 6. File-level change map

**New**
- `frontend/src/lib/workflow-state.ts` (+ `.test.ts`)
- `frontend/src/components/shared/workflow-shell.tsx`
- `frontend/src/components/shared/save-bar.tsx`
- `frontend/src/components/shared/job-progress-card.tsx`
- `frontend/src/hooks/use-job-progress.ts`
- `frontend/src/hooks/use-unsaved-changes.ts`
- `frontend/src/components/admin/data-table.tsx`
- `frontend/src/components/admin/admin-nav.tsx` (sidebar + mobile drawer)
- `backend/app/tasks/page_tasks.py`
- `backend/app/api/` — bulk preprocessing + review-complete endpoints

**Reworked**
- `frontend/src/components/shared/workflow-stepper.tsx`, `button.tsx` (sizes)
- `frontend/src/hooks/use-sse.ts`, `use-book-status.ts`, `use-job-polling.ts`
- `frontend/src/stores/workflow-store.ts` (reduce scope)
- Every `frontend/src/app/books/[bookId]/*/page.tsx`
- `frontend/src/components/ocr/text-editor.tsx`, `ocr-review/page.tsx`
- `frontend/src/components/metadata/metadata-form.tsx`, `metadata-review/page.tsx`
- `frontend/src/app/admin/{layout,page}.tsx`, `admin/books/page.tsx`,
  `admin/jobs/page.tsx`; delete `admin-sidebar.tsx`
- `frontend/src/lib/api.ts` (bulk preprocess, cancel, review-complete,
  `has_processed_image`, rotation fields)
- `backend/app/schemas/page.py`, `services/preprocessing.py`, `api/pages.py`,
  `api/books.py`, `services/admin_service.py`, `api/admin.py`,
  `api/metadata.py`, `tasks/ocr_tasks.py` (cancel-safe writes)

## 7. Dependencies and environment

- **Frontend:** Next 16 (App Router), React 19, TanStack Query 5, Zustand 5,
  Tailwind CSS 4, axios, sonner, react-konva/konva, react-dropzone, fuse.js.
  **No new packages needed.** Vitest + @testing-library + Playwright exist.
  ⚠️ This Next.js version has breaking changes vs. training data — read
  `node_modules/next/dist/docs/` before writing route/layout code
  (`frontend/AGENTS.md` rule).
- **Backend:** FastAPI, SQLAlchemy async + asyncpg, Celery (Redis broker),
  Redis pub-sub SSE (`sse_service.py`), OpenCV/NumPy, Tesseract, Ollama
  (Qwen 2.5 7B default). Alembic migrations — **none required** by this plan
  (rotation and job type are JSON/string, no schema change).
- **Local stack:** `make up` (docker compose: postgres, redis, ollama,
  backend :8000, frontend :3000, workers for OCR/LLM), `make migrate`,
  `make logs-backend` / `logs-worker-ocr` / `logs-worker-llm`,
  `make status`, `make reset-db`. API base `http://localhost:8000/api`.
- **Test data:** needs a real scanned Telugu/Hindi PDF (≤20 MB). Ground-truth
  corpus lives in `backend/tests/fixtures/ground_truth/` with PDFs referenced
  in `manifest.jsonl` — use one of those if no other book is at hand.
- **Repo note:** the worktree currently carries unrelated uncommitted backend
  work (auth/RBAC: `012_auth_rbac.py`, `app/core/security.py`, model/config
  edits). Do not touch or commit those; commit only files this plan changes.

## 8. Risks

- **Rotation order**: fine rotation interacts with binarization/border removal.
  Order: coarse rotate → grayscale/contrast → binarize → deskew (auto) → fine
  rotate last, or clamp fine angle to ±15° and document. Decide with a visual
  fixture during implementation.
- **Job scoping**: use `startedAt` recorded at run start; fall back to
  `job.id !== lastTerminalId` if timestamps are unreliable.
- **Re-run OCR resetting stages**: `StageManager` attempt rows accumulate;
  verify `get_current_stages` returns the new attempt and the resume banner
  updates.
- **Admin restructure churn**: existing deep links to `/admin/jobs` must keep
  working; no route deletions.
- **Threadpool/OpenCV**: releases the GIL; keep the semaphore small so
  preprocessing does not starve OCR workers.
- **Page-extraction job**: re-selection while active must cancel cleanly; the
  task must not resurrect pages after a cancel. Verify with a race test.
- **Review completion**: books already marked `complete` by the old behaviour
  stay complete; no data migration, only new saves use the explicit action.

## 9. Out of scope

- Authentication on the UI (tracked separately via the in-flight RBAC work).
- pgvector semantic search, Telugu/Hindi language expansion, OCR accuracy work
  (covered by plans 002–004).
- Word-level box editing in OCR review (deferred; boxes become read-only).
