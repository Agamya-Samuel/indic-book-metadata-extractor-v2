"""Persist the OCR engine/route and script coverage per page.

Revision ID: 017
Revises: 016
Create Date: 2026-11-16

Language routing can change the engine mid-pipeline (line model -> Tesseract,
or `hin+eng` -> `hin`). Without recording the decision, the review UI and
incident audits cannot tell how a page was produced. These columns are
additive and nullable, so existing rows remain valid.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ocr_results", sa.Column("ocr_engine", sa.String(length=20), nullable=True))
    op.add_column("ocr_results", sa.Column("ocr_route", sa.String(length=50), nullable=True))
    op.add_column("ocr_results", sa.Column("ocr_coverage", sa.Float(), nullable=True))
    op.add_column("ocr_results", sa.Column("ocr_script", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("ocr_results", "ocr_script")
    op.drop_column("ocr_results", "ocr_coverage")
    op.drop_column("ocr_results", "ocr_route")
    op.drop_column("ocr_results", "ocr_engine")
