# 014 — Frontend + Backend Route Redesign Outcome

- **Date:** 2026-11-12
- **Status:** Shipped (working tree; not yet committed)
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
moved to `/admin/bulk`. No pipeline routes were relocated. `/library` (the
admin catalog page) and `/library/[bookId]` (owner-or-admin detail) are kept, so
the frontend route surface changed by exactly one path.

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
- `ADMIN_EXACT_PATHS = ["/library"]` is retained: `/library` is admin-only while
  `/library/<bookId>` stays owner-or-admin.

### Verification

- Backend: `test_api_library.py` replaced by `test_admin_books.py`
  (admin listing/filters, owner-or-admin detail, and 404 for retired
  `/api/library/*`); `test_rbac.py`, `test_signup_approval.py`, and
  `test_dashboard.py` repointed. Target suites green.
- Frontend: `tsc --noEmit` clean, `eslint` 0 errors, `vitest` 198/198 pass.

## Recommendation

Shipped as outlined. The `getBookDetail` placement
(`/api/books/{id}/detail`) is the one intentional deviation and is the only
correct option given the owner-or-admin detail page.

## Next Steps

- Commit the change set in logical increments (backend convergence, tests,
  frontend, docs).
- Run the backend suite with Redis/Celery up to clear the three
  environment-dependent failures (see handoff §6).
- Note: `tests/unit/test_metadata_schema.py::TestExtractionRequest::test_defaults`
  currently fails on HEAD because commit `964d5af` switched the default model to
  `phi4-mini` without updating the test — unrelated to this routing change.

## References

- `todos/011-route-redesign-handoff.md`
- `docs/api-reference.md` (Catalog & Book Detail section)
- `docs/changelog.md` (Unreleased → Changed)
- `backend/app/api/router.py`, `backend/app/api/admin.py`,
  `backend/app/api/dashboard.py`, `backend/app/api/books.py`
- `frontend/src/lib/api.ts`, `frontend/src/components/shared/app-navbar.tsx`,
  `frontend/src/components/auth/route-guard.tsx`
