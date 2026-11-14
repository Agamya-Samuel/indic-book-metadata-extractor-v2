"""Moderated signup: approval gate, admin transitions, and access enforcement."""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.models.user import AccountStatus, User, UserRole
from app.services import auth_service

PASSWORD = "correct horse battery staple"


async def _register(anon_client, monkeypatch, email: str) -> None:
    async def fake_send(user, token):
        return True

    monkeypatch.setattr(auth_service, "send_verification_email", fake_send)
    response = await anon_client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "New User", "password": PASSWORD},
    )
    assert response.status_code == 201


async def _status_of(db_session, email: str) -> str:
    result = await db_session.execute(select(User).where(User.email == email))
    return result.scalar_one().account_status


async def test_register_starts_pending_when_approval_required(anon_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "registration_requires_approval", True)
    await _register(anon_client, monkeypatch, "pending.signup@example.com")
    assert await _status_of(db_session, "pending.signup@example.com") == AccountStatus.PENDING


async def test_register_is_auto_approved_when_approval_disabled(anon_client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "registration_requires_approval", False)
    await _register(anon_client, monkeypatch, "open.signup@example.com")
    assert await _status_of(db_session, "open.signup@example.com") == AccountStatus.APPROVED


async def test_pending_user_can_authenticate_but_not_use_the_app(pending_client, pending_user):
    assert (await pending_client.get("/api/auth/me")).status_code == 200

    blocked = await pending_client.get("/api/dashboard/summary")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "account_pending"


async def test_rejected_user_is_told_why_but_blocked_from_the_app(rejected_client, rejected_user):
    assert (await rejected_client.get("/api/auth/me")).status_code == 200

    blocked = await rejected_client.get("/api/dashboard/summary")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "account_rejected"


async def test_anonymous_access_is_denied_everywhere(anon_client):
    for path in (
        "/api/dashboard/summary",
        "/api/admin/books",
        "/api/admin/stats",
        "/api/bulk/stats",
    ):
        assert (await anon_client.get(path)).status_code == 401, path


async def test_admin_approve_grants_access(admin_client, admin_user, pending_client, pending_user):
    response = await admin_client.post(f"/api/admin/users/{pending_user.id}/approve")
    assert response.status_code == 200
    body = response.json()
    assert body["account_status"] == AccountStatus.APPROVED

    # Approving must not invalidate the pending user's existing session.
    assert (await pending_client.get("/api/dashboard/summary")).status_code == 200


async def test_admin_reject_records_reason_and_revokes_sessions(admin_client, admin_user, auth_client, create_user):
    target = await create_user(email="reject-me@example.com")
    target_client = await auth_client(target)
    assert (await target_client.get("/api/dashboard/summary")).status_code == 200

    response = await admin_client.post(
        f"/api/admin/users/{target.id}/reject",
        json={"rejection_reason": "Duplicate account"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["account_status"] == AccountStatus.REJECTED

    # Sessions are revoked, so the pre-existing access token is now invalid.
    assert (await target_client.get("/api/dashboard/summary")).status_code == 401

    # They can log back in (to see the holding screen) but the app stays closed.
    login = await target_client.post(
        "/api/auth/login",
        json={"email": "reject-me@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["account_status"] == AccountStatus.REJECTED
    blocked = await target_client.get("/api/dashboard/summary")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "account_rejected"


async def test_admin_cannot_reject_self(admin_client, admin_user):
    response = await admin_client.post(f"/api/admin/users/{admin_user.id}/reject", json={})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("You cannot")


async def test_pending_count_in_admin_stats(admin_client, create_user, regular_user):
    await create_user(email="p1@example.com", account_status=AccountStatus.PENDING)
    await create_user(email="p2@example.com", account_status=AccountStatus.PENDING)

    stats = await admin_client.get("/api/admin/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["pending_user_count"] == 2
    assert body["users"]["pending"] == 2


async def test_admin_user_list_filters_by_status(admin_client, create_user, regular_user):
    await create_user(email="p3@example.com", account_status=AccountStatus.PENDING)

    response = await admin_client.get("/api/admin/users?account_status=pending")
    assert response.status_code == 200
    emails = {item["email"] for item in response.json()["items"]}
    assert emails == {"p3@example.com"}


async def test_rejected_admin_is_blocked_from_the_admin_api(auth_client, create_user):
    rejected_admin = await create_user(
        email="rejected-admin@example.com",
        role=UserRole.ADMIN,
        account_status=AccountStatus.REJECTED,
    )
    client = await auth_client(rejected_admin)

    blocked = await client.get("/api/admin/stats")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "account_rejected"


async def test_patch_cannot_change_account_status(admin_client, create_user):
    target = await create_user(email="patch-status@example.com")

    response = await admin_client.patch(f"/api/admin/users/{target.id}", json={"account_status": "rejected"})
    assert response.status_code == 200
    assert response.json()["account_status"] == AccountStatus.APPROVED


async def test_admin_patch_self_does_not_lock_themselves_out(admin_client, admin_user):
    response = await admin_client.patch(f"/api/admin/users/{admin_user.id}", json={"account_status": "pending"})
    assert response.status_code == 200
    assert response.json()["account_status"] == AccountStatus.APPROVED


async def test_pending_count_endpoint(admin_client, create_user, regular_user):
    await create_user(email="pc1@example.com", account_status=AccountStatus.PENDING)
    await create_user(email="pc2@example.com", account_status=AccountStatus.PENDING)

    response = await admin_client.get("/api/admin/users/pending-count")
    assert response.status_code == 200
    assert response.json()["count"] == 2
