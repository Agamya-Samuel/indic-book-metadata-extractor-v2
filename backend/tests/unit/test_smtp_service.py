"""Unit tests for runtime SMTP configuration resolution and masking."""

from __future__ import annotations

from app.core import secret_box
from app.core.config import settings
from app.models.smtp_setting import SINGLETON_ID, SmtpSetting
from app.models.user import UserRole
from app.services import smtp_service


def _seed_user(db_session, user_id_fixture=None):
    from app.models.user import User

    user = User(
        email="smtp-admin@example.com",
        display_name="SMTP Admin",
        password_hash="not-a-real-hash",
        role=UserRole.ADMIN,
    )
    return user


async def test_effective_config_falls_back_to_env(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.env.test")
    monkeypatch.setattr(settings, "smtp_port", 2525)
    monkeypatch.setattr(settings, "smtp_username", "envuser")
    monkeypatch.setattr(settings, "smtp_password", "envpass")
    monkeypatch.setattr(settings, "smtp_from", "env@example.com")
    monkeypatch.setattr(settings, "smtp_enabled", True)

    config = await smtp_service.get_effective_config(db_session)
    assert config.host == "smtp.env.test"
    assert config.port == 2525
    assert config.username == "envuser"
    assert config.password == "envpass"
    assert config.from_address == "env@example.com"
    assert config.enabled is True


async def test_db_config_overrides_env(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.env.test")
    db_session.add(
        SmtpSetting(
            id=SINGLETON_ID,
            enabled=True,
            host="db.smtp.test",
            port=587,
            username="dbuser",
            password_encrypted=secret_box.encrypt("dbpass"),
            from_email="db@example.com",
            from_name="DB Sender",
            use_tls=False,
            use_starttls=True,
        )
    )
    await db_session.commit()

    config = await smtp_service.get_effective_config(db_session)
    assert config.host == "db.smtp.test"
    assert config.password == "dbpass"
    assert config.from_name == "DB Sender"
    assert config.display_from == "DB Sender <db@example.com>"


async def test_admin_config_masks_password(db_session) -> None:
    db_session.add(
        SmtpSetting(
            id=SINGLETON_ID,
            enabled=True,
            host="db.smtp.test",
            port=587,
            username="dbuser",
            password_encrypted=secret_box.encrypt("dbpass"),
            from_email="db@example.com",
        )
    )
    await db_session.commit()

    data = await smtp_service.get_admin_config(db_session)
    assert data["password_set"] is True
    assert "password" not in data
    assert "password_encrypted" not in data
    assert data["source"] == "db"


async def test_update_admin_config_keeps_password_when_blank(db_session) -> None:
    admin = _seed_user(db_session)
    db_session.add(admin)
    await db_session.commit()

    await smtp_service.update_admin_config(
        db_session,
        updated_by_id=admin.id,
        host="db.smtp.test",
        port=587,
        username="dbuser",
        password="initial-secret",
        from_email="db@example.com",
        enabled=True,
    )
    # Blank password keeps the stored one.
    await smtp_service.update_admin_config(
        db_session,
        updated_by_id=admin.id,
        from_name="Renamed",
        password="",
    )

    config = await smtp_service.get_effective_config(db_session)
    assert config.password == "initial-secret"
    assert config.from_name == "Renamed"


async def test_config_from_request_inherits_base(monkeypatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "base.host")
    monkeypatch.setattr(settings, "smtp_from", "base@example.com")
    base = smtp_service.from_settings()

    override = smtp_service.config_from_request(
        enabled=True,
        host="override.host",
        port=None,
        username=None,
        password=None,
        from_email=None,
        from_name=None,
        use_tls=None,
        use_starttls=None,
        base=base,
    )
    assert override.host == "override.host"
    assert override.from_address == "base@example.com"