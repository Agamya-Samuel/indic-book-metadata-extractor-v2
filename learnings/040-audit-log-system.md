# 040 — Administrator Audit Log System: Build Outcome

- **Date:** 2026-11-20
- **Study context:** plans/025 asked for a centralised audit trail. Analysis showed the backend core
  (model, service, migration `023` trigger, read-only API, action catalogue, auth/admin/book/config
  instrumentation) already existed; this record documents what was added, what the design proved,
  and the testing gap that shaped verification.
- **Status:** Shipped. See `CHANGELOG.md` (Unreleased → Added → Audit logs) and
  `plans/025-admin-audit-log.md`.

## Summary

The audit system is complete and append-only at the database layer. The remaining work was
instrumentation coverage (processing, exports, workers), the admin UI, and verification; all three
landed without touching the existing core.

## Key findings

### 1. The existing core matched the locked design

`models/audit_log.py` + `services/audit_service.py` already implemented every locked decision:
hybrid write paths (`record` transactional vs `record_isolated` post-commit), the fail-closed
`CRITICAL_ACTIONS` set, `actor_type` + `subject_user_id` with email/display-name snapshots,
`resource_id` as varchar(64), `sanitize()` redaction, `diff()`/`change_snapshots()`, and the
`audit.viewed` meta-audit. Instrumentation gaps were the actual work, not architecture.

### 2. Worker audit writes needed a third path

Celery signal handlers and lifespan loops run sync or background code with no request session, and
their ambient sessions differ (persistent worker loop vs uvicorn loop). `record_system()` resolves
this: it opens its own session from `async_session_factory` and runs it on a fresh thread/loop when
the caller's loop is already busy, never raising into the worker. The Celery failure hook
(`job.failed`), watchdog relay (`system.watchdog_alert`) and partial-OCR outcome
(`ocr.partial_failure`) use it with `label=` naming the source. The job reaper instead records its
`job.reaped` rows with the transactional `record()` inside the reap transaction (reaped ⟺ audited,
and no per-job thread/connection on the request loop).

### 3. SQLite tests cannot exercise the append-only trigger

The suite runs on `sqlite+aiosqlite` in-memory, where plpgsql does not exist. The trigger is
therefore verified by a **gated** integration test (`tests/integration/test_audit_trigger_postgres.py`,
skipped unless `TEST_POSTGRES_URL` points at a migrated Postgres) plus `poc/005`. This is a residual
risk to re-verify against staging each maintenance window — noted in the PoC follow-ups.

### 4. Two incidental backend bugs surfaced during instrumentation

- Query-parameter defaults bypass FastAPI enum coercion (`format: ExportFormat = Query(default="csv")`
  stayed a `str`); `ExportFormat` is a `Literal`, so no `.value` — use the value directly.
- `book.status` is a plain `str` when loaded from the DB (the `Mapped[str]` column does not
  coerce StrEnum members); `book.status.value` raised `AttributeError` on loaded rows. Use
  `str(book.status)` for snapshots.

## Recommendation

Keep the system as shipped. When extending coverage, follow the write-path table in
`docs/application/backend.md` §9.1 and record diffs via `change_snapshots` so 49-field metadata
saves stay bounded. Do not add mutation routes to the audit API — append-only is enforced at both
the routing and DB layers.

## Next steps

- Re-run the `TEST_POSTGRES_URL` trigger test against staging and record output in the deployment log.
- If volume ever demands retention, partition by range on `created_at` and re-attach the triggers to
  each child (see `poc/005` follow-ups).

## References

- `plans/025-admin-audit-log.md` — the increment plan
- `poc/005-audit-log-append-only-poc.md` — trigger reproduction
- `docs/application/backend.md` §9.1, `docs/application/data-model.md` (`audit_logs`),
  `docs/reference/api.md` (Audit logs), `docs/operations/runbook.md` §1
- `backend/app/services/audit_service.py`, `backend/app/api/audit.py`, migration `023`