"""Add composite indexes for admin queue aggregates.

Revision ID: 018
Revises: 017
Create Date: 2026-11-16

The admin queue view groups jobs by status/type and lists them ordered by
creation time. These composite indexes keep those reads cheap as the job
history grows, without changing any columns.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_status_created_at",
        "jobs",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_jobs_job_type_status",
        "jobs",
        ["job_type", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_job_type_status", table_name="jobs")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
