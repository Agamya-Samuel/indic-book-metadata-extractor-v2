# 009 — Auth/RBAC Milestone: Handoff & Completion Checklist

Companion to `plans/005-auth-rbac.md` (approved design) and this checklist
(implementation state, verification, remaining work). Read this first when
taking over the milestone.

- **Date:** 2026-11-11
- **Status:** Backend + frontend + docs implemented; **nothing committed yet**
- **Owner of the auth files:** this milestone. **Do not** mix in the parallel
  UI/UX workstream (see §6) or the ground-truth data work.

---

## 1. Objective (recap)

Add authentication and role-based access control to the existing
single-user application without replacing the architecture. Preserve the
PDF → page selection → preprocessing → OCR → LLM → metadata-review pipeline,
and enforce **every** permission on the backend (not by hiding UI).

Design decisions were locked with the user in `plans/005-auth-rbac.md` (§
"Decisions locked with the user"). They are binding — do not re-litigate.

---

## 2. Completed work

### 2.1 Backend (complete)

| Area | Files | Notes |
|---|---|---|
| Data model | `backend/app/models/user.py`, `backend/alembic/versions/012_auth_rbac.py` | `users`, `email_tokens`, `refresh_tokens`; `books.owner_id` **non-nullable** |
| Crypto/session | `backend/app/core/security.py` | Argon2id password hashing, JWT access/refresh signing, CSRF token issue/verify |
| Auth service | `backend/app/services/auth_service.py` | register/verify/login/refresh/logout/reset/change-password, session revocation via `token_version` |
| Email | `backend/app/services/email_service.py` | SMTP via `aiosmtplib`; **when `SMTP_ENABLED=false` the email body (incl. links) is logged instead of sent** |
| Endpoints | `backend/app/api/auth.py` | register, login, refresh, logout, me, verify-email, resend-verification, forgot-password, reset-password, change-password |
| Dashboard | `backend/app/api/dashboard.py`, `backend/app/services/dashboard_service.py` | summary, own books, own jobs (`queue_ahead`), job cancel |
| Admin | `backend/app/api/admin.py` (extended) | users CRUD + role/active/reset-password/delete; global books/jobs/stats |
| Guards | `backend/app/api/deps.py` | `get_current_user`, `get_optional_current_user`, `require_admin`, `get_owned_book_or_404`, `get_visible_book_or_404`, `get_job_for_user_or_404`, `can_view_full_book`, `is_public_book` |
| Ownership enforcement | `backend/app/api/{books,pages,metadata,extraction,stages,sse,bulk,library}.py` | every book/page/OCR/metadata/job route now owner-or-admin |
| CLI | `backend/scripts/create_admin.py` + `Makefile` target `create-admin` | creates the **first** admin (verified + active); password prompted when omitted |
| Tests | `backend/tests/integration/test_auth.py`, `test_rbac.py`, `test_dashboard.py` (+ `conftest.py` fixtures) | anon/user/admin client fixtures |

Key API surface (verified 2026-11-11):

```
POST /api/auth/register            GET  /api/auth/me
POST /api/auth/login               POST /api/auth/refresh
POST /api/auth/logout              POST /api/auth/verify-email
POST /api/auth/resend-verification POST /api/auth/forgot-password
POST /api/auth/reset-password      POST /api/auth/change-password

GET  /api/dashboard/summary        GET  /api/dashboard/books
GET  /api/dashboard/jobs           POST /api/jobs/{job_id}/cancel

GET|POST /api/admin/users          GET|PATCH|DELETE /api/admin/users/{id}
POST /api/admin/users/{id}/reset-password
GET  /api/admin/stats              GET  /api/admin/books | /api/admin/jobs
DELETE /api/admin/books/{id}       POST /api/admin/books/{id}/reset|rerun-ocr|rerun-extraction
POST /api/admin/jobs/{id}/cancel

DELETE /api/books/{id}             POST /api/books/{id}/reset|rerun-ocr|rerun-extraction
```

