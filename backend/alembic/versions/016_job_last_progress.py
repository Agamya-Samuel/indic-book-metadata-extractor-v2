"""Track the last progress write on a job.

Revision ID: 016
Revises: 015
Create Date: 2026-11-14

The stale-job reaper compared ``started_at``, so a legitimate long extraction
was failed after 90 minutes even while it kept reporting progress. Record the
last progress timestamp and reap on that instead.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "last_progress_at")