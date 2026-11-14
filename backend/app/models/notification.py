"""Per-recipient in-app notifications, mirrored to email when allowed."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class NotificationType(StrEnum):
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    ACCOUNT_APPROVED = "account_approved"
    PENDING_REGISTRATION = "pending_registration"


class Notification(UUIDMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("user_id", "event_key", name="uq_notifications_user_event"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(1000), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500))
    book_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"))
    # Idempotency key: a redelivered Celery task must not create a second row.
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User")
    book = relationship("Book")