### 2.2 Frontend (complete)

| Area | Files |
|---|---|
| Session plumbing | `frontend/src/lib/api.ts` (axios `withCredentials`, CSRF header from `csrf_token` cookie, single-flight 401→refresh→replay), `frontend/src/components/auth/auth-provider.tsx`, `route-guard.tsx`, `auth-card.tsx` |
| Auth pages | `frontend/src/app/{login,register,verify-email,forgot-password,reset-password}/page.tsx` |
| User dashboard | `frontend/src/app/dashboard/page.tsx` (summary cards, own books with Actions menu, own jobs with queue-ahead, cancel, polling) |
| Admin users | `frontend/src/app/admin/users/page.tsx` (search/role/active filters, role badges, `(you)` marker, Actions menu, create-user + reset-password `<dialog>`s) |
| Shared components (new) | `frontend/src/components/shared/stat-card.tsx` (`StatCard` — replaced `components/admin/admin-stats-card.tsx`), `frontend/src/components/shared/action-menu.tsx` (`ActionMenu`/`MenuLink`/`MenuButton`/`MenuSeparator`), `frontend/src/components/admin/owner-filter.tsx` (`OwnerFilter` + `OwnerSelection`) |
| Library | `frontend/src/components/library/book-card.tsx` ("Uploaded by {owner_display_name}"), `frontend/src/app/library/[bookId]/page.tsx` (gates on `detail.can_view_full`, hides pages/OCR/jobs/LLM runs + review CTAs for non-owners) |
| Admin surfaces | `admin/page.tsx` (Users stat card), `admin/books/page.tsx` (Owner column + OwnerFilter + ActionMenu), `admin/jobs/page.tsx` (Owner column + OwnerFilter), `admin-sidebar.tsx` (Users link) |
| Tests | `frontend/tests/pages/{login,register,reset-password,dashboard,admin-users}-page.test.tsx`, `frontend/tests/setup.ts` (jsdom `showModal` polyfill) |

### 2.3 Documentation (complete)

- `docs/api-reference.md` — auth overview (cookies/CSRF/roles), 401/403/429 codes, **Authentication API** section, owner-scoped book endpoints, **Dashboard API**, **Admin API** (users table, global books/jobs, stats users block), `can_view_full` / `owner_display_name` documented in "Get Book Detail (Library View)".
- `README.md` — new **Accounts & Access** section, `make create-admin` in the Makefile table, Known Limitations updated (auth gap removed; quotas/SMTP/rate-limit gaps added).
- `docs/known-limitations.md` — item 8 "Auth/user accounts" marked **Done** with remaining gaps.
- `docs/known-issues.md` — "No Authentication" replaced with an "Authentication" section.
- `docs/user-guide.md` — new **Accounts** section (register/verify/login/reset, role matrix, dashboard), public-entry note in "Book Detail", personal-dashboard pointer in "Job Queue Dashboard", troubleshooting entries for "verification email never arrives" and "cannot log in".
- `docs/changelog.md` — new `[Unreleased]` entry describing the milestone.
- `DEPLOY.md` — SMTP env vars (`SMTP_ENABLED/HOST/PORT/USERNAME/PASSWORD/FROM`), "Create the first admin" deploy step, migration-012 caveat.
- `docs/local-development-guide.md` — SMTP note (links are logged when `SMTP_ENABLED=false`), "Step 5b: Create the First Admin Account".

---

## 3. Verification state (re-run 2026-11-11, end of session)

| Check | Command | Result |
|---|---|---|
| Backend tests | `cd backend && uv run pytest -q` | **272 passed, 1 skipped** (skip = `SearchService.get_filter_options`, needs Postgres `.astext`) |
| Frontend typecheck | `cd frontend && npx tsc --noEmit` | **clean** (0 errors) — re-verified 2026-11-11 19:27 after the other workstream's commits landed |
| Frontend tests | `cd frontend && npm test` | **191 passed / 22 files** |
| Frontend lint | `cd frontend && npm run lint` | **0 errors** (5 pre-existing warnings) |

