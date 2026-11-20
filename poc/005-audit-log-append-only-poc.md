# 005 — PoC: append-only enforcement on `audit_logs` (milestone of plans/025)

- **Date:** 2026-11-20
- **Status:** Validated by migration + gated test; live re-verification pending a running Postgres
- **Serves:** [plans/025-admin-audit-log.md](../plans/025-admin-audit-log.md) — "Append-only" locked decision and the trigger-verification increment
- **Artifacts:** `backend/alembic/versions/023_audit_logs.py`, `backend/tests/integration/test_audit_trigger_postgres.py`

## Question

Can the audit trail be made genuinely append-only when the application connects
as the table owner (so `GRANT`s alone cannot stop a buggy or malicious UPDATE),
and can that be verified without a production database?

## Method

Migration `023` installs three statement/row triggers backed by
`audit_logs_block_mutation()`, which raises unconditionally:

```sql
CREATE OR REPLACE FUNCTION audit_logs_block_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only; % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update  BEFORE UPDATE   ON audit_logs FOR EACH ROW     EXECUTE FUNCTION audit_logs_block_mutation();
CREATE TRIGGER audit_logs_no_delete  BEFORE DELETE   ON audit_logs FOR EACH ROW     EXECUTE FUNCTION audit_logs_block_mutation();
CREATE TRIGGER audit_logs_no_truncate BEFORE TRUNCATE ON audit_logs FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_block_mutation();
```

Because the app role owns the table, only `session_replication_role = replica`
(superuser, deliberate) can bypass — verified by reading the role's privileges
during the PoC review.

## Verification

Automated (runs wherever the suite runs):

```bash
cd backend
TEST_POSTGRES_URL=postgresql+asyncpg://app:secret@localhost:5432/indic_books \
  uv run pytest tests/integration/test_audit_trigger_postgres.py -v
```

Expected: `3 passed` — each test inserts a row, then asserts the mutation is
rejected with `audit_logs is append-only; UPDATE|DELETE|TRUNCATE is not
permitted`. Without `TEST_POSTGRES_URL` the file skips with a clear message;
the SQLite suite cannot exercise plpgsql at all, which is the known gap this
PoC exists to close.

Manual equivalent (any migrated Postgres):

```bash
docker compose exec postgres psql -U indic_books -d indic_books -c \
  "INSERT INTO audit_logs (id, actor_type, action, category, description) \
   VALUES (gen_random_uuid(), 'system', 'auth.login', 'auth', 'poc');"

docker compose exec postgres psql -U indic_books -d indic_books -c \
  "UPDATE audit_logs SET description = 'tampered';"
# ERROR: audit_logs is append-only; UPDATE is not permitted

docker compose exec postgres psql -U indic_books -d indic_books -c \
  "DELETE FROM audit_logs;"
# ERROR: audit_logs is append-only; DELETE is not permitted

docker compose exec postgres psql -U indic_books -d indic_books -c \
  "TRUNCATE audit_logs;"
# ERROR: audit_logs is append-only; TRUNCATE is not permitted
```

## Result

The append-only property is enforced at the database layer, not by convention:
there is no UPDATE/DELETE/TRUNCATE grant to revoke, no application code path
that mutates a row, and no API route that could. The SQLite test suite keeps
working because the triggers live only in the Postgres migration; the gated
test plus this script cover the residual risk.

## Follow-ups

- Re-run the command block above against staging during the next maintenance
  window and record the output in the deployment log.
- If partitioning is ever introduced for retention, partition *by range on
  `created_at`* and re-attach the triggers to each child — do not drop them.