"""Integration tests for self-service account management and admin SMTP config."""

from __future__ import annotations

from app.core.config import settings
from app.models.user import User
from app.services import auth_service

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "an entirely different passphrase"


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


async def test_update_display_name(client, regular_user, db_session) -> None:
    response = await client.patch("/api/auth/me", json={"display_name": "Renamed Person"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Renamed Person"

    row = await db_session.get(User, regular_user.id)
    assert row is not None
    assert row.display_name == "Renamed Person"


async def test_new_user_email_notifications_default_off(create_user) -> None:
    user = await create_user(email="defaults@example.com")
    assert user.email_notifications_enabled is False


# ---------------------------------------------------------------------------
# Change email
# ---------------------------------------------------------------------------


async def test_change_email_verifies_new_address_first(client, anon_client, regular_user, monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_send(user, new_email, token, **kwargs):
        captured["new_email"] = new_email
        captured["token"] = token
        return True

    monkeypatch.setattr(auth_service, "send_email_change_email", fake_send)

    wrong = await client.post(
        "/api/auth/me/email",
        json={"current_password": "not-it", "new_email": "new.person@example.com"},
    )
    assert wrong.status_code == 400

    requested = await client.post(
        "/api/auth/me/email",
        json={"current_password": PASSWORD, "new_email": "New.Person@Example.com"},
    )
    assert requested.status_code == 202
    assert captured["new_email"] == "new.person@example.com"

    # The old address stays active until the new one is confirmed.
    me = await client.get("/api/auth/me")
    assert me.json()["email"] == regular_user.email

    confirmed = await anon_client.post("/api/auth/verify-new-email", json={"token": captured["token"]})
    assert confirmed.status_code == 200
    assert confirmed.json()["email"] == "new.person@example.com"

    # Email change revokes existing sessions.
    revoked = await client.get("/api/auth/me")
    assert revoked.status_code == 401

    # The new address can now sign in.
    login = await anon_client.post(
        "/api/auth/login",
        json={"email": "new.person@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200


async def test_change_email_rejects_taken_address(client, regular_user, create_user, monkeypatch) -> None:
    await create_user(email="taken@example.com")

    async def fake_send(user, new_email, token, **kwargs):  # pragma: no cover - should not be called
        raise AssertionError("verification email must not be sent for a taken address")

    monkeypatch.setattr(auth_service, "send_email_change_email", fake_send)

    response = await client.post(
        "/api/auth/me/email",
        json={"current_password": PASSWORD, "new_email": "taken@example.com"},
    )
    assert response.status_code == 409


async def test_change_email_rejects_same_address(client, regular_user) -> None:
    response = await client.post(
        "/api/auth/me/email",
        json={"current_password": PASSWORD, "new_email": regular_user.email},
    )
    assert response.status_code == 400


async def test_change_email_token_is_single_use(client, anon_client, regular_user, monkeypatch) -> None:
    captured: dict[str, str] = {}

    async def fake_send(user, new_email, token, **kwargs):
        captured["token"] = token
        return True

    monkeypatch.setattr(auth_service, "send_email_change_email", fake_send)
    await client.post(
        "/api/auth/me/email",
        json={"current_password": PASSWORD, "new_email": "single@example.com"},
    )

    first = await anon_client.post("/api/auth/verify-new-email", json={"token": captured["token"]})
    assert first.status_code == 200
    second = await anon_client.post("/api/auth/verify-new-email", json={"token": captured["token"]})
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# Admin SMTP configuration
# ---------------------------------------------------------------------------


async def test_smtp_get_defaults_to_env(admin_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_password", "")
    response = await admin_client.get("/api/admin/smtp")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "env"
    assert body["password_set"] is False
    assert "password" not in body
    assert "password_encrypted" not in body


async def test_smtp_update_never_returns_password(admin_client) -> None:
    response = await admin_client.put(
        "/api/admin/smtp",
        json={
            "enabled": True,
            "host": "smtp.example.com",
            "port": 587,
            "username": "mailer",
            "password": "super-secret-value",
            "from_email": "noreply@example.com",
            "from_name": "Open Book Map",
            "use_tls": False,
            "use_starttls": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["password_set"] is True
    assert body["source"] == "db"
    assert "password" not in body
    assert "password_encrypted" not in body
    assert "super-secret-value" not in response.text

    fetched = await admin_client.get("/api/admin/smtp")
    assert fetched.status_code == 200
    assert fetched.json()["password_set"] is True
    assert "super-secret-value" not in fetched.text


async def test_smtp_requires_admin(client) -> None:
    response = await client.get("/api/admin/smtp")
    assert response.status_code == 403


async def test_smtp_test_reports_connection_failure(admin_client) -> None:
    response = await admin_client.post(
        "/api/admin/smtp/test",
        json={
            "config": {
                "enabled": True,
                "host": "127.0.0.1",
                "port": 1,
                "username": "",
                "from_email": "noreply@example.com",
                "use_tls": False,
                "use_starttls": False,
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["detail"]