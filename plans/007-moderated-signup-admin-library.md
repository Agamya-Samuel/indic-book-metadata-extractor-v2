# 007 — Moderated Signup, Admin-Only Library, Owner-Only Book Access

- **Date:** 2026-11-12
- **Status:** Implemented (2026-11-12) — see `learnings/012-moderated-signup-outcome.md`.
- **Scope:** Approval-based registration, removal of anonymous/public catalog access, an admin-only Library that spans all users, and a hardening pass on per-user book ownership.
- **Depends on:** `plans/005-auth-rbac.md` (implemented). This plan extends that system; it does not replace it.

## Objective

Close the Pilot-phase access gaps in the shipped auth/RBAC system:

1. No anonymous or guest access — every page and API requires authentication, except signup/login/password/verification endpoints.
2. Moderated, approval-based signup: new accounts start `pending` and require admin approval. The gate must be **configurable** so open registration can be re-enabled later without redesign.
3. The Library page is admin-only and lists **all** books from **all** users. Regular users no longer see the Library page.
4. Regular users can only reach books they own; ownership is enforced in the backend, not by hiding UI.

## Context: what already exists (verified 2026-11-12)

The auth/RBAC milestone (`plans/005`, `todos/009`, `learnings/008`) already shipped most of what a naive reading of the brief assumes is missing:

| Area | State |
|---|---|
| Auth transport | JWT access (15 min) + rotating refresh in HttpOnly cookies, CSRF, Argon2id — `backend/app/core/security.py`, `backend/app/api/auth.py`, `backend/app/services/auth_service.py` |
| Router auth | `get_current_user` on nearly every router — `backend/app/api/router.py:16-54` |
| Admin gate | `require_admin` — `backend/app/api/deps.py:101-106` |
| Ownership | `books.owner_id` NOT NULL FK (`backend/app/models/book.py:34-38`); `get_owned_book_or_404`, `can_view_full_book` — `backend/app/api/deps.py:109-138` |
| Ownership coverage | Upload stamps `owner_id`; retrieval, lifecycle, metadata, jobs, dashboard are all owner-scoped |
| Roles / admin user mgmt | `role` (`user`/`admin`), full admin user CRUD — `backend/app/api/admin.py:44-146` |
| Email verification | Required before login — `auth_service.py:186-191` |

### Genuine gaps this plan closes

- **Approval/moderation does not exist.** No `status`/pending/approved/rejected concept anywhere (only `role`, `is_active`, `email_verified_at`). Entirely new.
- **Anonymous public catalog exists and is intentional.** `/library` is a public route (`frontend/src/components/auth/route-guard.tsx:8-15`); `GET /api/library/books` has no auth dependency and returns `public_only=True` books (`backend/app/api/library.py:27-85`); `PUBLIC_BOOK_STATUSES` + `get_visible_book_or_404` + the `can_view_full` anonymous branch implement metadata-only public viewing (`backend/app/models/book.py:21-23`, `deps.py:141-152`). **This plan removes all of it.**
- **No admin "all books" listing for the Library.** The library list only ever returns public-status books.

## Decisions locked with the user

| Topic | Decision |
|---|---|
| Anonymous/guest access | **Remove entirely.** All pages and APIs require auth, except `/auth/*` (register/login/verify/forgot/reset) and health. |
| Library page | **Admin-only**, lists all books by all users. Regular users use the existing owner-scoped Dashboard. |
| Approval model | **New `account_status` enum column** (`pending`/`approved`/`rejected`), separate from `is_active` (which keeps meaning "admin suspended"). |
| Gate ordering | **Two gates:** verify email → admin approves → full access. |
| Pending user login | **Allowed.** Logs in and lands on an "awaiting approval" screen (no app endpoints usable). *(default adopted; flagged for confirmation)* |
| Rejected user | Logs in to a "registration not approved" screen; app endpoints return 403. Admin can later flip them back to `approved`. |
| Admin notification | **Pending-count badge** in the admin nav (no SMTP dependency). *(default adopted; flagged for confirmation)* |
| Config switch | `registration_requires_approval: bool = True`. When `false`, new signups are auto-`approved` (open registration, no redesign). |
| Existing users + bootstrap admin | Backfilled to `approved`; DB column default `approved`. Registration sets `pending` only when the flag is on. |

## Data model — migration `013_user_approval`

Additive only; does not touch `books`, so it is safe regardless of existing rows.

### `users` (new columns)

| Column | Type | Notes |
|---|---|---|
| `account_status` | String(20), not null, default `approved` | check `account_status IN ('pending','approved','rejected')` |
| `status_reviewed_at` | DateTime(tz), nullable | when an admin approved/rejected |
| `status_reviewed_by_id` | UUID FK `users.id` `ON DELETE SET NULL`, nullable | which admin acted |
| `rejection_reason` | String(500), nullable | optional, shown to the user |

