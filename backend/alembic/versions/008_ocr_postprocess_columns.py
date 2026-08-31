"""Add cleaned_text + corrections to ocr_results for Tier 5 post-processing

Revision ID: 008
Revises: 007
Create Date: 2026-08-31
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ocr_results",
        sa.Column("cleaned_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "ocr_results",
        sa.Column(
            "corrections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("ocr_results", "corrections")
    op.drop_column("ocr_results", "cleaned_text")