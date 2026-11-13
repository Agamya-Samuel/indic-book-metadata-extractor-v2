"""Schemas for in-app notifications and the email preference."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel


class NotificationRow(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    link_url: str | None = None
    book_id: uuid.UUID | None = None
    read_at: datetime.datetime | None = None
    created_at: datetime.datetime | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationRow]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class UnreadCountResponse(BaseModel):
    count: int


class MarkAllReadResponse(BaseModel):
    updated: int


class NotificationPreferences(BaseModel):
    email_enabled: bool
