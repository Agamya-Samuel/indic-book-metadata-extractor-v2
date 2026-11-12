# 014 — Frontend + Backend Route Redesign Outcome

- **Date:** 2026-11-12
- **Status:** Shipped and committed (`0809a8d` API, `0c78806` tests, `c4f501f`
  web, `40031d9` docs) — unpushed.
- **Companion:** `todos/011-route-redesign-handoff.md` (inventory + locked decisions)

## Study Context

Following the landing of plan 007 (moderated signup, admin-only catalog,
owner-only books), the API and web app had accumulated route drift:

1. Three book-list endpoints for one resource (`/api/library/books`,
   `/api/admin/books`, `/api/dashboard/books`).
2. Two book-detail surfaces (`/books/[bookId]` pipeline, `/library/[bookId]`
   detail card).
3. Root-mounted dashboard/job routes outside the `/api/<group>` convention.
4. Naming drift: frontend `/bulk-operations` vs API `/bulk`.

The task was a **convergence + grouping + naming** pass — not a rewrite.

## Summary

The `/api/library/*` API is retired and folded into the admin API; the
dashboard and job routes are grouped under `/api/dashboard`; the bulk-ops page
moved to `/admin/bulk`. No pipeline routes were relocated. The separate
`/library` catalog page was subsequently removed (it duplicated `/admin/books`)
and book detail moved from `/library/[bookId]` to `/books/[bookId]` — see
"Follow-up: /library removed" below.

## Key Findings

### Backend convergence

- **Catalog listing** now has a single source of truth: `GET /api/admin/books`
  (admin-only). It absorbed the former `/api/library/books` query surface and
  gained `genre` / `publisher` filters, which `SearchService.list_books` now
  supports directly (previously those filters only applied on the search path).
- **Filter options** moved to `GET /api/admin/filters` (admin-only), reusing
  `SearchService.get_filter_options`.
- **Book detail** moved to `GET /api/books/{book_id}/detail` (owner-or-admin).
  *Deviation from the outline:* the handoff proposed `GET /api/admin/books/{id}`
  (admin-only), but the detail page `/library/[bookId]` is owner-or-admin
  (Q7 kept it), so an admin-only endpoint would have locked owners out of their
  own book detail. Placing it on the book-scoped path keeps the current
  ownership semantics while removing the `/library` prefix.
- **Dashboard grouping**: `dashboard.py` paths are now relative to a
  `prefix="/dashboard"` mount, so nothing is root-mounted. Job cancellation is
  now `POST /api/dashboard/jobs/{job_id}/cancel` (owner) with the admin variant
  unchanged at `POST /api/admin/jobs/{job_id}/cancel`.
- The `library.py` router and its `include_router` were deleted.

### Frontend

- `api.ts`: `getLibraryBooks` → `/admin/books`; `getFilterOptions` →
  `/admin/filters`; `getBookDetail` → `/books/{id}/detail`; `cancelJob` →
  `/dashboard/jobs/{id}/cancel`. The unused `searchLibrary` helper was removed.
- `/bulk-operations` → `/admin/bulk` (page moved; nav + route guard updated;
  `/bulk-operations` dropped from `ADMIN_PATHS`). The page now inherits the
  `/admin` layout (admin sidebar), which is appropriate for an admin tool.

### Follow-up: `/library` removed

Decided with the user after the initial pass: the `/library` list duplicated
`/admin/books` (both read `GET /api/admin/books`) and only admins may see the
all-books list, so the `/library` page was **removed** and `/admin/books` is the
sole admin catalog.

- Book detail moved from `/library/[bookId]` to `/books/[bookId]` so owners keep
  a detail view (linked from the dashboard). All `/library/*` links repointed
  (dashboard, admin overview/books/jobs, navbar). `ADMIN_EXACT_PATHS` and the
  `Library` nav link were deleted.
- No redirects were added — the app is pre-production, so the old URL is simply
  broken rather than shimmed.
- Dead code removed: `BookCard`, `LibrarySkeleton`, `SkeletonCard`, and the
  `components/library/` folder (the workflow resume banner moved to
  `components/book/`).
- Deployed verification on the OKI host (2026-11-12): `/library` → `404`,
  `/api/library/books` → `404`, `/api/admin/books` → `401` (exists, auth-gated),
  `/api/books/{id}/detail` → `401`; `/admin/books`, `/login`, `/dashboard` →
  `200`; backend `/health` → `200`.

## Verification

- Backend: `test_api_library.py` replaced by `test_admin_books.py`
  (admin listing/filters, owner-or-admin detail, and 404 for retired
  `/api/library/*`); `test_rbac.py`, `test_signup_approval.py`, and
  `test_dashboard.py` repointed. Target suites green.
- Frontend: `tsc --noEmit` clean, `eslint` 0 errors, `vitest` 198/198 pass.

## Known failures on the branch (not caused by this change)

- `tests/integration/test_api_books.py::TestSelectPages::{test_select_pages_success,
  test_select_pages_duplicate_deduped}` — need a live Redis/Celery
  (`localhost:6379`); fail identically on the pre-change base.
- `tests/unit/test_metadata_schema.py::TestExtractionRequest::test_defaults` —
  asserted the stale default `qwen2.5` after `964d5af` switched the default
  model to `phi4-mini`. Fixed in the follow-up cleanup commit.

## Follow-ups carried out after this note

- Renamed the catalog helper `getLibraryBooks` → `getAdminBooks` at the call
  site and deleted the alias (catalog is admin-scoped).
- Added `/admin/bulk` to the admin sidebar so the moved page is reachable from
  the admin surface, not only the top navbar.

## Recommendation

Shipped as outlined. The `getBookDetail` placement
(`/api/books/{id}/detail`) is the one intentional deviation and is the only
correct option given the owner-or-admin detail page.

## Next Steps

- Run the backend suite with Redis/Celery up to clear the environment-dependent
  failures (see handoff §6).
- Verify the redesigned routes on the deployed host (admin catalog, owner book
  detail, `/bulk-operations` redirect, retired `/api/library/*` → 404).

## References

- `todos/011-route-redesign-handoff.md`
- `docs/api-reference.md` (Catalog & Book Detail section)
- `docs/changelog.md` (Unreleased → Changed)
- `backend/app/api/router.py`, `backend/app/api/admin.py`,
  `backend/app/api/dashboard.py`, `backend/app/api/books.py`
- `frontend/src/lib/api.ts`, `frontend/src/components/shared/app-navbar.tsx`,
  `frontend/src/components/auth/route-guard.tsx`