The whole tree is green. The window where the tree was red (see §6) closed
when the other workstream committed its work (`2465730`, `ba8540c`, `46dcac1`,
`11fd26f`): the two missing `api.ts` preview helpers and the `metadata-review`
workflow-shell migration were the last gaps and are now resolved (`c314021`).

Re-run these three commands before any commit; they are the acceptance gate
for the auth milestone.

---

## 4. Findings (things that will bite the next agent)

1. **Migration 012 refuses to run on a non-empty `books` table** and
   `books.owner_id` is non-nullable → the production DB must be **reset** on
   deploy; there is no ownership backfill. Documented in `DEPLOY.md`.
2. **SMTP is off by default** (`SMTP_ENABLED=false`) → verification/reset
   emails are *logged*, not sent. Do not read "no SMTP" as "registration is
   broken"; read it as "the link is in the backend log".
3. **Token lifetimes**: verification 24 h, reset 1 h (single use). `verify-email`
   and `reset-password` **start a session on success**; `forgot-password` and
   `resend-verification` return `202` with generic messages (no account
   enumeration).
4. **`PASSWORD_MIN_LENGTH` defaults to 10** — the frontend mirrors it as
   `MIN_PASSWORD_LENGTH = 10` in the auth pages and the admin user dialogs.
   If the backend default changes, update those two frontend constants.
5. **CSRF**: every state-changing request must echo the readable `csrf_token`
   cookie in `X-CSRF-Token`; the backend answers `403` when it is missing.
6. **Refresh is single-use and rotating**; reuse is detected and revokes the
   session. `api.ts` does a single-flight refresh (one in-flight promise) and
   replays the original request once.
7. **Public catalog rules**: only `complete` and `awaiting_review` books are
   listed/visible publicly; non-owner detail returns metadata only
   (`pages`/`llm_runs`/`jobs` empty, `can_view_full: false`). Uploader display
   name is public; uploader **email is admin-only**.
8. **Admin protections in the UI are mirrored in the backend**: self-protection
   (no self-demote/deactivate/delete), last-admin protection, and deletion
   blocked while the user owns books.
9. **react-query v5 passes a second context argument to `mutationFn`** — assert
   on `mock.mock.calls[0][0]`, not `toHaveBeenCalledWith(payload)`.
10. **jsdom has no `showModal`** — polyfilled in `frontend/tests/setup.ts`
    (toggles the `open` attribute). Any new `<dialog>` component relies on it.
11. **`AdminUser` is a type alias** (`export type AdminUser = AuthUser;`) after
    the empty-interface lint fix — update usages accordingly.

---

## 5. Research methodology (how the design was arrived at)

- **Feasibility before implementation** (AGENTS.md §1): the design was written
  first in `plans/005-auth-rbac.md` (data model, endpoint inventory, endpoint
  contract table, authorization matrix, test plan, rollout order) and approved
  by the user before any code was written.
- **Architecture was verified against the code, not assumed**: the plan's
  "Current architecture (verified)" section was checked against
  `backend/app/api/*`, `Book`/`Job` models, `SearchService`, the SSE/`<img>`
  transport (which is why cookie auth was chosen over bearer tokens), the
  Alembic revision level (011 → 012), and the SQLite in-memory test harness.
- **Backend contracts drive the frontend**: `backend/app/api/auth.py`,
  `dashboard.py`, `admin.py` were written first and the frontend
  (`lib/api.ts` types + page components) was matched to them field-by-field
  (`queue_ahead`, `can_view_full`, `owner_display_name`, `book_count`).
- **Verification-driven**: every increment was checked with
  `pytest` / `tsc --noEmit` / `eslint` / `vitest` before the next increment
  (no big-bang commit).
- **No new external services**: only `aiosmtplib` was added (plus
  `argon2`/`pyjwt` if not already present — check `backend/pyproject.toml`
  before adding anything).

