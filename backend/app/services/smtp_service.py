"""Runtime SMTP configuration with env fallback.

The database row is the source of truth when a host is configured. When it is
empty (fresh deploy), the environment settings are used, so existing env-based
deployments keep working until an administrator saves settings here.

Reads are cached in-process for a short window; writes invalidate the cache.
The password is Fernet-encrypted at rest (see ``core.secret_box``) and never
returned by the admin API.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secret_box
from app.core.config import settings
from app.models.smtp_setting import SINGLETON_ID, SmtpSetting
from app.models.user import User

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 10.0


@dataclass(frozen=True)
class SmtpConfig:
    enabled: bool
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool
    use_starttls: bool
    timeout: int

    @property
    def from_address(self) -> str:
        return self.from_email or self.username

    @property
    def display_from(self) -> str:
        if self.from_name and self.from_address:
            return f"{self.from_name} <{self.from_address}>"
        return self.from_address


# Cache holds only a DB-derived config; the env fallback is read live so test
# monkeypatching and config changes are always reflected.
_cache: SmtpConfig | None = None
_cache_at: float = 0.0


def reset_cache() -> None:
    global _cache, _cache_at
    _cache = None
    _cache_at = 0.0


def from_settings() -> SmtpConfig:
    return SmtpConfig(
        enabled=settings.smtp_enabled,
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_email=settings.smtp_from,
        from_name="",
        use_tls=settings.smtp_use_tls,
        use_starttls=settings.smtp_starttls,
        timeout=settings.smtp_timeout,
    )


def _from_row(row: SmtpSetting) -> SmtpConfig:
    password = ""
    if row.password_encrypted:
        try:
            password = secret_box.decrypt(row.password_encrypted)
        except secret_box.SecretBoxError:
            logger.error("Could not decrypt stored SMTP password")
    return SmtpConfig(
        enabled=bool(row.enabled),
        host=row.host or "",
        port=row.port,
        username=row.username or "",
        password=password,
        from_email=row.from_email or "",
        from_name=row.from_name or "",
        use_tls=bool(row.use_tls),
        use_starttls=bool(row.use_starttls),
        timeout=settings.smtp_timeout,
    )


async def get_effective_config(db: AsyncSession) -> SmtpConfig:
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and (now - _cache_at) < CACHE_TTL_SECONDS:
        return _cache

    row = await db.get(SmtpSetting, SINGLETON_ID)
    if row is not None and (row.host or "").strip():
        config = _from_row(row)
        _cache = config
        _cache_at = now
        return config

    # No DB config yet: fall back to env, uncached.
    return from_settings()


async def _get_or_create(db: AsyncSession) -> SmtpSetting:
    row = await db.get(SmtpSetting, SINGLETON_ID)
    if row is None:
        row = SmtpSetting(id=SINGLETON_ID)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _masked(row: SmtpSetting) -> dict:
    from_settings_flag = not (row.host and row.host.strip())
    config = from_settings() if from_settings_flag else _from_row(row)
    return {
        "enabled": config.enabled,
        "host": config.host,
        "port": config.port,
        "username": config.username,
        "password_set": bool(row.password_encrypted) if not from_settings_flag else bool(settings.smtp_password),
        "from_email": config.from_email,
        "from_name": config.from_name,
        "use_tls": config.use_tls,
        "use_starttls": config.use_starttls,
        "source": "env" if from_settings_flag else "db",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": None,
    }


async def get_admin_config(db: AsyncSession) -> dict:
    row = await _get_or_create(db)
    data = _masked(row)
    if row.updated_by_id:
        user = await db.get(User, row.updated_by_id)
        data["updated_by"] = user.display_name if user is not None else None
    return data


async def update_admin_config(
    db: AsyncSession,
    *,
    updated_by_id: uuid.UUID,
    enabled: bool | None = None,
    host: str | None = None,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    use_tls: bool | None = None,
    use_starttls: bool | None = None,
) -> SmtpSetting:
    global _cache
    row = await _get_or_create(db)

    if enabled is not None:
        row.enabled = enabled
    if host is not None:
        row.host = host.strip() or None
    if port is not None:
        if not (1 <= port <= 65535):
            from app.services.auth_service import AuthError

            raise AuthError("Port must be between 1 and 65535", 400, "invalid_port")
        row.port = port
    if username is not None:
        row.username = username.strip() or None
    if password is not None and password != "":
        row.password_encrypted = secret_box.encrypt(password)
    if from_email is not None:
        row.from_email = from_email.strip() or None
    if from_name is not None:
        row.from_name = from_name.strip() or None
    if use_tls is not None:
        row.use_tls = use_tls
    if use_starttls is not None:
        row.use_starttls = use_starttls

    row.updated_by_id = updated_by_id
    await db.commit()
    await db.refresh(row)

    _cache = None
    return row


async def test_config(
    db: AsyncSession,
    *,
    to_email: str | None = None,
    override: SmtpConfig | None = None,
) -> dict:
    """Attempt an SMTP connection (and optional test send) and report the result.

    ``override`` lets an administrator test values that are not yet saved. The
    returned ``detail`` is a short human-readable message, never a stack trace.
    """
    config = override if override is not None else await get_effective_config(db)

    if not config.enabled:
        # Testing an unsaved/disabled form still attempts the connection; the
        # enabled flag only gates real sends.
        pass
    if not config.host:
        return {"ok": False, "detail": "No SMTP host configured"}
    if not (1 <= config.port <= 65535):
        return {"ok": False, "detail": "Invalid SMTP port"}
    if not config.from_address:
        return {"ok": False, "detail": "No sender email address configured"}

    try:
        if to_email:
            message = EmailMessage()
            message["From"] = config.display_from or config.from_address
            message["To"] = to_email
            message["Subject"] = "Open Book Map SMTP test"
            message.set_content(
                "This is a test message from Open Book Map to confirm your SMTP settings work.\n"
            )
            await aiosmtplib.send(
                message,
                hostname=config.host,
                port=config.port,
                username=config.username or None,
                password=config.password or None,
                start_tls=config.use_starttls,
                use_tls=config.use_tls,
                timeout=config.timeout,
            )
            return {"ok": True, "detail": f"Test email sent to {to_email}"}

        smtp = aiosmtplib.SMTP(
            hostname=config.host,
            port=config.port,
            use_tls=config.use_tls,
            timeout=config.timeout,
        )
        await smtp.connect()
        try:
            if config.use_starttls and not config.use_tls:
                await smtp.starttls()
            if config.username:
                await smtp.login(config.username, config.password or "")
        finally:
            try:
                await smtp.quit()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "detail": "Connected and authenticated successfully"}
    except Exception as exc:  # noqa: BLE001
        message = str(exc).strip() or exc.__class__.__name__
        logger.warning("SMTP test failed: %s", message)
        return {"ok": False, "detail": message[:500]}


def config_from_request(
    *,
    enabled: bool | None,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,
    from_email: str | None,
    from_name: str | None,
    use_tls: bool | None,
    use_starttls: bool | None,
    base: SmtpConfig | None = None,
) -> SmtpConfig:
    """Build a config from admin form values for an unsaved test.

    Fields left ``None`` are inherited from ``base`` (the effective config), so
    a partial form can be tested without resending everything.
    """
    base = base or from_settings()
    return SmtpConfig(
        enabled=base.enabled if enabled is None else enabled,
        host=(base.host if host is None else (host.strip() or "")),
        port=base.port if port is None else port,
        username=(base.username if username is None else (username.strip() or "")),
        password=(base.password if password is None else password),
        from_email=(base.from_email if from_email is None else (from_email.strip() or "")),
        from_name=(base.from_name if from_name is None else (from_name.strip() or "")),
        use_tls=base.use_tls if use_tls is None else use_tls,
        use_starttls=base.use_starttls if use_starttls is None else use_starttls,
        timeout=base.timeout,
    )


__all__ = [
    "SmtpConfig",
    "config_from_request",
    "from_settings",
    "get_admin_config",
    "get_effective_config",
    "reset_cache",
    "test_config",
    "update_admin_config",
]