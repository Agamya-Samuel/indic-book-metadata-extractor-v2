# 011 — Frontend + Backend Route Redesign: Handoff & Implementation Outline

Companion to this document is the route inventory below. Read this first when
taking over the route-redesign task. **No route renaming has been done yet** —
this is the agreed outline awaiting the user's go-ahead on the three open
product questions in §7.

- **Date:** 2026-11-12
- **Status:** Inventory complete, decisions locked. Implementation not started.

---

## 0. Recovery note — read before touching the tree

At the start of this session the working tree *looked* like it carried an
uncommitted plan-007 backend change set. That was a **stale-session artifact**:
the tree had an older stash re-applied on top of HEAD. Verified `2026-11-12`:

- Plan 007 is **fully committed** in HEAD — backend `476a766`, tests `ffe87fa`,
  frontend `5263668`, docs `7e836f7`. `frontend/src/app/pending-approval/`,
  `route-guard.tsx` (`PENDING_PATH`, `ADMIN_EXACT_PATHS = ["/library"]`), admin
  approvals, and the admin-only library are all in HEAD.
- During recovery a stale stash was applied and then fully reversed; the tree is
  now **clean at HEAD** (`git status` empty).
- Two **pre-existing user stashes are intact and untouched**:
  `stash@{0}` "ui-spinner" (frontend admin spinner/refactor) and
  `stash@{1}` "qwen" (LLM model work). **Do not pop/drop them.**
  The stale plan-007 snapshot also remains recoverable as commit `1e3ce65`
  (unreachable) — do not re-apply it; its content is already in HEAD.

**Consequence for this task:** the route pass now runs on a *settled, committed*
base, per the locked Q1 decision (b). No 007 work is outstanding.

---

## 1. Decisions locked with the user (2026-11-12)

| # | Topic | Decision |
|---|---|---|
| Q1 | Sequencing | Finish/settle 007 first, then route pass on the committed base. **007 is already committed → route pass can start immediately.** |
| Q2 | API prefix | **Keep `/api`** as the mount and the whole `/auth/*` surface. Only re-group segments *under* `/api`. |
| Q3 | Library convergence | Converge the admin "all books" surface onto **`/api/admin/books`** (richer filters) as the single source of truth; **retire `/api/library/*`**. `/api/dashboard/books` stays the user's own list. |
| Q4 | Action naming | **Keep RPC verb suffixes** (`/reset`, `/rerun-ocr`, `/run-extraction`, `/review/complete`). Do not convert to REST sub-resources. |
| Q5 | Frontend moves | **Minimal** — re-prefix/consolidate only; do **not** physically relocate the pipeline pages (`/books/[bookId]/*`) in this pass. |

Net effect: this is a **convergence + grouping + naming** pass, not a rewrite.
The big win is removing the `/library/*` ↔ `/admin/books` duplication and
grouping the root-mounted dashboard/job routes.

---

## 2. Current backend inventory (mounted at `/api`, `main.py:185`)

Auth is outside the approval gate; every other app router depends on
`require_approved_user` (`router.py`); the admin router additionally depends on
`require_admin`.

| Group | Prefix | Endpoints |
|---|---|---|
| Auth (public) | `/auth` | `POST register, login, refresh, logout, verify-email, resend-verification, forgot-password, reset-password, change-password`; `GET me` |
| Books | `/books` | `POST upload`; `GET {id}`; `GET {id}/pages/{n}/thumbnail`; `POST|GET {id}/pages`; `POST {id}/preprocessing`; `POST {id}/run-ocr`; `GET {id}/ocr-status`; `GET {id}/jobs`; `DELETE {id}`; `POST {id}/reset`, `{id}/rerun-ocr`, `{id}/rerun-extraction` |
| Extraction | `/books` | `GET models`; `POST {id}/run-extraction`, `{id}/retry-extraction` |
| Metadata | `/books` | `GET|PUT {id}/metadata`; `POST {id}/review/complete`; `GET {id}/metadata/fields`, `{id}/metadata/evidence`; `GET {id}/llm-runs` |
| Stages | `/books` | `GET {id}/stages`, `{id}/stages/current` |
| Pages | `/pages` | `PUT {id}/preprocessing`; `POST|GET {id}/preprocessing/preview`; `GET {id}/image`; `GET|PUT {id}/ocr` |
| SSE | `/sse` | `GET books/{id}/events` |
| Library (**admin-only now**) | `/library` | `GET books`, `search`, `filters`; `GET books/{id}/detail` — *target: retire, fold into `/admin/books`* |
| Dashboard | **root** | `GET /dashboard/summary`, `/dashboard/books`, `/dashboard/jobs`; `POST /jobs/{id}/cancel` |
| Bulk (admin) | `/bulk` | `GET stats`; `POST export`, `import`, `export-wikibase` |
| Admin | `/admin` | `GET|POST users`; `GET users/pending-count`; `GET|PATCH|DELETE users/{id}`; `POST users/{id}/approve\|reject\|reset-password`; `GET stats`; `GET books`; `DELETE books/{id}`; `POST books/{id}/reset\|rerun-ocr\|rerun-extraction`; `GET jobs`; `POST jobs/{id}/cancel` |
| Health | — | `GET /health` (outside `/api`) |

