"""Add performance indexes for common queries

Revision ID: 005
Revises: 004
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_books_status ON books(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_books_language ON books(language)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_books_created_at ON books(created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_jobs_book_id_status ON jobs(book_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pages_book_id ON pages(book_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pages_book_id")
    op.execute("DROP INDEX IF EXISTS ix_jobs_book_id_status")
    op.execute("DROP INDEX IF EXISTS ix_jobs_status")
    op.execute("DROP INDEX IF EXISTS ix_books_created_at")
    op.execute("DROP INDEX IF EXISTS ix_books_language")
    op.execute("DROP INDEX IF EXISTS ix_books_status")
