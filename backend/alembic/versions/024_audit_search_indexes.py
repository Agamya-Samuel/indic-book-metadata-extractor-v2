"""Audit search coverage: trigram indexes for resource_label/action, actor sort index.

Revision ID: 024
Revises: 023
Create Date: 2026-11-20

Migration ``023`` created trigram GIN indexes for the audit search box on
``description``, ``actor_email`` and ``actor_display_name``, but the ``q``
predicate also ORs leading-wildcard ILIKE arms over ``resource_label`` and
``action`` — without matching trigram indexes the planner falls back to a
sequential scan for every search. The ``actor`` sort column is a
``coalesce(actor_display_name, actor_email, '')`` expression with no index;
this revision indexes the exact expression the API sorts by.

``audit_logs`` is a fresh table, so plain (non-concurrent) index creation is
instant; if this ever runs against a populated table, revisit with a
concurrent-index procedure.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_audit_logs_resource_label_trgm ON audit_logs USING gin (resource_label gin_trgm_ops)")
    op.execute("CREATE INDEX ix_audit_logs_action_trgm ON audit_logs USING gin (action gin_trgm_ops)")
    op.execute("CREATE INDEX ix_audit_logs_actor_sort ON audit_logs (coalesce(actor_display_name, actor_email, ''))")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_actor_sort")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_action_trgm")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_resource_label_trgm")
