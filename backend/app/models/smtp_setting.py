"""Singleton runtime SMTP configuration set by administrators.

A one-row table keeps SMTP settings durable and editable at runtime without an
env change or redeploy. The password is stored Fernet-encrypted (``secrets``)
and never leaves the process in plaintext; the API only exposes whether one is
set. When this row has no host configured, the email service falls back to the
environment settings, so existing env-based deployments keep working.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Exactly one row exists; the primary key is pinned to this value.
SINGLETON_ID = 1


class SmtpSetting(Base):
    __tablename__ = "smtp_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    host: Mapped[str | None] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=587, server_default="587")
    username: Mapped[str | None] = mapped_column(String(255))
    password_encrypted: Mapped[str | None] = mapped_column(Text)
    from_email: Mapped[str | None] = mapped_column(String(320))
    from_name: Mapped[str | None] = mapped_column(String(255))
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    use_starttls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