---

## 6. ⚠ Concurrent workstream in the same working tree

> **Resolved (2026-11-11 19:2x).** The parallel UI/UX workstream committed its
> work — `2465730` (backend hardening), `ba8540c` (workflow UI), `46dcac1`
> (admin sidebar/headers), `11fd26f` (docs) — and the auth milestone followed
> as `79f1035`. The tree is green; the notes below are retained as a record of
> the hazard and the staging rules that applied.

The repository has **uncommitted, unrelated work** in the same tree:

| Workstream | Tracking | Files |
|---|---|---|
| UI/UX workflow + admin overhaul | `plans/006-ui-ux-workflow-admin.md`, `todos/008-ui-ux-workflow-admin.md`, `learnings/007-ui-ux-workflow-admin-audit.md` | `frontend/src/lib/workflow-state.ts`, `frontend/src/hooks/use-sse.ts`, `use-job-progress.ts`, `use-unsaved-changes.ts`, `frontend/src/components/shared/{workflow-shell,job-progress-card,progress,save-bar}.tsx`, `frontend/src/app/books/[bookId]/*` |
| Ground-truth data enrichment | `learnings/002..004`, `plans/002`, `backend/scripts/enrich_ground_truth.py`, `fetch_from_wikisource.py`, `eval_ocr.py` | `backend/tests/fixtures/ground_truth/**` (many new dirs), `backend/scripts/fetch_*` |

Observed during this session: `frontend/src/app/books/[bookId]/metadata-review/page.tsx`
was being edited **while this milestone's verification was running** (mtime
18:32 vs. session end 18:34). Consequences observed:

- A lint run reported `'WorkflowStepper' is not defined` in
  `metadata-review/page.tsx` — **not** an auth-file problem.
- One `npm test` run showed 5 failures in `tests/lib/workflow-state.test.ts`
  that vanished on re-run (the file passes in isolation: 15/15) — a
  mid-edit flake.

**Rules for the next agent:**

1. Do **not** "fix" files owned by the other workstream; if lint/test noise
   comes from them, note it and move on (or coordinate).
2. When committing, stage **only** the auth-milestone file list (§7.1),
   using `git add -p` for the shared files listed in the overlap map.
3. Re-run the §3 verification gate right before committing, and note in the
   commit message that lint/test noise from the parallel workstream is
   pre-existing if it is still present.
4. **Do not commit while the other workstream is mid-edit.** During this
   session `metadata-review/page.tsx` was being rewritten mid-verification
   (a lint error appeared and disappeared between two runs). Verify that the
   tree is quiet, or stage only hunks you can attribute to this milestone.

### 6.1 What this milestone already merged into the other workstream

Good news worth recording: the other workstream **adopted** the auth
surface rather than clobbering it — `components/admin/admin-nav.tsx` (its
replacement for `admin-sidebar.tsx`) already links `/admin/users`. Only
verify that link survives their next refactor.

### 6.2 Exact tree-red state at hand-off (owned by the other workstream)

`npx tsc --noEmit` fails with 5 errors, all in their files:

| File | Error | Missing symbol |
|---|---|---|
| `src/app/books/[bookId]/metadata-review/page.tsx` | TS2304 / TS2552 | `useWorkflowHydration`, `useWorkflowStore`, `WorkflowStepper` (imports removed mid-edit while still used) |
| `src/app/books/[bookId]/preprocessing/page.tsx` | TS2305 | `previewPreprocessing`, `getPreprocessingPreviewUrl` (not yet added to `lib/api.ts`) |

Consequence for this milestone: the other workstream still has to **add two
functions to `frontend/src/lib/api.ts`** — a file this milestone also owns
(auth additions). Coordinate: append the new functions rather than
rewriting `api.ts`, or the two changes will conflict.

---

## 7. Remaining work — do these in order

### 7.1 Commit the milestone (nothing is committed yet)

