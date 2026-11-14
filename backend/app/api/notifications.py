"""In-app notifications and the email-notification preference."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationPreferences,
    NotificationRow,
    UnreadCountResponse,
)
from app.services import notification_service

router = APIRouter()


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    unread_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    filters = [Notification.user_id == user.id]
    if unread_only:
        filters.append(Notification.read_at.is_(None))

    total = int(await db.scalar(select(func.count(Notification.id)).where(*filters)) or 0)
    rows = (
        (
            await db.execute(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return NotificationListResponse.create(
        items=[NotificationRow.model_validate(row, from_attributes=True) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        unread_count=await notification_service.unread_count(db, user.id),
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    return UnreadCountResponse(count=await notification_service.unread_count(db, user.id))


@router.post("/{notification_id}/read", response_model=NotificationRow)
async def mark_notification_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationRow:
    notification = await notification_service.mark_read(db, user.id, notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationRow.model_validate(notification, from_attributes=True)


@router.post("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    updated = await notification_service.mark_all_read(db, user.id)
    return MarkAllReadResponse(updated=updated)


@router.get("/preferences", response_model=NotificationPreferences)
async def get_preferences(
    user: User = Depends(get_current_user),
) -> NotificationPreferences:
    return NotificationPreferences(email_enabled=user.email_notifications_enabled)


@router.patch("/preferences", response_model=NotificationPreferences)
async def update_preferences(
    payload: NotificationPreferences,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferences:
    updated = await notification_service.set_email_preference(db, user, payload.email_enabled)
    return NotificationPreferences(email_enabled=updated.email_notifications_enabled)
