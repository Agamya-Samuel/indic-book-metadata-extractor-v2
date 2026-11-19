"""Watchdog relay: a Redis failure key becomes one admin notification."""

from __future__ import annotations

import uuid

from app.models.notification import Notification
from app.models.user import AccountStatus, User, UserRole
from app.services import watchdog_service


class _FakeRedis:
    def __init__(self, data: dict[str, str]) -> None:
        self.data = dict(data)
        self.deleted: list[str] = []

    async def keys(self, pattern: str):
        prefix = pattern.rstrip("*")
        return [k for k in self.data if k.startswith(prefix)]

    async def get(self, key: str):
        return self.data.get(key)

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.deleted.append(key)


class _FakeSessionFactory:
    """Mimics async_session_factory(): call returns an async context manager."""

    def __init__(self, session) -> None:
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


async def _admin(db_session) -> User:
    user = User(
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        display_name="Watchdog Admin",
        password_hash="x",
        role=UserRole.ADMIN,
        account_status=AccountStatus.APPROVED,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def test_relay_notifies_admins_once(db_session) -> None:
    admin = await _admin(db_session)
    redis = _FakeRedis({"watchdog:fail:host-watchdog": "container 'worker' is not running"})

    db_factory = _FakeSessionFactory(db_session)

    count = await watchdog_service.poll_and_notify(redis, db_factory)

    assert count == 1
    rows = (
        await db_session.execute(Notification.__table__.select().where(Notification.user_id == admin.id))
    ).all()
    assert len(rows) == 1
    assert rows[0].title == "Host watchdog alert"
    assert "container 'worker' is not running" in rows[0].body
    assert redis.deleted == ["watchdog:fail:host-watchdog"]


async def test_relay_no_keys_is_a_no_op(db_session) -> None:
    redis = _FakeRedis({})

    db_factory = _FakeSessionFactory(db_session)

    assert await watchdog_service.poll_and_notify(redis, db_factory) == 0