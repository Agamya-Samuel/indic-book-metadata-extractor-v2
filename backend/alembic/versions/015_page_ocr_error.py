"""Record per-page OCR failures so partial runs can advance.

Revision ID: 015
Revises: 014
Create Date: 2026-11-14

Additive only. A page whose OCR failed keeps an error message; the OCR stage
can then complete with failures visible instead of blocking the whole book.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pages", sa.Column("ocr_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("pages", "ocr_error")