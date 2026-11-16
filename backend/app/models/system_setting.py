"""Singleton application settings, including maintenance mode."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Exactly one row exists; the primary key is pinned to this value.
SINGLETON_ID = 1


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    maintenance_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    maintenance_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenance_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
