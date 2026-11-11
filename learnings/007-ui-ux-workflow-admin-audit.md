# 007 — UI/UX Audit: Book Workflow + Admin Dashboard

**Date:** 2026-11-11
**Companion plan:** `plans/006-ui-ux-workflow-admin.md`

## Study Context

Full UI/UX review of the seven-stage book-processing workflow (upload → page
selection → preprocessing → OCR → OCR review → LLM extraction → metadata
review) and the admin dashboard, requested before any code change. The goal was
to catalogue defects and usability gaps with verified file:line evidence, agree
on product decisions interactively, and only then produce an implementation
plan.

## Methodology

1. **Inventory** — listed the whole frontend tree (~11.8k LOC: 20 routes,
   40+ components, hooks, stores, `lib/`) and the backend (`app/` ~8.3k LOC:
   API layer, tasks, services, models, schemas) to build a file map before
   reading anything in depth.
2. **Read-through per stage** — each workflow page and its supporting
   components were read end-to-end (not skimmed): `select-pages`,
   `extracting-pages`, `preprocessing`, `ocr-processing`, `ocr-review` +
   `text-editor.tsx` + `bounding-box-canvas.tsx`, `llm-config`,
   `metadata-review` + `metadata-form.tsx`, `upload`, library pages,
   bulk operations.
3. **Backend trace** — for every frontend call, the corresponding endpoint and
   task was read (`books.py`, `pages.py`, `extraction.py`, `metadata.py`,
   `admin.py`, `library.py`, `stages.py`, `ocr_tasks.py`, `llm_tasks.py`,
   `stage_manager.py`, `sse_service.py`, `admin_service.py`,
   `preprocessing.py`, `main.py`) to check status/progress semantics, blocking
   work, and data-persistence semantics (e.g. what "Preview" actually writes).
4. **Defect verification** — every suspected bug was confirmed in code before
   reporting: e.g. job ordering (`created_at.desc()` at `books.py:336`) +
   `useJobPolling`'s fallback to `filteredJobs[0]` proves the LLM-config trap;
   the missing `key` on `<OcrTextEditor>` proves state bleed; grepping for
   `rotation` in backend and frontend proves no manual-rotation path exists.
5. **Interactive decision-making** — findings were presented grouped by
   severity; product decisions (save model, rotation, re-run policy, admin
   shape, preview semantics, page-extraction architecture) were agreed with
   the user through two rounds of questions before writing the plan.

## Summary

The workflow's plumbing (jobs, stages, SSE, design tokens) is solid, but the
UI lies about state in five places that can lose or misapply data, and the
admin area duplicates itself instead of aggregating. Fix order: P0 data-integrity
defects → stage polish → admin restructure.

## Key Findings

### P0 — data-integrity / workflow-breaking

| # | Finding | Evidence |
|---|---|---|
| 1 | LLM config unreachable after any completed run: the progress screen gates on `isPolling \|\| isComplete` while polling falls back to the newest job (always completed) | `llm-config/page.tsx:201`, `use-job-polling.ts:66-71`, `books.py:336` |
| 2 | OCR editor state bleeds across pages (no `key`); saving on page 5 can write page 4's text; textarea can never be cleared (`editedText \|\| displayText`); save enabled with no edits | `ocr-review/page.tsx` render, `text-editor.tsx:63,87` |
| 3 | Stepper never reflects real state: stage-name mismatch (`select_pages` vs `page_selection`…), `stages` prop never passed, `completedStep` written optimistically by pages | `workflow-stepper.tsx:96,122`, `workflow-store.ts:29-40`, `preprocessing/page.tsx:98` |
| 4 | Re-run OCR is a dead end: endpoint only accepts `pages_selected`; OCR Review → Preprocessing → Run OCR always 400s | `books.py:230` |
| 5 | Preprocessing uses one config for all pages, never loads persisted per-page config, and "Preview" persists (PNG + DB commit); "Apply to All" fires N parallel blocking PUTs | `preprocessing/page.tsx:62-105`, `pages.py:33` |

