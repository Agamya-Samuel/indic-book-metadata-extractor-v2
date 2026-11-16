"""Add the singleton system_settings row for maintenance mode.

Revision ID: 019
Revises: 018
Create Date: 2026-11-16

Maintenance mode is a single application-wide switch. A one-row table keeps the
state durable across restarts and records who last changed it; the API also
mirrors it into Redis so request checks and other processes see it quickly.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("maintenance_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("maintenance_message", sa.Text(), nullable=True),
        sa.Column("maintenance_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute("INSERT INTO system_settings (id, maintenance_enabled) VALUES (1, false)")


def downgrade() -> None:
    op.drop_table("system_settings")
