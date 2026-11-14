"""API tests for /api/notifications: list, read state, and preferences."""

from __future__ import annotations

import uuid

from app.models.notification import Notification, NotificationType


async def _seed(db_session, user_id, count: int = 2) -> list[Notification]:
    rows = []
    for index in range(count):
        row = Notification(
            user_id=user_id,
            type=NotificationType.JOB_COMPLETED,
            title=f"Notification {index}",
            body="Body",
            event_key=f"job:{uuid.uuid4()}:completed",
            link_url="/dashboard",
        )
        db_session.add(row)
        rows.append(row)
    await db_session.commit()
    return rows


async def test_list_returns_only_own_notifications(client, regular_user, admin_user, db_session) -> None:
    mine = await _seed(db_session, regular_user.id, count=2)
    await _seed(db_session, admin_user.id, count=3)

    response = await client.get("/api/notifications")
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 2
    assert body["unread_count"] == 2
    assert {row["id"] for row in body["items"]} == {str(row.id) for row in mine}


async def test_pagination_and_unread_filter(client, regular_user, db_session) -> None:
    rows = await _seed(db_session, regular_user.id, count=5)

    first = await client.get("/api/notifications", params={"page": 1, "page_size": 2})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["total_pages"] == 3

    # Mark one read, then ask for unread only.
    await client.post(f"/api/notifications/{rows[0].id}/read")
    unread = await client.get("/api/notifications", params={"unread_only": "true", "page_size": 100})
    assert unread.json()["total"] == 4
    assert str(rows[0].id) not in {row["id"] for row in unread.json()["items"]}


async def test_read_and_read_all(client, regular_user, db_session) -> None:
    rows = await _seed(db_session, regular_user.id, count=3)

    read = await client.post(f"/api/notifications/{rows[0].id}/read")
    assert read.status_code == 200
    assert read.json()["read_at"] is not None

    count = await client.get("/api/notifications/unread-count")
    assert count.json()["count"] == 2

    all_read = await client.post("/api/notifications/read-all")
    assert all_read.status_code == 200
    assert all_read.json()["updated"] == 2
    assert (await client.get("/api/notifications/unread-count")).json()["count"] == 0


async def test_cannot_read_another_users_notification(client, admin_user, db_session) -> None:
    theirs = await _seed(db_session, admin_user.id, count=1)

    response = await client.post(f"/api/notifications/{theirs[0].id}/read")
    assert response.status_code == 404


async def test_preferences_round_trip(client, regular_user) -> None:
    initial = await client.get("/api/notifications/preferences")
    assert initial.status_code == 200
    assert initial.json()["email_enabled"] is True

    updated = await client.patch("/api/notifications/preferences", json={"email_enabled": False})
    assert updated.status_code == 200
    assert updated.json()["email_enabled"] is False

    again = await client.get("/api/notifications/preferences")
    assert again.json()["email_enabled"] is False


async def test_in_app_notifications_survive_preference_off(client, regular_user, db_session) -> None:
    await client.patch("/api/notifications/preferences", json={"email_enabled": False})
    await _seed(db_session, regular_user.id, count=1)

    response = await client.get("/api/notifications")
    assert response.status_code == 200
    assert response.json()["total"] == 1
