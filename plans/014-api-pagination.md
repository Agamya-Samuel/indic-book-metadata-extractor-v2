# 014 — API + UI Pagination

## Status

Implemented (backend + frontend in one change set).

## Problem

Six endpoints paginated with three different `total_pages` formulas; eight returned
unbounded arrays. `GET /api/books/{id}/detail` shipped every page, job, and LLM run of a
book in one response, which grows with book length (100–300 pages).

## Design

- One envelope: `app/schemas/common.py::Page[T]` → `{items, total, page, page_size, total_pages}`.
- One calculator: `app/services/pagination.py::page_count` (0 for empty sets).
- One dependency: `app/api/deps.py::get_pagination` → `?page=&page_size=` (1-based, capped 100).
- Existing response models inherit `Page[...]` so their JSON is unchanged.

## Endpoints

Migrated to the shared envelope: `GET /admin/users`, `/admin/books`, `/admin/jobs`
(previously a bare dict, now typed `AdminJobsResponse`), `/dashboard/books`, `/dashboard/jobs`,
`/notifications`.

Newly paginated: `/books/{id}/pages` (optional `include_ocr=true`), `/books/{id}/jobs`,
`/books/{id}/stages`, `/books/{id}/stages/current`, `/books/{id}/metadata/fields`,
`/books/{id}/metadata/evidence`, `/books/{id}/llm-runs`, `/books/models`.

Added `GET /api/jobs/{job_id}` (uses the existing `get_job_for_user_or_404` dependency) so the
client can fetch one job instead of scanning a list.

`GET /books/{id}/detail` now returns only `book`, `metadata`, `metadata_updated_at`,
`owner_display_name`. Pages/jobs/LLM runs come from their paginated endpoints.

Intentionally not paginated: aggregate dicts (`/admin/stats`, `/dashboard/summary`,
`/bulk/stats`), distinct filter values (`/admin/filters`), streaming bulk exports, SSE, and
`/books/{id}/ocr-status` (an aggregate whose averages need the whole set).

## Frontend

- `lib/api.ts`: generic `Page<T>`, `PageParams`, `pageQuery`, `fetchAll` plus `getAll*`
  helpers for consumers that genuinely need the whole set (filmstrip, counts, status
  derivation). Array fetchers now return `Page<T>`.
- `components/shared/pagination.tsx`: numbered window with ellipsis, `aria-current`,
  `aria-live`, optional rows-per-page selector; the hand-rolled pager in `select-pages` was
  replaced by it.
- Book detail tables (pages, processing history, LLM runs) and the book jobs page now page
  server-side. `metadata-review` pages the LLM run history.

## Verification

- `cd backend && uv run pytest tests/integration -q`
- Frontend: `npm run lint && npx tsc --noEmit && npm test`
- Manual: `?page=2&page_size=10` slicing, out-of-range page returns `items: []`,
  `page_size=101` → 422.