### Indirection that makes `/library/*` retirement easy

`/library/*` is already `require_admin`-gated (`library.py:25,87,128`), and
`/admin/books` already exists with owner filters. The frontend is the only
consumer; `frontend/src/lib/api.ts` isolates every call in `getLibraryBooks`,
`searchLibrary`, `getFilterOptions`, `getBookDetail`. Retiring `/library/*` is
therefore an API + callsite change, not a data change.

---

## 3. Current frontend inventory (`frontend/src/app`)

| Section | Routes |
|---|---|
| Public | `/` (landing), `/login`, `/register`, `/verify-email`, `/forgot-password`, `/reset-password` |
| Authenticated | `/upload`, `/dashboard`, `/books/[bookId]/{select-pages, preprocessing, extracting-pages, ocr-processing, ocr-review, llm-config, metadata-review, jobs}` |
| Admin-only | `/admin`, `/admin/{users, books, jobs}`, `/bulk-operations` |
| Mixed | `/library` (admin catalog), `/library/[bookId]` (owner-or-admin book detail) |
| Holding | `/pending-approval` |

Route gate: `frontend/src/components/auth/route-guard.tsx`
(`PUBLIC_PATHS`, `ADMIN_PATHS = ["/admin","/bulk-operations"]`,
`ADMIN_EXACT_PATHS = ["/library"]`, `PENDING_PATH`).
Nav: `frontend/src/components/shared/app-navbar.tsx` (`navLinks` with
`scope: all | auth | admin`).

### Inconsistencies identified

1. **Two book-detail pages:** `/books/[bookId]` (pipeline) and
   `/library/[bookId]` (detail card). Both are reachable.
2. **Three book-list endpoints for one resource:** `/library/books` (admin),
   `/admin/books` (admin), `/dashboard/books` (own).
3. **Root-mounted dashboard routes** (`/dashboard/*`, `/jobs/{id}/cancel`) sit
   outside the prefix grouping every other router uses.
4. **Naming drift:** frontend `/bulk-operations` vs API `/bulk`.
5. **RPC verbs** used consistently (kept per Q4).

---

## 4. Proposed target structure

### 4.1 Backend (changes only — everything else stays)

| Change | From | To |
|---|---|---|
| Retire admin catalog listing | `GET /api/library/books`, `/search`, `/filters` | `GET /api/admin/books` (filters already present) |
| Retire admin book detail | `GET /api/library/books/{id}/detail` | `GET /api/admin/books/{id}` (new lightweight wrapper) |
| Group dashboard | `GET /api/dashboard/*` (root) | keep paths; ensure a single `dashboard` router with prefix `/dashboard` (no root-mounted routes) |
| Group job cancel | `POST /api/jobs/{id}/cancel` | `POST /api/dashboard/jobs/{id}/cancel` (owner) — admin keeps `/api/admin/jobs/{id}/cancel` |
| Keep | `/api/books/*`, `/api/pages/*`, `/api/bulk/*`, `/api/admin/*`, `/api/auth/*`, `/api/sse/*`, `/health` | unchanged |

> `/library` prefix disappears entirely from the API. Any straggler import of
> `app.api.library` must be removed from `router.py`.

### 4.2 Frontend (minimal moves)

