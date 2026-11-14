"""Add users, auth tokens, and book/job ownership.

Revision ID: 012
Revises: 011
Create Date: 2026-11-11

The deployment is expected to start from an empty database. Existing books
have no owner and cannot be attributed safely, so this migration refuses to
run while books exist rather than inventing an owner.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_check_constraint("ck_users_role", "users", "role IN ('user','admin')")
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "email_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_email_tokens_purpose",
        "email_tokens",
        "purpose IN ('verify_email','reset_password')",
    )
    op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    bind = op.get_bind()
    existing_books = bind.execute(sa.text("SELECT COUNT(*) FROM books")).scalar() or 0
    if existing_books:
        raise RuntimeError(
            "Migration 012 cannot assign owners to existing books. "
            "This deployment is expected to start with an empty books table. "
            "Delete existing books (and their storage) before running this migration."
        )

    op.add_column(
        "books",
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_books_owner_id",
        "books",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_books_owner_id", "books", ["owner_id"])
    op.execute("ALTER TABLE books ALTER COLUMN owner_id SET NOT NULL")

    op.add_column(
        "jobs",
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_jobs_requested_by_id",
        "jobs",
        "users",
        ["requested_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_jobs_requested_by_id", "jobs", ["requested_by_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_requested_by_id", table_name="jobs")
    op.drop_constraint("fk_jobs_requested_by_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "requested_by_id")

    op.drop_index("ix_books_owner_id", table_name="books")
    op.drop_constraint("fk_books_owner_id", "books", type_="foreignkey")
    op.drop_column("books", "owner_id")

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("ix_email_tokens_user_id", table_name="email_tokens")
    op.drop_constraint("ck_email_tokens_purpose", "email_tokens", type_="check")
    op.drop_table("email_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_table("users")
