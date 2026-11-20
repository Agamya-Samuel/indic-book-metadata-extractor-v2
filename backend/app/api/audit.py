"""Administrator audit log: read-only, filterable, paginated.

There is deliberately no create, update, or delete route. Rows are written by
the services that perform the action, and the database rejects mutations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_context, require_admin
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit import AuditActionInfo, AuditLogListResponse, AuditLogResponse
from app.services import audit_service
from app.services.audit_service import (
    ACTION_SPECS,
    CRITICAL_ACTIONS,
    AuditAction,
    AuditContext,
)

router = APIRouter(dependencies=[Depends(require_admin)])

_SORT_COLUMNS = {
    "created_at": AuditLog.created_at,
    "action": AuditLog.action,
    "actor": func.coalesce(AuditLog.actor_display_name, AuditLog.actor_email, ""),
    "category": AuditLog.category,
    "result": AuditLog.result,
}


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _apply_filters(
    query,
    *,
    q: str | None,
    actor_user_id: UUID | None,
    actor_role: str | None,
    actor_type: str | None,
    action: str | None,
    category: str | None,
    resource_type: str | None,
    resource_id: str | None,
    result: str | None,
    exclude_meta: bool,
    date_from: datetime | None,
    date_to: datetime | None,
):
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                AuditLog.description.ilike(term),
                AuditLog.actor_email.ilike(term),
                AuditLog.actor_display_name.ilike(term),
                AuditLog.resource_label.ilike(term),
                AuditLog.action.ilike(term),
            )
        )
    if actor_user_id is not None:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if actor_role:
        query = query.where(AuditLog.actor_role == actor_role)
    if actor_type:
        query = query.where(AuditLog.actor_type == actor_type)
    if action:
        query = query.where(AuditLog.action == action)
    if category:
        query = query.where(AuditLog.category == category)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)
    if result:
        query = query.where(AuditLog.result == result)
    if exclude_meta:
        query = query.where(AuditLog.action != AuditAction.AUDIT_VIEWED.value)

    start = _as_aware(date_from)
    end = _as_aware(date_to)
    if start is not None:
        query = query.where(AuditLog.created_at >= start)
    if end is not None:
        query = query.where(AuditLog.created_at <= end)
    return query


# Declared before the ``/{log_id}`` route so the literal segment is not
# captured as a UUID path parameter.
@router.get("/actions", response_model=list[AuditActionInfo])
async def list_audit_actions() -> list[AuditActionInfo]:
    """The event catalogue, so the UI can label and group filters."""
    items = [
        AuditActionInfo(
            value=action.value,
            category=spec.category.value,
            label=spec.label,
            critical=action in CRITICAL_ACTIONS,
        )
        for action, spec in ACTION_SPECS.items()
    ]
    return sorted(items, key=lambda item: (item.category, item.label))


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    q: str | None = Query(default=None),
    actor_user_id: UUID | None = Query(default=None),
    actor_role: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    category: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    result: str | None = Query(default=None),
    exclude_meta: bool = Query(default=False),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    sort: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    ctx: AuditContext = Depends(get_audit_context),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    if sort not in _SORT_COLUMNS:
        raise HTTPException(status_code=422, detail=f"Unsupported sort column '{sort}'")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order must be 'asc' or 'desc'")

    filters = dict(
        q=q,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        actor_type=actor_type,
        action=action,
        category=category,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        exclude_meta=exclude_meta,
        date_from=date_from,
        date_to=date_to,
    )
    query = _apply_filters(select(AuditLog), **filters)
    total = int(await db.scalar(select(func.count()).select_from(query.subquery())) or 0)

    column = _SORT_COLUMNS[sort]
    direction = column.desc() if order == "desc" else column.asc()
    rows = (
        (
            await db.execute(
                query.order_by(direction, AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    # Access to the trail is itself an event. Recorded after the read so the
    # entry cannot shift the page the administrator just loaded.
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUDIT_VIEWED,
        ctx=ctx,
        description="Viewed the audit log",
        resource_type="audit_log",
        details={
            "filters": {key: str(value) for key, value in filters.items() if value is not None},
            "page": page,
            "page_size": page_size,
        },
    )

    return AuditLogListResponse.create(
        items=[AuditLogResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: UUID,
    ctx: AuditContext = Depends(get_audit_context),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    row = await db.get(AuditLog, log_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")

    await audit_service.record_isolated(
        db,
        action=AuditAction.AUDIT_VIEWED,
        ctx=ctx,
        description="Viewed an audit entry",
        resource_type="audit_log",
        resource_id=row.id,
    )
    return AuditLogResponse.model_validate(row)
