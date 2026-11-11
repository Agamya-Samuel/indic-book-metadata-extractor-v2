# 005 — Authentication and Role-Based Access Control

- **Date:** 2026-11-11
- **Status:** Implemented (backend + frontend + docs). Not yet committed — see
  `todos/009-auth-rbac-handoff.md` for the verification state, the commit
  order, and the remaining deploy-time steps.
- **Scope:** User accounts, session authentication, role-based authorization, per-user book ownership, user dashboard, admin user management, and the global admin job queue.

## Objective

Add authentication and authorization to the existing single-user application without replacing its architecture. Preserve the PDF → page selection → preprocessing → OCR → LLM → metadata-review pipeline, and enforce every permission on the backend.

## Decisions locked with the user

| Topic | Decision |
|---|---|
| Roles | `user` and `admin` |
| Other users' books | Metadata-only detail: thumbnail and bibliographic metadata; no pages, OCR text, jobs, or LLM runs |
| Own books | Full pipeline, metadata editing, delete, reset, re-run OCR/extraction |
| Bulk operations | Admin-only |
| Signup | Open self-registration |
| Login identity | Email + password |
| Password reset | Self-service via email |
| Email verification | Required before login |
| Admin user management | View, create, change role, activate/deactivate, reset password, delete |
| Sessions | HttpOnly cookie JWT (access + refresh), CSRF-protected |
| First admin | CLI script (`make create-admin`) |
| Existing books | Database will be reset; no ownership backfill |
| Queue display | Lifecycle status + estimated jobs ahead |
| Uploader identity | Display name shown publicly; email admin-only |
| Admin book access | Full content of every book |
| Public catalog | Only `complete` and `awaiting_review` books |
| Anonymous visitors | May browse the public catalog; login required for all other actions |
| Own job cancellation | Allowed for queued/running jobs; admins may cancel any |
| User deletion | Blocked while the user owns books |

## Current architecture (verified)

- FastAPI routers under `backend/app/api/`; no auth dependencies exist.
- `admin.py` already provides global stats, book management, and a global job list. These become admin-only.
- `Book` has no owner; `Job` links only to `Book`.
- `SearchService` lists/searches all books globally.
- Thumbnails and page images are loaded as plain `<img>` URLs, and job updates use SSE. Cookie auth is therefore the correct transport.
- Alembic is at revision `011`.
- Backend tests use SQLite in-memory and an unauthenticated client fixture.

## Data model (migration 012)

### `users`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | String(320), unique, indexed | stored lower-case |
| `display_name` | String(120), not null | public attribution |
| `password_hash` | String(255), not null | Argon2id |
| `role` | String(20), not null, default `user` | check `user`/`admin` |
| `is_active` | Boolean, not null, default true | |
| `email_verified_at` | DateTime(tz), nullable | login requires a value |
| `last_login_at` | DateTime(tz), nullable | |
| `token_version` | Integer, not null, default 0 | session invalidation |
| `created_at`, `updated_at` | DateTime(tz) | |

### `email_tokens`

Single-use verification and password-reset tokens. Store only a SHA-256 hash.

`id`, `user_id` (FK cascade), `purpose` (`verify_email` / `reset_password`), `token_hash` (unique), `expires_at`, `used_at`, `created_at`.

### `refresh_tokens`

Rotating refresh tokens. Store only a SHA-256 hash.

`id`, `user_id` (FK cascade), `token_hash` (unique), `expires_at`, `revoked_at`, `user_agent`, `ip_address`, `created_at`.

### Ownership columns

- `books.owner_id` → `users.id`, not nullable, `ON DELETE RESTRICT`, indexed.
- `jobs.requested_by_id` → `users.id`, nullable, `ON DELETE SET NULL`, indexed. Durable attribution for queue views; dashboard ownership is derived from `books.owner_id`.
- No backfill: migration 012 requires the `books` table to be empty (the user confirmed the database will be reset). It raises a clear error otherwise.

## Authentication design

