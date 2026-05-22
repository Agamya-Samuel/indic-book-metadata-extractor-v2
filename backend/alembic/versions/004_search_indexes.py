"""Add pg_trgm GIN indexes for library search

Revision ID: 004
Revises: 003
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_books_title_trgm ON books USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_books_filename_trgm ON books USING gin (filename gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_fields_gin ON metadata USING gin (fields)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_author_trgm ON metadata USING gin ((fields->>'author') gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_publisher_trgm ON metadata USING gin ((fields->>'publisher') gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_genre_trgm ON metadata USING gin ((fields->>'genre') gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_metadata_subject_trgm ON metadata USING gin ((fields->>'subject') gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_metadata_subject_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_genre_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_publisher_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_author_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_fields_gin")
    op.execute("DROP INDEX IF EXISTS ix_books_filename_trgm")
    op.execute("DROP INDEX IF EXISTS ix_books_title_trgm")
