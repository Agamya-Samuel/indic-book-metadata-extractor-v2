"""Add moderated signup: account approval state on users.

Revision ID: 013
Revises: 012
Create Date: 2026-11-12

Additive only; existing rows (including the bootstrap admin) are backfilled to
``approved`` via the column server default so no one is locked out by the new
gate.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(20),
            nullable=False,
            server_default="approved",
        ),
    )
    op.add_column(
        "users",
        sa.Column("status_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "status_reviewed_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "users",
        sa.Column("rejection_reason", sa.String(500), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_account_status",
        "users",
        "account_status IN ('pending','approved','rejected')",
    )
    op.create_index("ix_users_account_status", "users", ["account_status"])


def downgrade() -> None:
    op.drop_index("ix_users_account_status", table_name="users")
    op.drop_constraint("ck_users_account_status", "users", type_="check")
    op.drop_column("users", "rejection_reason")
    op.drop_column("users", "status_reviewed_by_id")
    op.drop_column("users", "status_reviewed_at")
    op.drop_column("users", "account_status")
