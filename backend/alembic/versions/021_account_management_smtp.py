"""Account management + runtime SMTP settings.

Revision ID: 021
Revises: 020
Create Date: 2026-11-19

Three additive changes for the account-management work:

* ``users.email_notifications_enabled`` now defaults to **false** so email
  notifications are off by default for new users. Existing rows are untouched.
* ``email_tokens.pending_email`` holds the target address for the new
  ``verify_new_email`` token (change-email flow).
* ``smtp_settings`` is a one-row table holding admin-configured SMTP settings.
  The password is stored encrypted; this table overrides env vars when a host
  is set.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Email notifications OFF by default for new users (existing rows unchanged).
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "email_notifications_enabled",
            existing_type=sa.Boolean(),
            server_default=sa.false(),
            existing_nullable=False,
        )

    # Pending target address for the change-email verification token.
    op.add_column("email_tokens", sa.Column("pending_email", sa.String(length=320), nullable=True))

    # Singleton SMTP configuration.
    op.create_table(
        "smtp_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password_encrypted", sa.Text(), nullable=True),
        sa.Column("from_email", sa.String(length=320), nullable=True),
        sa.Column("from_name", sa.String(length=255), nullable=True),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_starttls", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.execute(
        "INSERT INTO smtp_settings (id, enabled, port, use_tls, use_starttls) VALUES (1, false, 587, false, true)"
    )


def downgrade() -> None:
    op.drop_table("smtp_settings")
    op.drop_column("email_tokens", "pending_email")
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "email_notifications_enabled",
            existing_type=sa.Boolean(),
            server_default=sa.true(),
            existing_nullable=False,
        )