| Change | From | To |
|---|---|---|
| Admin catalog | `/library` page | `/admin/library` (renders the admin book list) |
| Book detail | `/library/[bookId]` | **Keep the page**, but reach it from `/admin/library` and from the dashboard for owners. Decide Q7 (below) whether to rename to `/books/[bookId]/details`. |
| Bulk | `/bulk-operations` | `/admin/bulk` (cosmetic; nav + guard only) |
| Everything else | unchanged | — |

Update `route-guard.tsx` (`ADMIN_PATHS`, drop `ADMIN_EXACT_PATHS` if library
detail is renamed), `app-navbar.tsx`, and every `router.push`/`href`/`api.ts`
callsite (enumerate with the grep in §6).

---

## 5. Implementation steps (increments)

1. **Backend convergence (own commit).** Add `GET /api/admin/books/{id}`;
   repoint the admin catalog frontend calls to `/api/admin/books`; delete
   `app/api/library.py` and its `include_router`; move job-cancel to
   `/api/dashboard/jobs/{id}/cancel`; move dashboard off the root mount.
2. **Backend tests.** Update `test_api_library.py` → `test_admin_books.py`
   semantics; add coverage that `/api/library/*` is gone (404) and admin book
   detail enforces admin.
3. **Frontend routing (own commit).** Create `/admin/library`; rename
   `/bulk-operations` → `/admin/bulk`; update guard + navbar + callsites;
   delete the old `/library` list page.
4. **Docs.** Regenerate the route tables in `docs/api-reference.md`; update
   `docs/known-limitations.md`, `docs/changelog.md`, `README.md` breadcrumbs.
5. **Validation.** `uv run pytest` (needs Redis/Celery up — see §6 caveat),
   `npm run lint`, `npx tsc --noEmit`, `npm test`; then verify on the **deployed
   host** with the agent browser (per the "verify on deployed host" rule):
   admin sees `/admin/library`; a regular user gets redirected; no 404s in the
   pipeline; `/api/library/*` returns 404.
6. **Learning.** `learnings/014-routing-redesign-outcome.md`.

---

## 6. Known caveats to hand over

- **Local tests need infra.** Three backend tests fail locally because Redis
  (6379) and Celery are not running: `test_select_pages_success`,
  `test_select_pages_duplicate_deduped`, `test_run_extraction_no_ocr_text`.
  Confirmed pre-existing on the clean base (not caused by any change). Run the
  suite with `docker compose up postgres redis` first, or via
  `docker compose exec backend`.
- **ruff debt.** `uv run ruff check app tests` reports 41 errors, mostly
  unused imports in `tests/`, unrelated to routing. Fix opportunistically in
  files you touch; do not widen scope.
- **Callsite enumeration** (run before/after the change):
  `rg "/(library|dashboard|bulk-operations|jobs)" frontend/src`
  and `rg "library|dashboard|/bulk" frontend/src/lib/api.ts backend/app`.
- **Do not** touch the two user stashes (§0).

---

## 7. Open product questions (need the user's answer before step 3)

- **Q6 — Admin catalog path.** Is `/admin/library` the desired URL for the
  admin book catalog, or keep the top-level `/library` (admin-only) and only
  retire the *API* `/library/*`? (API convergence can proceed either way.)
- **Q7 — Book detail route.** Keep the detail page at `/library/[bookId]`, or
  move it under the book it belongs to as `/books/[bookId]/details` and make
  `/admin/library` row → that URL? The latter is cleaner but touches more
  callsites (contradicts Q5's "minimal" only in spirit).
- **Q8 — Bulk path.** Rename `/bulk-operations` → `/admin/bulk`, or leave the
  frontend path and only align the API? (Low stakes.)

Defaults if the user does not object: **Q6 keep `/library` top-level
(admin-only)** to minimize churn, **Q7 keep `/library/[bookId]`**, **Q8 rename
to `/admin/bulk`**.

---

## 8. Acceptance criteria

- No `/api/library/*` endpoint remains; admin book listing/detail served by
  `/api/admin/books` with admin enforcement tested.
- Dashboard and job-cancel routes are grouped (no root-mounted app routes).
- Frontend has one entry point per resource; nav and guard reflect the new
  structure; no dead links; `tsc`, `lint`, and `vitest` green.
- All existing workflows (upload → select → preprocess → OCR → extraction →
  metadata review → library/admin) still function on the deployed host.
- Docs (`api-reference.md`, `changelog.md`) match the shipped routes.
