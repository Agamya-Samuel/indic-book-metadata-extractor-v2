"""Relay host-watchdog failures (set in Redis by infra/host-watchdog.sh) to admins.

The watchdog itself cannot create in-app notifications: it runs as a systemd
timer outside the app. It publishes a short-lived key instead, and this loop —
started from the backend's lifespan alongside the job reaper — turns any such
key into an admin notification with the watchdog's one-line reason. The key
carries a TTL (watchdog sets 24 h), so a failure cannot notify twice.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.models.notification import NotificationType
from app.models.user import User, UserRole
from app.services import notification_service

logger = logging.getLogger(__name__)

WATCHDOG_FAIL_KEY_PREFIX = "watchdog:fail:"
WATCHDOG_POLL_SECONDS = 60

MESSAGE_BY_KEY = {
    "host-watchdog": "Host watchdog: {reason}",
}


async def _notify_admins(db, title: str, body: str, event_key: str) -> list[uuid.UUID]:
    admin_ids = (
        (
            await db.execute(
                select(User.id).where(
                    User.role == UserRole.ADMIN,
                    User.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    ids: list[uuid.UUID] = []
    for admin_id in admin_ids:
        created = await notification_service.create_notification(
            db,
            user_id=admin_id,
            type=NotificationType.PENDING_REGISTRATION,
            title=title[:200],
            body=body[:1000],
            event_key=event_key,
            link_url="/admin/dashboard",
        )
        if created is not None:
            ids.append(created)
    return ids


async def poll_and_notify(redis, db_factory) -> int:
    """Scan watchdog keys, notify admins once per key, delete them."""
    notified = 0
    keys = await redis.keys(f"{WATCHDOG_FAIL_KEY_PREFIX}*")
    for raw_key in keys:
        key = raw_key if isinstance(raw_key, str) else raw_key.decode()
        reason = await redis.get(key)
        reason = (reason if isinstance(reason, str) else reason.decode()) if reason else "unknown reason"
        short = key[len(WATCHDOG_FAIL_KEY_PREFIX):]
        try:
            async with db_factory() as db:
                ids = await _notify_admins(
                    db,
                    title="Host watchdog alert",
                    body=MESSAGE_BY_KEY.get(short, "Host watchdog: {reason}").format(reason=reason),
                    event_key=f"host-watchdog:{short}",
                )
                await notification_service.notify_and_deliver(db, ids)
        except Exception:  # noqa: BLE001
            logger.exception("Could not notify admins about watchdog key %s", key)
            continue
        await redis.delete(key)
        notified += 1
    return notified


async def watchdog_relay_loop(redis, db_factory) -> None:
    """Poll forever; exits cleanly on cancellation."""
    while True:
        try:
            count = await poll_and_notify(redis, db_factory)
            if count:
                logger.info("Watchdog relay: notified admins of %d failure(s)", count)
        except Exception:  # noqa: BLE001
            logger.exception("Watchdog relay poll failed")
        await asyncio.sleep(WATCHDOG_POLL_SECONDS)