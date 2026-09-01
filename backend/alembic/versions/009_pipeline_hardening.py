"""Pipeline hardening: evidence method column, page composite index, job celery_task_id

Revision ID: 009
Revises: 008
Create Date: 2026-09-01

This migration addresses three pipeline bugs:

1. ``metadata_field_evidence`` had a UNIQUE constraint on ``(book_id, field_name)``
   that silently prevented storing multiple competing evidence rows per field
   (regex vs. dictionary vs. LLM vs. human). The existing ``extraction_method``
   column is widened (still required) and the unique index now covers
   ``(book_id, field_name, extraction_method)``.

2. ``pages`` lacked a composite ``(book_id, page_number)`` index. The hot
   query path ``WHERE book_id = ? ORDER BY page_number`` forced a sort.
   This migration adds an index (non-unique, to avoid breaking historical
   data that may contain duplicates).

3. ``jobs`` lacked a ``celery_task_id`` column. The task_failure signal
   handler in ``app/tasks/celery_app.py`` needs to map a Celery task id
   back to a job row to mark it FAILED when the task crashes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the too-narrow UNIQUE constraint and re-create it with method.
    op.drop_index(
        "ix_metadata_field_evidence_book_field",
        table_name="metadata_field_evidence",
    )
    op.create_index(
        "ix_metadata_field_evidence_book_field_method",
        "metadata_field_evidence",
        ["book_id", "field_name", "extraction_method"],
        unique=True,
    )
    op.create_index(
        "ix_metadata_field_evidence_book_field",
        "metadata_field_evidence",
        ["book_id", "field_name"],
        unique=False,
    )

    # 2. Composite index on pages for the hot ``ORDER BY page_number`` path.
    op.create_index(
        "ix_pages_book_id_page_number",
        "pages",
        ["book_id", "page_number"],
        unique=False,
    )

    # 3. Celery task id on jobs. Nullable because jobs may exist before
    # they are dispatched (e.g. created during API request, then dispatched).
    op.add_column(
        "jobs",
        sa.Column("celery_task_id", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_jobs_celery_task_id",
        "jobs",
        ["celery_task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_celery_task_id", table_name="jobs")
    op.drop_column("jobs", "celery_task_id")

    op.drop_index("ix_pages_book_id_page_number", table_name="pages")

    op.drop_index(
        "ix_metadata_field_evidence_book_field",
        table_name="metadata_field_evidence",
    )
    op.drop_index(
        "ix_metadata_field_evidence_book_field_method",
        table_name="metadata_field_evidence",
    )
    op.create_index(
        "ix_metadata_field_evidence_book_field",
        "metadata_field_evidence",
        ["book_id", "field_name"],
        unique=True,
    )
