"""Add metadata_field_evidence table for per-field provenance

Revision ID: 007
Revises: 006
Create Date: 2026-08-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metadata_field_evidence",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "book_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "source_page_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_page_number", sa.Integer(), nullable=True),
        sa.Column("source_text_snippet", sa.Text(), nullable=True),
        sa.Column("source_bbox", postgresql.JSONB(), nullable=True),
        sa.Column(
            "extraction_method",
            sa.String(32),
            nullable=False,
            server_default="llm",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_metadata_field_evidence_book_id",
        "metadata_field_evidence",
        ["book_id"],
    )
    op.create_index(
        "ix_metadata_field_evidence_book_field",
        "metadata_field_evidence",
        ["book_id", "field_name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_metadata_field_evidence_book_field", table_name="metadata_field_evidence")
    op.drop_index("ix_metadata_field_evidence_book_id", table_name="metadata_field_evidence")
    op.drop_table("metadata_field_evidence")
