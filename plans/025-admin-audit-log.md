# 025 — Administrator audit logs and activity tracking

**Status:** implemented
**Author:** platform
**Created:** 2026-11-20

## Problem

The platform needs a centralized audit trail so administrators can review who did what,
when, and on which records — covering user/admin actions, configuration changes, job
lifecycle events, and system-level failures.

## Current state (pre-plan analysis)

The audit **core already exists** and matches the agreed design:

| Component | Location | Status |
| --- | --- | --- |
| `audit_logs` table, denormalized actor snapshots, no FKs | `backend/app/models/audit_log.py` | built |
| Append-only Postgres trigger (blocks `UPDATE`/`DELETE`/`TRUNCATE`) + indexes | `backend/alembic/versions/023_audit_logs.py` | built |
| Action catalog (~50 actions across all 8 categories) | `services/audit_service.py` (`AuditAction`, `ACTION_SPECS`) | built |
| Hybrid write paths: `record()` (same transaction) vs `record_isolated()` (post-commit, never raises) | `services/audit_service.py` | built |
| Fail-closed set (`CRITICAL_ACTIONS`: user delete/update, SMTP + maintenance config) | `services/audit_service.py` | built |
| Secret redaction + truncation (`sanitize()`, `diff()`, `change_snapshots()`) | `services/audit_service.py` | built |
| Read-only filterable/paginated API + `GET /actions` catalog + `audit.viewed` meta-audit | `backend/app/api/audit.py` | built |
| Request-ID middleware, client IP, actor snapshots (email + display name) | `core/request_context.py`, `api/deps.py` | built |
| Instrumented flows: full auth, admin user mgmt, admin book ops, upload/language/pages-selected/preprocessing-applied, SMTP + maintenance config, job cancel/retry/bulk-cancel, `audit.viewed` | `api/auth.py`, `api/admin.py`, `api/books.py`, `services/auth_service.py`, `services/smtp_service.py`, `services/maintenance_service.py` | built |

**Remaining gaps** (this plan):

1. **Frontend:** no `/admin/audit` page, no admin-nav entry, no API client module/types.
2. **Processing instrumentation:** `ocr.requested`, `ocr.correction_saved`, `ocr.partial_failure`,
   `preprocessing.updated`, `extraction.requested`, `extraction.retried`,
   `metadata.updated` (with before/after diffs), `metadata.review_completed`.
3. **Export instrumentation:** `export.metadata`, `export.wikibase`, `bulk.import`.
4. **System/worker instrumentation:** `job.failed` (Celery `task_failure`),
   `job.reaped` (job reaper), `system.watchdog_alert` (watchdog relay).
5. **Tests:** no audit coverage at all (sanitize, diff, each event landing, RBAC, append-only trigger).
6. **Docs:** no audit chapter in `docs/`.

## Locked decisions (unchanged from the agreed design)

| Decision | Choice |
| --- | --- |
| Write path | Hybrid: `record()` in the action's transaction where the route owns the commit; `record_isolated()` for auth + post-commit paths |
| System events | New **sync helper** in `audit_service` that opens its own session from `async_session_factory` inside `run_async` — workers use sync sessions, not request handlers |
| Append-only | Existing Postgres trigger + GET-only routing (no changes) |
| Retention | Keep forever |
| Failed-login identity | Attempted email + reason stored; never the password (already implemented) |
| Audit write failure | Best-effort + loud structured log via `record_isolated`; fail-closed for the `CRITICAL_ACTIONS` set (already implemented) |
| Meta-audit | `audit.viewed` kept **as-is** (one row per list/detail request) + new `exclude_meta` query param (default `false`) so admins can filter it out |
| Export | No CSV export of the audit log itself |
| Actor model | `actor_type` + `subject_user_id` with email/display-name snapshots (already implemented) |
| Trigger verification | New `@pytest.mark.postgres` test gated on `TEST_POSTGRES_URL` (skipped by default) + manual PoC script under `poc/` |

## Event catalog → instrumentation map

