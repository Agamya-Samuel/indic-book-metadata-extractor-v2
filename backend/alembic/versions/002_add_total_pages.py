"""Add total_pages column to books table

Revision ID: 002
Revises: 001
Create Date: 2026-05-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("books", sa.Column("total_pages", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("books", "total_pages")