### Per-stage issues

- **Upload**: no real progress (`onUploadProgress` unused), no cancel,
  duplicate error surfaces, form not locked while pending.
- **Select pages**: 300 full thumbnails with `unoptimized` and no
  virtualization; `sessionStorage` handoff to `/extracting-pages` loses state
  on refresh; hardcoded 50% progress bar; backend renders pages synchronously
  inside the request.
- **Preprocessing**: no rotation control (backend only auto-rotates inside
  `deskew()`); hidden ops (`upscale_to_300dpi`, `remove_borders`,
  `sauvola_window/k`) unreachable via the API schema; frontend/backend defaults
  disagree (`denoise` true/7 vs false/10); no before/after, no reset, nested
  600px scroll trap in a `lg:col-span-2` rail.
- **OCR processing**: preprocessing phase invisible (progress 0), no cancel,
  no per-page counter, no partial-results view, auto-redirect skips review.
- **OCR review**: `h-screen` under a sticky navbar plus three scroll panes; no
  dirty tracking, no low-confidence navigation, empty OCR indistinguishable
  from unprocessed.
- **LLM config**: `totalBatches` computed as `fieldDefs.length /
  fields_per_batch`, not the backend's `batch_group` routing (wrong count);
  no Ollama preflight; config not persisted; spinner shown even when complete.
- **Metadata review**: evidence fetched but `source_page_number` /
  `source_text_snippet` unused; low-confidence branch dead; no sticky save bar,
  no dirty guard, no section nav, no field revert; any save while
  `AWAITING_REVIEW` completes the whole book (`metadata.py:89`).

### Admin

- Two stacked top bars (root `AppNavbar` + `AdminSidebar`) with different
  widths and overlapping links; `overflow-x-hidden` clips instead of scrolls.
- No `PageHeader` anywhere in admin — pages start with stat/filter cards.
- Progress double-scaled (`*100` on a 0–100 value) in dashboard and jobs table.
- Dashboard duplicates `/admin/jobs` top-10; "Needs attention" derives from the
  same 10 rows (false "All clear"); stats re-derive from the same page.
- `/admin/books` and `/admin/jobs` wrap tables in Card + bordered div
  (double chrome); duplicated `LANGUAGE_LABELS`/status lists; actions change
  row height; cancel disables every row; `Open book` uses
  `window.location.href` while the title is already a link.
- Backend: `has_metadata` filtered after pagination, `total` redefined as
  `len(items)`; cancel only flips DB status (`celery_task_id` never revoked).

### Loading/feedback/reliability

- `useSSE` ignores the `snapshot` event; `connectionMode` can only be
  `"sse"`/`"idle"`, so the polling-fallback warning is unreachable; stale UI
  has no signal.
- Blocking CPU work on the event loop (`run_pipeline`, PDF rendering, upload
  processing) stalls the whole API during one user's action.
- Button size scale internally inconsistent (`min-h-11` in `sm`/`md` alongside
  `h-8`/`h-10`); error copy inconsistent (inline vs toast vs both).

## Recommendation

**Go** — phased implementation approved by the user (plan 006). P0 items first
because three of them can silently write wrong data; the rest is polish that
should not be mixed into those fixes.

## Next Steps

1. Implement per `plans/006` (Phase 0 → 5), committing in logical increments.
2. Verify each P0 fix by reproducing it on the local stack with a real book.
3. Update `docs/user-guide.md` and `docs/known-issues.md` at the end of
   Phase 5; add the takeover checklist in `todos/008`.

## References

- Plan: `plans/006-ui-ux-workflow-admin.md`
- Checklist: `todos/008-ui-ux-workflow-admin.md`
- Existing stage/job plumbing: `backend/app/api/stages.py`,
  `backend/app/services/stage_manager.py`, `backend/app/services/sse_service.py`
- Design tokens: `frontend/src/app/globals.css` (ARCHIVE LIGHT system)