Backfill: all existing rows (including the bootstrap admin) default to `approved`. `alembic/versions/013_user_approval.py`, `down_revision = "012"`.

### Model / schema

- `UserRole` stays; add `class AccountStatus(StrEnum)` (`PENDING`/`APPROVED`/`REJECTED`) in `backend/app/models/user.py`.
- Add `account_status` to `UserResponse` (`backend/app/schemas/auth.py:24-34`) so `/auth/me` and login/refresh payloads carry it.
- Extend `AdminUserUpdateRequest` with `account_status: AccountStatus | None`; add `rejection_reason` to the reject request.

## Backend design

### Config (`backend/app/core/config.py`)

```python
# Registration moderation. When False, new signups are auto-approved.
registration_requires_approval: bool = True
```

### Auth service (`backend/app/services/auth_service.py`)

- `create_user(..., account_status: str = AccountStatus.APPROVED)` — default keeps admin-create and the CLI admin `approved`; `register_user` passes `PENDING` when `settings.registration_requires_approval` is true, else `APPROVED`.
- `authenticate_user` — **does not** reject on `account_status`; pending/rejected users get a session so the frontend can render the holding screen. (Existing `is_active` and `email_verified_at` checks and their error codes are unchanged.)
- New `approve_user(db, admin, target)` and `reject_user(db, admin, target, reason)` — set status, `status_reviewed_at/by`, `rejection_reason`; revoke the target's other sessions on rejection.
- `list_users` gains an `account_status` filter.

### Authorization dependency (`backend/app/api/deps.py`)

- Add `require_approved_user(user = Depends(get_current_user))` → 403 with detail code `account_pending` / `account_rejected` when the account is not `approved`.
- Apply it at router level to every application router in `backend/app/api/router.py` (books, pages, metadata, extraction, stages, sse, library, dashboard, bulk) and keep `require_admin` for admin. `/auth/*` and `/health` are untouched so sessions, logout, and the holding screen keep working.
- Retire the anonymous branches: `get_optional_current_user` / `can_view_full_book(None)` no longer grant anything; `get_visible_book_or_404` collapses to owner-or-admin.

### Book visibility (catalog removal)

- Delete the public-catalog concept: remove `PUBLIC_BOOK_STATUSES` / `is_public_book` gating. `PUBLIC_BOOK_STATUSES` is used in `library.py`, `deps.py`, and the thumbnail route — all become owner-or-admin.
- `POST /api/books/upload` and every lifecycle route already use `get_owned_book_or_404`; no change needed beyond removing the public fallback.
- Thumbnail route (`GET /api/books/{id}/pages/{n}/thumbnail`) changes from `get_visible_book_or_404` to `get_owned_book_or_404`.

### Endpoints

Changed:

| Method | Path | Change |
|---|---|---|
| GET | `/api/auth/me` | response includes `account_status` |
| POST | `/api/auth/register` | success message reflects moderation ("verify your email; an admin will review your account") |
| GET | `/api/admin/users` | new `account_status` filter |
| PATCH | `/api/admin/users/{id}` | *as built:* approval state is **not** settable here — use the dedicated approve/reject endpoints |
| GET | `/api/admin/stats` | add `pending_user_count` (drives the badge) |
| GET | `/api/library/books` (and `/search`, `/filters`) | require auth; return **all** books (drop `public_only`); serve the admin Library |
| GET | `/api/library/books/{id}/detail` | owner or admin only; no anonymous metadata view |

New:

| Method | Path | Auth |
|---|---|---|
| POST | `/api/admin/users/{id}/approve` | admin |
| POST | `/api/admin/users/{id}/reject` | admin (optional `rejection_reason`) |

The admin Library page can use either the repurposed `/api/library/*` (all books) or the existing `/api/admin/books`; implementation will pick one and keep a single source of truth.

## Frontend design

- `frontend/src/lib/api.ts`: add `account_status` to `AuthUser`; add `approveAdminUser(id)`, `rejectAdminUser(id, reason?)`; extend `getAdminUsers` params with `account_status`; extend `AdminUserUpdateRequest`.
- `frontend/src/components/auth/auth-provider.tsx`: expose `accountStatus` and `isApproved` (`=== "approved"`). `isAuthenticated` stays `user !== null` so pending users can reach the holding screen.
- `frontend/src/components/auth/route-guard.tsx`:
  - Remove `/library` from `PUBLIC_PATHS` (public list becomes `/`, `/login`, `/register`, `/verify-email`, `/forgot-password`, `/reset-password`).
  - Add `/library` to `ADMIN_PATHS`.
  - New branch: authenticated but `!isApproved` → redirect to `/pending-approval` (except that route itself).