- **Password hashing:** Argon2id via `argon2-cffi`.
- **Access token:** JWT, 15 minutes, HttpOnly cookie `access_token`, `SameSite=Lax`, `Secure` in production.
- **Refresh token:** opaque random token, 7 days, HttpOnly cookie `refresh_token`; hashed row in `refresh_tokens`. Rotated on every refresh; reuse of a revoked token revokes all of that user's sessions.
- **CSRF:** non-HttpOnly `csrf_token` cookie plus `X-CSRF-Token` header required on state-changing methods. Frontend axios interceptor supplies it.
- **Revocation:** logout revokes the refresh row; password reset/change, deactivation, and role changes bump `token_version` and revoke all refresh tokens.
- **Login throttling:** stricter per-IP limits for `/auth/login`, `/auth/register`, `/auth/forgot-password`, and `/auth/reset-password` in the existing Redis rate-limit middleware.
- **Email:** SMTP via `aiosmtplib`, configured by env. Local development logs links when SMTP is disabled. Verification links expire in 24 hours; reset links in 1 hour.

### Auth endpoints

| Method | Path | Auth |
|---|---|---|
| POST | `/api/auth/register` | public |
| POST | `/api/auth/login` | public |
| POST | `/api/auth/logout` | authenticated |
| POST | `/api/auth/refresh` | refresh cookie |
| GET | `/api/auth/me` | authenticated |
| POST | `/api/auth/verify-email` | public (token) |
| POST | `/api/auth/resend-verification` | public |
| POST | `/api/auth/forgot-password` | public |
| POST | `/api/auth/reset-password` | public (token) |
| POST | `/api/auth/change-password` | authenticated |

## Authorization model

Two layers:

1. **Router-level authentication.** Every router except the public allowlist depends on `get_current_user`. The admin router additionally depends on `require_admin`. This prevents accidentally leaving a new endpoint open.
2. **Resource-level checks.**
   - `get_owned_book_or_404` for owner-or-admin mutations and full-detail reads.
   - `get_visible_book_or_404` for public catalog reads; non-public books return 404.
   - Jobs, stages, SSE, and OCR/page/metadata endpoints require owner or admin.
   - Bulk operations require admin.
   - Admin book/job operations remain global and admin-only.

Public allowlist:

- `/api/auth/*`
- `/api/library/books`, `/api/library/search`, `/api/library/filters`, `/api/library/books/{id}/detail`
- `GET /api/books/{id}/pages/{n}/thumbnail` (public status, or owner/admin)
- `/health`

Unauthorized resources return `404` rather than `403` to avoid confirming existence.

## Book visibility

- **Public statuses:** `complete`, `awaiting_review`.
- Public catalog listing/search/filters return only public-status books.
- Anonymous and non-owner detail: metadata, thumbnail, uploader display name; no pages, OCR text, jobs, or LLM runs.
- Owner and admin detail: full response (pages, OCR, metadata, jobs, LLM runs, stages).
- Users' own book lists and dashboards include every status they own.
- Thumbnails for non-public books return 404 unless the viewer is owner/admin.
- Page images (`/api/pages/{id}/image`) are owner/admin only.

## New and changed endpoints

### Owner-scoped book actions

Add to `/api/books` (owner or admin):

- `DELETE /api/books/{book_id}`
- `POST /api/books/{book_id}/reset`
- `POST /api/books/{book_id}/rerun-ocr`
- `POST /api/books/{book_id}/rerun-extraction`

These wrap the existing `admin_service` functions after an ownership check. Admin global routes stay under `/api/admin/books/*`.

### Dashboard

- `GET /api/dashboard/summary` — own book counts by status, job counts, queue counts.
- `GET /api/dashboard/books` — own books, paginated.
- `GET /api/dashboard/jobs` — own jobs, paginated, with `queue_ahead`.
- `POST /api/jobs/{job_id}/cancel` — owner or admin.

`queue_ahead` estimates position by counting queued jobs of the same family created earlier: OCR/preprocessing → `ocr` queue, LLM → `llm` queue. A running job reports `queue_ahead = 0`.

### Admin user management

- `GET /api/admin/users`
- `POST /api/admin/users`
- `GET /api/admin/users/{user_id}`
- `PATCH /api/admin/users/{user_id}` (display name, role, active)
- `POST /api/admin/users/{user_id}/reset-password`
- `DELETE /api/admin/users/{user_id}`

Safety rules:

- An admin cannot demote or deactivate themselves.
- An admin cannot delete themselves.
- The last active admin cannot be demoted, deactivated, or deleted.
- User deletion is blocked while the user owns books.
- Admin-created users are marked verified; the admin supplies a temporary password.

