"""Transactional email delivery for verification and password reset.

SMTP settings come from the runtime config service (``smtp_service``): the
admin-set database row when present, otherwise the environment. The password
is resolved there and never logged here.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.models.user import User
from app.services.smtp_service import SmtpConfig, from_settings

logger = logging.getLogger(__name__)


def _resolve(config: SmtpConfig | None) -> SmtpConfig:
    return config if config is not None else from_settings()


async def send_email(
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
    config: SmtpConfig | None = None,
) -> bool:
    """Send an email, or log it when SMTP is disabled (local development)."""
    cfg = _resolve(config)

    if not cfg.enabled:
        logger.warning(
            "SMTP disabled; email to %s with subject %r was not sent.\n%s",
            to,
            subject,
            text_body,
        )
        return False

    if not cfg.host or not cfg.from_address:
        logger.error("SMTP is enabled but host/from address are not configured")
        return False

    message = EmailMessage()
    message["From"] = cfg.display_from or cfg.from_address
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=cfg.host,
            port=cfg.port,
            username=cfg.username or None,
            password=cfg.password or None,
            start_tls=cfg.use_starttls,
            use_tls=cfg.use_tls,
            timeout=cfg.timeout,
        )
        logger.info("Sent %r email to %s", subject, to)
        return True
    except Exception:
        logger.exception("Failed to send %r email to %s", subject, to)
        return False


def _frontend_link(path: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?token={token}"


async def send_verification_email(user: User, token: str, *, config: SmtpConfig | None = None) -> bool:
    link = _frontend_link("/verify-email", token)
    text = (
        f"Hello {user.display_name},\n\n"
        "Confirm your email address to activate your Open Book Map account:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not create this account, you can ignore this message.\n"
    )
    html = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Confirm your email address to activate your Open Book Map account:</p>"
        f'<p><a href="{link}">Verify email</a></p>'
        f"<p>This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not create this account, you can ignore this message.</p>"
    )
    return await send_email(
        to=user.email,
        subject="Verify your Open Book Map email",
        text_body=text,
        html_body=html,
        config=config,
    )


async def send_password_reset_email(user: User, token: str, *, config: SmtpConfig | None = None) -> bool:
    link = _frontend_link("/reset-password", token)
    text = (
        f"Hello {user.display_name},\n\n"
        "Use this link to reset your Open Book Map password:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.password_reset_expire_minutes} minutes. "
        "If you did not request a reset, you can ignore this message.\n"
    )
    html = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Use this link to reset your Open Book Map password:</p>"
        f'<p><a href="{link}">Reset password</a></p>'
        f"<p>This link expires in {settings.password_reset_expire_minutes} minutes. "
        "If you did not request a reset, you can ignore this message.</p>"
    )
    return await send_email(
        to=user.email,
        subject="Reset your Open Book Map password",
        text_body=text,
        html_body=html,
        config=config,
    )


async def send_email_change_email(
    user: User,
    new_email: str,
    token: str,
    *,
    config: SmtpConfig | None = None,
) -> bool:
    link = _frontend_link("/verify-email", token) + "&type=new-email"
    text = (
        f"Hello {user.display_name},\n\n"
        "Confirm this address to change your Open Book Map account email:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not request this change, you can ignore this message and your "
        "current email address will stay active.\n"
    )
    html = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Confirm this address to change your Open Book Map account email:</p>"
        f'<p><a href="{link}">Confirm new email</a></p>'
        f"<p>This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not request this change, you can ignore this message and your "
        "current email address will stay active.</p>"
    )
    return await send_email(
        to=new_email,
        subject="Confirm your new Open Book Map email",
        text_body=text,
        html_body=html,
        config=config,
    )
