"""Add book_stage_status table and book_current_stage view.

Revision ID: 011
Revises: 010
Create Date: 2026-09-21

Tracks per-stage lifecycle (initiated → processing → completed / failed / cancelled)
with retry history via an `attempt` integer. The view `book_current_stage` exposes
the latest attempt per stage for easy querying.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "book_stage_status",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("book_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_name", sa.String(30), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_log", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_check_constraint("ck_stage_status", "book_stage_status", "status IN ('initiated','processing','completed','failed','cancelled')")
    op.create_check_constraint(
        "ck_stage_name",
        "book_stage_status",
        "stage_name IN ('upload','page_selection','ocr','llm_extraction','human_review','completion')",
    )

    op.create_index("ix_book_stage_status_book_id", "book_stage_status", ["book_id"])
    op.create_index("ix_book_stage_status_status", "book_stage_status", ["status"])
    op.create_unique_constraint("uq_book_stage_status_book_stage_attempt", "book_stage_status", ["book_id", "stage_name", "attempt"])

    op.execute("""
        CREATE VIEW book_current_stage AS
        SELECT bss.*
        FROM book_stage_status bss
        JOIN (
            SELECT book_id, stage_name, MAX(attempt) AS attempt
            FROM book_stage_status
            GROUP BY book_id, stage_name
        ) latest ON latest.book_id = bss.book_id
          AND latest.stage_name = bss.stage_name
          AND latest.attempt = bss.attempt
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS book_current_stage")
    op.drop_constraint("uq_book_stage_status_book_stage_attempt", "book_stage_status", type_="unique")
    op.drop_index("ix_book_stage_status_status", table_name="book_stage_status")
    op.drop_index("ix_book_stage_status_book_id", table_name="book_stage_status")
    op.drop_constraint("ck_stage_name", "book_stage_status", type_="check")
    op.drop_constraint("ck_stage_status", "book_stage_status", type_="check")
    op.drop_table("book_stage_status")
