"""Schemas for the administrator audit log."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel

from app.schemas.common import Page


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    actor_type: str
    actor_user_id: uuid.UUID | None = None
    actor_role: str | None = None
    actor_email: str | None = None
    actor_display_name: str | None = None
    action: str
    category: str
    description: str
    resource_type: str | None = None
    resource_id: str | None = None
    resource_label: str | None = None
    subject_user_id: uuid.UUID | None = None
    result: str
    error_message: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    details: dict | None = None
    truncated: bool = False

    model_config = {"from_attributes": True}


class AuditLogListResponse(Page[AuditLogResponse]):
    pass


class AuditActionInfo(BaseModel):
    value: str
    category: str
    label: str
    critical: bool = False
