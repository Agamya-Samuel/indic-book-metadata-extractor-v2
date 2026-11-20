"""Application-wide maintenance switch.

The database row is the source of truth. The state is mirrored into Redis so
other processes and request checks see a toggle immediately, and an in-process
snapshot keeps the per-request middleware off the database. A small refresher
loop reconciles the snapshot with Redis (or the database when Redis is down).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SINGLETON_ID, SystemSetting
from app.models.user import User
from app.services import audit_service
from app.services.audit_service import AuditAction, AuditContext

logger = logging.getLogger(__name__)

CACHE_KEY = "system:maintenance"
CACHE_TTL_SECONDS = 3600
DEFAULT_MESSAGE = "The service is under maintenance. Please check back shortly."

_DEFAULT_STATE: dict = {
    "enabled": False,
    "message": None,
    "until": None,
    "updated_at": None,
    "updated_by": None,
}
_state: dict = dict(_DEFAULT_STATE)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return _as_aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _effective(enabled: bool, until: str | None) -> bool:
    if not enabled:
        return False
    deadline = _parse_iso(until)
    return True if deadline is None else deadline > datetime.now(timezone.utc)


def _serialize(row: SystemSetting) -> dict:
    return {
        "enabled": bool(row.maintenance_enabled),
        "message": row.maintenance_message,
        "until": row.maintenance_until.isoformat() if row.maintenance_until else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": None,
    }


def _set_state(data: dict) -> None:
    global _state
    _state = {
        "enabled": bool(data.get("enabled")),
        "message": data.get("message"),
        "until": data.get("until"),
        "updated_at": data.get("updated_at"),
        "updated_by": data.get("updated_by"),
    }


def set_state_for_test(data: dict) -> None:
    """Test hook: replace the in-process snapshot without touching the database."""
    _set_state({**_DEFAULT_STATE, **data})


def get_state() -> dict:
    """The effective state, with an expired `until` treated as disabled."""
    state = dict(_state)
    state["enabled"] = _effective(state["enabled"], state["until"])
    if state["enabled"] and not state["message"]:
        state["message"] = DEFAULT_MESSAGE
    return state


def get_public_state() -> dict:
    state = get_state()
    return {
        "enabled": state["enabled"],
        "message": state["message"],
        "until": state["until"],
    }


async def _get_or_create(db: AsyncSession) -> SystemSetting:
    row = await db.get(SystemSetting, SINGLETON_ID)
    if row is None:
        row = SystemSetting(id=SINGLETON_ID, maintenance_enabled=False)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def _write_cache(redis, data: dict) -> None:
    if redis is None:
        return
    try:
        await redis.set(CACHE_KEY, json.dumps(data), ex=CACHE_TTL_SECONDS)
    except Exception:  # noqa: BLE001
        logger.warning("Could not write maintenance state to Redis", exc_info=True)


async def refresh_state(db: AsyncSession, redis=None) -> dict:
    """Reconcile the in-process snapshot with Redis, falling back to the DB."""
    data = None
    if redis is not None:
        try:
            raw = await redis.get(CACHE_KEY)
            if raw:
                data = json.loads(raw)
        except Exception:  # noqa: BLE001
            logger.warning("Could not read maintenance state from Redis", exc_info=True)

    if data is None:
        row = await _get_or_create(db)
        data = _serialize(row)
        await _write_cache(redis, data)

    _set_state(data)
    return get_state()


async def get_admin_status(db: AsyncSession) -> dict:
    row = await _get_or_create(db)
    data = _serialize(row)
    if row.updated_by_id:
        user = await db.get(User, row.updated_by_id)
        data["updated_by"] = user.display_name if user is not None else None
    data["enabled"] = _effective(data["enabled"], data["until"])
    return data


async def set_maintenance(
    db: AsyncSession,
    *,
    enabled: bool,
    message: str | None,
    until: datetime | None,
    updated_by_id: UUID | None,
    redis=None,
    audit: AuditContext | None = None,
) -> dict:
    row = await _get_or_create(db)
    before = _maintenance_snapshot(row)
    row.maintenance_enabled = enabled
    row.maintenance_message = (message or "").strip() or None
    row.maintenance_until = None if not enabled else _as_aware(until)
    row.updated_by_id = updated_by_id
    after = _maintenance_snapshot(row)
    if audit is not None:
        changed_before, changed_after = audit_service.change_snapshots(before, after)
        if changed_before:
            # Critical: same transaction, so a failed insert blocks the change.
            await audit_service.record(
                db,
                action=AuditAction.CONFIG_MAINTENANCE_UPDATED,
                ctx=audit,
                description=("Enabled maintenance mode" if enabled else "Disabled maintenance mode"),
                resource_type="config",
                resource_id="maintenance",
                before=changed_before,
                after=changed_after,
            )
    await db.commit()
    await db.refresh(row)

    data = _serialize(row)
    await _write_cache(redis, data)
    _set_state(data)
    return data


def _maintenance_snapshot(row: SystemSetting) -> dict:
    return {
        "enabled": bool(row.maintenance_enabled),
        "message": row.maintenance_message,
        "until": row.maintenance_until.isoformat() if row.maintenance_until else None,
    }
