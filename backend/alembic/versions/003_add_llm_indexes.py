"""Add indexes for LLM extraction and job queries

Revision ID: 003
Revises: 002
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_book_type_status",
        "jobs",
        ["book_id", "job_type", "status"],
    )
    op.create_index("ix_jobs_job_type", "jobs", ["job_type"])
    op.create_index(
        "ix_metadata_book_id",
        "metadata",
        ["book_id"],
        unique=True,
    )
    op.create_index("ix_llm_runs_job_id", "llm_runs", ["job_id"])
    op.create_index(
        "ix_ocr_results_page_id",
        "ocr_results",
        ["page_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_ocr_results_page_id", table_name="ocr_results")
    op.drop_index("ix_llm_runs_job_id", table_name="llm_runs")
    op.drop_index("ix_metadata_book_id", table_name="metadata")
    op.drop_index("ix_jobs_job_type", table_name="jobs")
    op.drop_index("ix_jobs_book_type_status", table_name="jobs")
