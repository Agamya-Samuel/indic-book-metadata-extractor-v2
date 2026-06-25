"""Add pg_trgm trigram indexes for search performance

Revision ID: 006
Revises: 005
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    # autocommit_block() commits the current tx, runs statements with
    # AUTOCOMMIT isolation, then starts a fresh tx.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_books_title_trgm "
            "ON books USING gin (title gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_books_filename_trgm "
            "ON books USING gin (filename gin_trgm_ops)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_metadata_fields_gin "
            "ON metadata USING gin (fields jsonb_path_ops)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_books_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_books_filename_trgm")
    op.execute("DROP INDEX IF EXISTS ix_metadata_fields_gin")
