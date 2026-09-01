"""Change LlmRun.job_id ON DELETE to SET NULL to preserve audit rows.

Revision ID: 010
Revises: 009
Create Date: 2026-09-01

Deleting a book cascades to ``jobs`` (which uses SET NULL on
``book_id``) and CASCADEs to ``llm_runs``. The net effect is that
audit/research evidence stored in ``llm_runs.parsed_fields`` and
``metadata_field_evidence`` is wiped. Switching the FK to SET NULL
lets the parent cleanup proceed while keeping the LLM run rows for
later analysis.

Must be applied with care: existing data may already violate the new
constraint if there are dangling LlmRuns. Run with a fresh DB or
accept some noise on production upgrades.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop and re-create the FK with ON DELETE SET NULL.
    op.drop_constraint(
        "llm_runs_job_id_fkey",
        "llm_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "llm_runs_job_id_fkey",
        "llm_runs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # Allow job_id to be NULL.
    op.alter_column(
        "llm_runs",
        "job_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Re-create the CASCADE FK. Will fail if any LlmRun has a NULL job_id,
    # which is acceptable for downgrade.
    op.drop_constraint(
        "llm_runs_job_id_fkey",
        "llm_runs",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "llm_runs_job_id_fkey",
        "llm_runs",
        "jobs",
        ["job_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column(
        "llm_runs",
        "job_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