- New page `frontend/src/app/pending-approval/page.tsx`: status-specific message (pending → "awaiting review"; rejected → reason/notice) + logout.
- `frontend/src/app/login/page.tsx`: after successful login, if `account_status !== "approved"` redirect to `/pending-approval` instead of `/dashboard`.
- `frontend/src/app/register/page.tsx`: post-signup copy reflects email-verify + admin-review ordering.
- `frontend/src/components/shared/app-navbar.tsx`: move the Library link from scope `all` to `admin`; add a pending-count badge on the Admin link.
- `frontend/src/app/admin/users/page.tsx`: add an Account-status column + badge, an `account_status` filter, and Approve/Reject actions (reject prompts for an optional reason).
- `frontend/src/app/library/page.tsx`: admin-only (guard handles it); ensure it lists all books with an owner column.
- `frontend/src/app/library/[bookId]/page.tsx`: keep reachable by owners (their own book) and admins; drop the anonymous "public catalog entry" branch. The path stays under `/library/…`; no route move.

## Testing

Backend (`backend/tests/`):

- Extend `conftest.py` fixtures: `user_client` becomes an approved owner; add `pending_client`, `rejected_client`, and keep `admin_client`.
- New tests: register creates `pending` when the flag is on / `approved` when off; pending and rejected users get 403 (`account_pending`/`account_rejected`) on app routers but can call `/auth/me` and `/auth/logout`; admin approve/reject transitions + `status_reviewed_*`; `pending_user_count` in stats; library endpoints require auth and return all books for admin; non-owner book/page/metadata/thumbnail access returns 404; anonymous access to every non-`/auth` route returns 401.

Frontend (`vitest`): route-guard redirect for pending/rejected; navbar admin-only Library + badge; login redirect for unapproved; login/register copy; admin users approve/reject actions.

## Rollout

1. `alembic` migration `013` (additive, backfills `approved`).
2. Backend: config flag, model/schema, service transitions, `require_approved_user`, catalog removal, endpoints.
3. Frontend: auth provider/guard, `/pending-approval`, navbar, admin users, library.
4. Docs: `README.md` "Accounts & Access", `docs/known-limitations.md`, `docs/api-reference.md`, `docs/known-issues.md`, `frontend/.env.example`, `backend/.env.example`, `docs/changelog.md`.
5. Verify on the deployed host (dev server + browser): register → verify → pending screen → admin approve → access; non-owner book URL 404s; Library absent for `user`, present for `admin`.
6. `learnings/012-moderated-signup-outcome.md` with the results.

## Out of scope

- OAuth/social login; email-change flows; per-user quotas; admin impersonation; per-book sharing (unchanged from `plans/005`).
- Email notification to admins on new signups (badge only).
- Self-service re-application after rejection (an admin flips the status).
- Renaming the `/library/[bookId]` route to a non-library path.

## Open items to confirm

- **Pending login UX** — adopted: pending/rejected users may log in to a holding screen. Alternative: block at login with a specific error. Confirm before implementing the guard.
- **PoC depth** — `AGENTS.md` asks for study → PoC → docs → implementation. This extends an already-implemented and tested auth system; the proposal is to treat the migration + backend test suite as the verification step rather than a standalone PoC. Say if a formal PoC doc is wanted.

## Implementation notes (deviations)

- **Library listing is admin-only.** The endpoint table said "require auth" for
  `/api/library/books|search|filters`, but that would leak every user's book
  metadata to any approved user and contradict objective 4. Those three
  endpoints use `require_admin`; book *detail* stays owner-or-admin so owners can
  still open their own book.
- **`UserResponse.rejection_reason` added** (not in the original schema section)
  so the rejected holding screen can show the reason.
- **`register` copy** differs by `registration_requires_approval`, and
  admin-created/CLI accounts remain `approved`.

### Review hardening (post-implementation)

- `require_admin` now depends on `require_approved_user`, so a `pending`/`rejected`
  account with the admin role cannot reach `/api/admin/*`.
- `/library/<bookId>` is owner-or-admin: the route guard treats only the exact
  `/library` listing as admin-only, so owners can open their own book.
- `account_status` was removed from `PATCH /api/admin/users/{id}` (approve/reject
  are the sole status API); the status-change duplication and the PATCH
  self-lockout path are gone.
- The admin nav badge uses a dedicated `GET /api/admin/users/pending-count`
  instead of the full stats endpoint; `can_view_full` was removed from
  `BookDetailResponse`; the frontend approval predicate is one shared
  allow-list helper.
