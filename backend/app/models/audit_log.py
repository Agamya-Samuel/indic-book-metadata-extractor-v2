"""Append-only audit trail of user, administrator, and system activity.

The table is deliberately denormalised and has **no foreign keys**. An audit
row must outlive the account or book it refers to, and an ``ON DELETE SET
NULL`` cascade would be an UPDATE — which the append-only trigger rejects.
Actor identity is snapshotted into each row instead.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_category_created", "category", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_subject_created", "subject_user_id", "created_at"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Who acted. ``system`` covers workers, the reaper, and the watchdog;
    # ``anonymous`` covers failed sign-ins and unauthenticated token links.
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False, default="system")
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    actor_role: Mapped[str | None] = mapped_column(String(20))
    # Snapshots so history stays readable after a rename or account deletion.
    actor_email: Mapped[str | None] = mapped_column(String(320))
    actor_display_name: Mapped[str | None] = mapped_column(String(120))

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # The affected object. ``resource_id`` is a string so it can hold a UUID,
    # a singleton config row id, or a Wikibase Q-id.
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    resource_label: Mapped[str | None] = mapped_column(String(500))
    # The person whose work was affected (e.g. the job requester), when that is
    # not the actor.
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(index=True)

    result: Mapped[str] = mapped_column(String(16), nullable=False, default=AuditResult.SUCCESS)
    error_message: Mapped[str | None] = mapped_column(String(1000))

    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[str | None] = mapped_column(String(64))

    # Column names avoid SQL keywords; the Python attributes are the API names.
    before: Mapped[dict | None] = mapped_column("before_values", JSONB)
    after: Mapped[dict | None] = mapped_column("after_values", JSONB)
    details: Mapped[dict | None] = mapped_column(JSONB)
    # True when a value was cut to fit the row (long OCR text, wide lists).
    truncated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