Already instrumented (no work): all `auth.*`, all `user.*`, `book.uploaded`, `book.deleted`,
`book.language_changed`, `book.reset`, `book.rerun_ocr`, `book.rerun_extraction`,
`pages.selected`, `preprocessing.applied`, `job.cancelled`, `job.retried`,
`config.smtp_updated`, `config.smtp_tested`, `config.maintenance_updated`, `audit.viewed`.

To instrument (this plan):

| Action | Call site | Path | Notes |
| --- | --- | --- | --- |
| `ocr.requested` | `api/books.py` start-OCR route | `record_isolated` | after job enqueue; details: job_id, page count |
| `ocr.correction_saved` | `api/pages.py:144` `PUT /{page_id}/ocr` | `record` | route owns commit; diff old vs new `corrected_text` via `change_snapshots` |
| `ocr.partial_failure` | OCR finalization path (`tasks/ocr_tasks.py` outcome or `services/ocr_service.py`) | sync helper | actor `system`, `subject_user_id` = book owner; details: failed/total pages |
| `preprocessing.updated` | `api/pages.py:40` `PUT /{page_id}/preprocessing` | `record` | diff `preprocessing_config` |
| `extraction.requested` | `api/extraction.py:81` `run_extraction` | `record_isolated` | details: job_id, batch config summary |
| `extraction.retried` | `api/extraction.py:178` `retry_extraction` | `record_isolated` | details: previous job_id, new job_id |
| `metadata.updated` | `api/metadata.py:51` `PUT /{book_id}/metadata` | `record` | `change_snapshots` over changed field keys only (keeps 49-field saves bounded) |
| `metadata.review_completed` | `api/metadata.py:91` `POST /{book_id}/review/complete` | `record` | details: book status transition |
| `export.metadata` | `api/export.py:46,59` (single + bulk filter export) | `record_isolated` | details: row count, filter summary |
| `export.wikibase` | `api/wikibase.py:29` `publish` | `record_isolated` | details: item count, dry-run flag |
| `bulk.import` | `api/bulk.py:87` `bulk_import` | `record_isolated` | details: rows processed, errors count |
| `job.failed` | `tasks/celery_app.py:33` `_on_task_failure` | sync helper | actor `system`, details: task_id, exception class, job_id |
| `job.reaped` | `services/job_reaper.py` (per reaped job, summary acceptable) | sync helper | actor `system`, details: job_id, stale minutes, last progress |
| `system.watchdog_alert` | `services/watchdog_service.py:61` `poll_and_notify` | sync helper | actor `system`, details: key, reason |

Implementation rules for every new call site:

* Route owns the commit (mutation applied in the same session) → `record()` before `await db.commit()`.
* Action already committed or runs outside a request → `record_isolated()`.
* Worker/background loop → new `record_system()` sync helper.
* Changes use `change_snapshots()` so only changed keys are stored; `sanitize()` runs inside `_build_row` regardless.

## Increment plan

### Increment 1 — Processing instrumentation (backend)

* `api/pages.py`: `ocr.correction_saved` + `preprocessing.updated` (transactional `record` with diffs).
* `api/books.py`: `ocr.requested`.
* `api/extraction.py`: `extraction.requested`, `extraction.retried`.
* `api/metadata.py`: `metadata.updated` (diff), `metadata.review_completed`.
* Unit tests: each action produces exactly one row with expected `category`, `resource_*`, and `before`/`after` keys.

### Increment 2 — Export + bulk instrumentation (backend)

* `api/export.py`, `api/wikibase.py`, `api/bulk.py` as mapped above.
* Unit/integration tests: row counts and failure paths (export of zero rows still logged as success with `count=0`? — log with result `success`, details `{count: 0}`).

### Increment 3 — System/worker events (backend)

* New `record_system(*, action, description, ...)` in `services/audit_service.py`: opens a fresh session via `async_session_factory` wrapped in `run_async`, builds `system_context(label=...)`, commits, logs loudly on failure (never raises into the worker).
* Hook `task_failure` signal, job reaper, watchdog relay, partial-OCR outcome.
* Tests: helper writes a row under a fake `async_session_factory`; failure path logs and returns `None`.

### Increment 4 — Filter API refinement + tests

