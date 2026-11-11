"""Authentication flows: registration, verification, sessions, and passwords."""

from __future__ import annotations

from app.models.user import UserRole
from app.services import auth_service


PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "an entirely different passphrase"


async def test_register_requires_email_verification_and_sets_session(
    anon_client, monkeypatch
):
    captured: dict[str, str] = {}

    async def fake_send(user, token):
        captured["token"] = token
        captured["email"] = user.email
        return True

    monkeypatch.setattr(auth_service, "send_verification_email", fake_send)

    response = await anon_client.post(
        "/api/auth/register",
        json={
            "email": "New.User@Example.com",
            "display_name": "New User",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201
    assert captured["email"] == "new.user@example.com"

    # The account cannot log in before verification.
    login = await anon_client.post(
        "/api/auth/login",
        json={"email": "new.user@example.com", "password": PASSWORD},
    )
    assert login.status_code == 403
    assert "verify" in login.json()["detail"].lower()

    verified = await anon_client.post(
        "/api/auth/verify-email", json={"token": captured["token"]}
    )
    assert verified.status_code == 200
    assert verified.json()["role"] == UserRole.USER
    assert verified.cookies.get("access_token")
    assert verified.cookies.get("csrf_token")

    me = await anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "new.user@example.com"


async def test_login_logout_and_me(anon_client, create_user):
    await create_user(email="login@example.com", password=PASSWORD)

    login = await anon_client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    assert login.cookies.get("access_token")

    csrf = anon_client.cookies.get("csrf_token")
    anon_client.headers["X-CSRF-Token"] = csrf

    me = await anon_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["display_name"] == "Test User"

    logout = await anon_client.post("/api/auth/logout")
    assert logout.status_code == 204
    # Cookies are cleared, so the session is no longer usable.
    after = await anon_client.get("/api/auth/me")
    assert after.status_code == 401


async def test_login_rejects_bad_password(anon_client, create_user):
    await create_user(email="badpass@example.com", password=PASSWORD)
    response = await anon_client.post(
        "/api/auth/login",
        json={"email": "badpass@example.com", "password": "wrong password"},
    )
    assert response.status_code == 401


async def test_inactive_user_cannot_login(anon_client, create_user):
    await create_user(
        email="inactive@example.com", password=PASSWORD, is_active=False
    )
    response = await anon_client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403


async def test_refresh_rotates_and_reuse_revokes_sessions(anon_client, create_user):
    await create_user(email="refresh@example.com", password=PASSWORD)
    login = await anon_client.post(
        "/api/auth/login",
        json={"email": "refresh@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    old_refresh = anon_client.cookies.get("refresh_token")

    refreshed = await anon_client.post("/api/auth/refresh")
    assert refreshed.status_code == 200
    new_refresh = anon_client.cookies.get("refresh_token")
    assert new_refresh and new_refresh != old_refresh

    # Replaying the superseded token invalidates the whole session family.
    anon_client.cookies.set("refresh_token", old_refresh)
    replay = await anon_client.post("/api/auth/refresh")
    assert replay.status_code == 401

    anon_client.cookies.set("refresh_token", new_refresh)
    after = await anon_client.post("/api/auth/refresh")
    assert after.status_code == 401


async def test_csrf_is_required_for_cookie_mutations(client):
    client.headers.pop("X-CSRF-Token", None)
    response = await client.post("/api/auth/logout")
    assert response.status_code == 403
    assert "csrf" in response.json()["detail"].lower()


async def test_forgot_and_reset_password(anon_client, create_user, monkeypatch):
    user = await create_user(email="reset@example.com", password=PASSWORD)
    captured: dict[str, str] = {}

    async def fake_send(target, token):
        captured["token"] = token
        return True

    monkeypatch.setattr(auth_service, "send_password_reset_email", fake_send)

    requested = await anon_client.post(
        "/api/auth/forgot-password", json={"email": user.email}
    )
    assert requested.status_code == 202
    assert captured["token"]

    reset = await anon_client.post(
        "/api/auth/reset-password",
        json={"token": captured["token"], "new_password": NEW_PASSWORD},
    )
    assert reset.status_code == 200

    old_login = await anon_client.post(
        "/api/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )
    assert old_login.status_code == 401

    new_login = await anon_client.post(
        "/api/auth/login",
        json={"email": user.email, "password": NEW_PASSWORD},
    )
    assert new_login.status_code == 200


async def test_email_token_is_single_use(anon_client, create_user, monkeypatch):
    captured: dict[str, str] = {}

    async def fake_send(user, token):
        captured["token"] = token
        return True

    monkeypatch.setattr(auth_service, "send_verification_email", fake_send)
    await create_user(email="once@example.com", verified=False)
    await anon_client.post(
        "/api/auth/resend-verification", json={"email": "once@example.com"}
    )

    first = await anon_client.post(
        "/api/auth/verify-email", json={"token": captured["token"]}
    )
    assert first.status_code == 200
    second = await anon_client.post(
        "/api/auth/verify-email", json={"token": captured["token"]}
    )
    assert second.status_code == 400


async def test_deactivation_revokes_existing_session(
    client, admin_client, regular_user
):
    # The regular user already has a live session via the `client` fixture.
    assert (await client.get("/api/auth/me")).status_code == 200
    response = await admin_client.patch(
        f"/api/admin/users/{regular_user.id}", json={"is_active": False}
    )
    assert response.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 401
