"""Maintenance state: persistence, expiry, and cache refresh."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.system_setting import SystemSetting
from app.models.user import AccountStatus, User
from app.services import maintenance_service as ms


@pytest.fixture(autouse=True)
def _reset_state():
    ms.set_state_for_test({"enabled": False})
    yield
    ms.set_state_for_test({"enabled": False})


async def test_enable_and_disable_persists(db_session) -> None:
    await ms.set_maintenance(db_session, enabled=True, message="Upgrading", until=None, updated_by_id=None)

    assert ms.get_state()["enabled"] is True
    assert ms.get_state()["message"] == "Upgrading"
    row = await db_session.get(SystemSetting, 1)
    assert row is not None
    assert row.maintenance_enabled is True

    await ms.set_maintenance(db_session, enabled=False, message=None, until=None, updated_by_id=None)
    assert ms.get_state()["enabled"] is False
    await db_session.refresh(row)
    assert row.maintenance_enabled is False


async def test_blank_message_falls_back_to_default(db_session) -> None:
    await ms.set_maintenance(db_session, enabled=True, message="   ", until=None, updated_by_id=None)
    assert ms.get_state()["message"] == ms.DEFAULT_MESSAGE


async def test_past_until_reads_as_disabled(db_session) -> None:
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    await ms.set_maintenance(db_session, enabled=True, message=None, until=past, updated_by_id=None)
    assert ms.get_state()["enabled"] is False


async def test_future_until_reads_as_enabled(db_session) -> None:
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await ms.set_maintenance(db_session, enabled=True, message=None, until=future, updated_by_id=None)
    assert ms.get_state()["enabled"] is True


async def test_refresh_reads_database_when_no_redis(db_session) -> None:
    await ms.set_maintenance(db_session, enabled=True, message="DB truth", until=None, updated_by_id=None)
    ms.set_state_for_test({"enabled": False})

    await ms.refresh_state(db_session, None)

    assert ms.get_state()["enabled"] is True
    assert ms.get_state()["message"] == "DB truth"


async def test_admin_status_includes_updater(db_session) -> None:
    admin = User(
        id=uuid.uuid4(),
        email="maintenance-admin@example.com",
        display_name="Maintenance Admin",
        password_hash="x",
        account_status=AccountStatus.APPROVED,
    )
    db_session.add(admin)
    await db_session.commit()

    await ms.set_maintenance(db_session, enabled=True, message="Patch", until=None, updated_by_id=admin.id)
    status = await ms.get_admin_status(db_session)

    assert status["enabled"] is True
    assert status["updated_by"] == "Maintenance Admin"