### Admin queue and books

- Extend `/api/admin/jobs` and `/api/admin/books` rows with owner display name/email, and support filtering by owner.
- Admin stats gain user counts.

## Frontend

- `AuthProvider` + `useAuth`, fetching `/auth/me` on load; axios with `withCredentials` and CSRF header; single refresh-and-retry on 401.
- Route gate in the root layout:
  - public: `/`, `/library/*`, `/login`, `/register`, `/verify-email`, `/forgot-password`, `/reset-password`
  - authenticated: `/upload`, `/dashboard`, `/books/*`
  - admin: `/admin/*`
- Navbar: Library always; Dashboard/Upload when authenticated; Admin when admin; Login/Register when anonymous; user menu with display name, email, logout.
- New pages: `/login`, `/register`, `/verify-email`, `/forgot-password`, `/reset-password`, `/dashboard`, `/admin/users`.
- Dashboard: own books (with delete/reset/re-run actions), own jobs (status, progress, queue-ahead, cancel), summary cards.
- Library: public, shows uploader display name; detail page renders metadata-only for non-owners and full content for owner/admin.
- Admin: users page; owner columns/filters on books and jobs.

## Test plan

Backend:

- Update `conftest.py` with user fixtures and dependency overrides so existing tests run as an authenticated user with an owned book.
- Add `anon_client`, `user_client`, `admin_client`, and `auth_client` fixtures.
- New tests: registration + verification, login/logout/refresh, password reset, CSRF, role enforcement, ownership isolation for books/pages/metadata/jobs/SSE, public catalog filtering, admin-only bulk, user management, last-admin protection, user-deletion guard, queue-ahead calculation.

Frontend:

- Auth provider and route-gate tests.
- Login/register/reset form tests.
- Dashboard rendering and job-cancel tests.
- Update existing tests with the auth provider wrapper.

## Rollout

1. Add backend dependencies and migration.
2. Run `make migrate` against a reset database.
3. Create the first admin with `make create-admin EMAIL=... PASSWORD=... DISPLAY_NAME=...`.
4. Configure SMTP and `FRONTEND_URL`.
5. Verify registration → email verification → login → upload → pipeline → dashboard → admin views.
6. Update README, API reference, known limitations, env examples, and deployment docs.

## Implementation results (2026-11-11)

Implemented in full; see `todos/009-auth-rbac-handoff.md` for the file-level
checklist and `learnings/008-auth-rbac-outcome.md` for the findings.

| Planned | Delivered | Deviation |
|---|---|---|
| `users` / `email_tokens` / `refresh_tokens` + `books.owner_id` | migration `012_auth_rbac.py` | Migration aborts if `books` is non-empty (no backfill, per the locked decision) |
| Cookie sessions (access + refresh) + CSRF | as planned; refresh is single-use/rotating, reuse revokes the session | — |
| 10 auth endpoints | as planned | — |
| Owner-scoped book actions + admin global equivalents | `/api/books/{id}/{reset,rerun-ocr,rerun-extraction}`, `/api/books/{id}` DELETE, `/api/admin/books/*` | — |
| Dashboard summary/books/jobs + `queue_ahead` + cancel | as planned | `queue` counts the `ocr` family (preprocessing + OCR) and the `llm` family separately |
| Admin user management (create/role/active/reset/delete) | as planned | Guards: self, last admin, and "still owns books" |
| Public catalog = `complete` + `awaiting_review`, metadata-only for non-owners | as planned; `can_view_full` + `owner_display_name` added to the library detail response | — |
| Frontend pages (auth, dashboard, admin users) + shared components | as planned | `AdminStatsCard` was moved to `components/shared/stat-card.tsx` as `StatCard`; a shared `ActionMenu` replaced per-page dropdown code |
| Rate limiting on auth endpoints | as planned | — |

Verification at hand-off: backend `pytest` 272 passed / 1 skipped (Postgres-only
test), frontend `vitest` 191 passed, `tsc --noEmit` clean, `eslint` clean for
the auth-owned files.

## Out of scope

- OAuth/social login.
- Email change flows.
- Per-user storage quotas.
- Admin impersonation.
- Fine-grained per-book sharing or collaborators.