* `api/audit.py`: add `exclude_meta: bool = False` query param; when true, `action != audit.viewed`.
* Integration tests: filters (user, role, action, category, resource, date range, `q`), sort columns
  (`created_at`/`action`/`actor`/`category`/`result`) + order, pagination, 404 on unknown id,
  non-admin gets 403, no POST/PUT/PATCH/DELETE routes exist.
* `@pytest.mark.postgres` append-only test (gated on `TEST_POSTGRES_URL`): insert a row, assert
  `UPDATE`/`DELETE`/`TRUNCATE` all raise; skipped with a clear message otherwise.

### Increment 5 — PoC script (per AGENTS.md gate)

* `poc/005-audit-log-append-only-poc.md` (next free number after `004`): documents the trigger
  test run against a real Postgres, with the exact SQL and observed errors, plus how to reproduce.

### Increment 6 — Frontend

* `frontend/src/lib/api/audit.ts` (or extend existing client module — follow current structure):
  `listAuditLogs(params)`, `getAuditLog(id)`, `listAuditActions()`; TypeScript types mirroring
  `schemas/audit.py`.
* `frontend/src/app/admin/audit/page.tsx`:
  * filter bar — search (`q`), category select (from `/actions`), action select (dependent on category),
    actor (user id/email text), role, result, resource type + id, date range with presets
    (24 h / 7 d / 30 d / custom);
  * `DataTable` (existing `components/shared/data-table.tsx`) with sortable timestamp (default desc),
    actor (display name + email + role badge), action label, description, resource, result badge;
  * pagination via existing pagination pattern;
  * expanded row (`renderExpandedRow` if present, else expandable detail panel): before/after diff
    table (only changed keys), request metadata (IP, user agent, request id), raw-JSON toggle;
  * filters mirrored into the query string so a filtered view is shareable;
  * empty and error states.
* `frontend/src/components/admin/admin-nav.tsx`: add "Audit logs" entry (admin-only).
* Frontend tests if the project has a test setup; otherwise verify manually per
  `docs/testing/running-tests.md`.

### Increment 7 — Docs + changelog + learnings

* `docs/application/data-model.md` — audit_logs section (columns, trigger, retention).
* `docs/reference/api.md` — `GET /admin/audit-logs`, `/{id}`, `/actions`, all query params incl. `exclude_meta`.
* `docs/application/backend.md` — audit service usage rules (which write path to use, secret policy).
* `docs/architecture/system-architecture.md` — audit as cross-cutting concern; system-event flow.
* `docs/operations/runbook.md` — where to look during incidents (audit log as first stop).
* `CHANGELOG` entry.
* `learnings/040-audit-log-system.md` (verify next free number): findings, trigger PoC result,
  SQLite-vs-Postgres testing gap, worker write path rationale.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| SQLite test suite cannot run the append-only trigger | Gated `@pytest.mark.postgres` test + PoC script (increments 4–5) |
| Worker audit writes could block/raise into Celery tasks | `record_system` never raises; failures logged via `_log_failure` path |
| `audit.viewed` adds one row per admin view | `exclude_meta` filter param; keep default behavior for completeness |
| Page rows are deleted/recreated on re-selection (`select_pages`) — page IDs are run-scoped | `pages.selected` records counts + page numbers only (already implemented) |
| No `username` field on `users` | Actor identity = `display_name` + `email` snapshots (already implemented) |
| `metadata.updated` could store a 49-field blob | `change_snapshots()` stores only changed keys |
| Long OCR text / wide lists could bloat rows | `sanitize()` truncates (>2000 chars, >50 items, depth >5) and sets `truncated=true` (already implemented) |

## Verification checklist

1. `pytest` green (SQLite suite) — new unit + integration tests included.
2. `TEST_POSTGRES_URL=... pytest -m postgres` green — trigger rejects `UPDATE`/`DELETE`/`TRUNCATE`.
3. Manual: every event in the catalog table produces exactly one row with correct actor, category,
   resource, and result; failed login stores `attempted_email` and never a password.
4. Manual UI pass: filters, sort, pagination, shareable URL, detail expansion, role badge,
   non-admin sees 403 on `/admin/audit` and no nav entry.
5. `ruff` + frontend lint/typecheck clean.