> **Done (2026-11-11):** committed as `79f1035` — *feat(auth): add
> email/password auth, RBAC, and per-user book ownership*. Two follow-ups were
> made afterwards: `c314021` (the `api.ts` preview helpers) and the
> `docs(known-limitations)` update. The plan below is kept for reference.

Suggested logical commit order (small commits, heading + descriptive body,
**no co-author lines**):

1. `feat(backend): add users, sessions, and role-based access control`
   — models, `012_auth_rbac.py`, `core/security.py`, `services/auth_service.py`,
   `services/email_service.py`, `api/auth.py`, `api/deps.py`, `api/dashboard.py`,
   `services/dashboard_service.py`, `api/admin.py` (user mgmt + ownership
   filters), ownership enforcement in `api/{books,pages,metadata,extraction,stages,sse,bulk,library}.py`,
   `scripts/create_admin.py`, `Makefile` (`create-admin`), `backend/pyproject.toml`,
   `backend/uv.lock`, `backend/tests/**` (auth/rbac/dashboard/conftest).
2. `feat(frontend): add auth pages, session handling, and route guards`
   — `lib/api.ts`, `components/auth/*`, `app/{login,register,verify-email,forgot-password,reset-password}`, `app/layout.tsx` + `providers.tsx` wiring, `frontend/tests/setup.ts`.
3. `feat(frontend): add per-user dashboard and admin user management`
   — `app/dashboard/`, `app/admin/users/`, `components/shared/{stat-card,action-menu}.tsx`,
   `components/admin/owner-filter.tsx`, `admin/{page,books/page,jobs/page}.tsx`,
   `library/[bookId]/page.tsx`, `library/book-card.tsx`, the five new page tests.
   (`admin/admin-sidebar.tsx` is **not** in this list — the other workstream
   deleted it and replaced it with `admin/admin-nav.tsx`, which already
   carries the `/admin/users` link; see §6.1.)
4. `docs(auth): document accounts, sessions, and the admin surface`
   — `docs/api-reference.md`, `README.md`, `DEPLOY.md`, `docs/user-guide.md`,
   `docs/{known-limitations,known-issues,changelog,local-development-guide}.md`,
   `learnings/008-auth-rbac-outcome.md`, `learnings/README.md`,
   `plans/005-auth-rbac.md`, `todos/009-auth-rbac-handoff.md`.

Stage explicitly (e.g. `git add <paths>` or `git add -p`) — **do not** use
`git add -A`, it would sweep in the other workstream's files.

#### Overlap map (files touched by BOTH workstreams → stage with `git add -p`)

| File | Auth-milestone hunks | Other workstream hunks |
|---|---|---|
| `frontend/src/app/admin/books/page.tsx` | Owner column + `OwnerFilter`, `ActionMenu` refactor | admin table rewrite (≈200 changed lines) |
| `frontend/src/app/admin/jobs/page.tsx` | Owner column + `OwnerFilter` | admin jobs table/aggregation |
| `frontend/src/app/admin/layout.tsx` | Users nav link | layout rework (sidebar → `admin-nav.tsx`) |
| `frontend/src/components/admin/admin-sidebar.tsx` | (my "Users" link was added here) | **file deleted** by the other workstream — replaced by `components/admin/admin-nav.tsx`, which already carries the `/admin/users` link (verified 2026-11-11). Nothing to commit from my side. |
| `frontend/src/app/library/[bookId]/page.tsx` | `can_view_full` gating, owner name | layout/resume-banner rework |
| `frontend/src/app/layout.tsx`, `providers.tsx` | `AuthProvider` + `RouteGuard` wiring | — |
| `frontend/src/lib/api.ts` | axios auth/CSRF/refresh + auth/dashboard/admin API functions | **also needs** `previewPreprocessing` + `getPreprocessingPreviewUrl` (see §6.2) |
| `docs/user-guide.md` | Accounts section, public-entry note, troubleshooting entries | preprocessing/Qwen wording changes |

Frontend files owned **exclusively** by the other workstream and therefore
**not** to be staged: `frontend/src/lib/workflow-state.ts`,
`frontend/src/hooks/use-{sse,job-progress,unsaved-changes}.ts`,
`frontend/src/components/shared/{workflow-shell,job-progress-card,progress,save-bar}.tsx`,
`frontend/src/app/books/[bookId]/*` (except any auth hunks),
`backend/tests/fixtures/ground_truth/**`, `backend/scripts/{enrich_ground_truth,fetch_from_wikisource,eval_ocr}.py`.

Backend auth files are effectively exclusive to this milestone, except
`backend/app/api/admin.py`, `backend/app/api/books.py` and
`backend/tests/conftest.py` (shared with the pipeline tests) — review those
three with `git diff` before staging.

### 7.2 Post-commit verification

```bash
cd backend && uv run pytest -q          # expect 272 passed, 1 skipped
cd frontend && npx tsc --noEmit         # expect clean
cd frontend && npm test                 # expect all green
cd frontend && npm run lint             # expect 0 errors (ignore other workstream noise)
```

### 7.3 Update the plan and learnings (AGENTS.md §4) — DONE

- ✅ `plans/005-auth-rbac.md` → **Status** changed to "Implemented" and an
  "Implementation results (2026-11-11)" section added (planned vs. delivered
  table with deviations, e.g. the DB reset).
- ✅ `learnings/008-auth-rbac-outcome.md` written with the
  `learnings/README.md` template (10 findings: cookie+CSRF choice, single-use
  refresh, `token_version` invalidation, metadata-only enforcement at the
  serializer, catalog whitelist, migration-012 guard, SMTP-off semantics,
  SQLite-compatible auth fixtures, mirrored frontend knobs, react-query v5
  mutation arg) + index entry in `learnings/README.md`.
- ⬜ Optional: note the outcome in `PRODUCT.md` — accounts, dashboard and
  admin users are product-level changes.

### 7.4 Deploy-time items (not doable in this repo — for the operator)

- Configure SMTP secrets in the git-ignored `.env` / Dokploy env tab.
- Run `make create-admin EMAIL=... DISPLAY_NAME=...` once on the new stack.
- Reset the production DB (migration 012 will refuse otherwise) and re-upload
  books (ownership is per-user, no backfill).

### 7.5 Optional follow-ups (not required for the milestone)

- Per-user upload/job quotas (deliberately out of scope in the plan).
- Rate limiting beyond the auth endpoints.
- Email-change flow, admin impersonation, per-book sharing (out of scope).

---

## 8. Open questions / decisions needed from the user

1. **Production DB reset**: the plan assumed the DB is reset on deploy. Confirm
   the operator accepts losing the existing books (and re-uploads them under
   their owners).
2. **Auth for bulk operations / Wikibase credentials**: bulk endpoints are
   admin-only now; confirm the bulk/QuickStatements workflow still fits the
   single-admin model.
3. Whether the **public catalog** should ever include `awaiting_review` books
   (it currently does, per the locked decision) — flag only, do not change.

---

## 9. Dependencies (what blocks what)

```
backend auth + RBAC (DONE)
   ├─► frontend auth pages / route guards (DONE)
   │      └─► /dashboard, /admin/users, library gating (DONE)
   │             └─► docs (DONE)
   │                    └─► commits (DONE — `79f1035` + follow-ups)
   └─► migration 012 + create-admin CLI (DONE)
          ├─► deploy: reset DB → migrate → create-admin → SMTP (OPERATOR, §7.4)
          └─► manual end-to-end check: register → verify → login → upload →
             pipeline → dashboard → admin views (PENDING — needs the stack up
             and a real scanned PDF; §7.4)
```

The only hard blocker left is the **live-stack verification**: the Docker
stack was not fully up during this session (the parallel workstream also
reported wikibase/flower restart issues), so registration → email → login →
upload → pipeline was not exercised end-to-end in a browser.
