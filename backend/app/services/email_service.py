"""Transactional email delivery for verification and password reset."""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


def _from_address() -> str:
    return settings.smtp_from or settings.smtp_username


async def send_email(
    *,
    to: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> bool:
    """Send an email, or log it when SMTP is disabled (local development)."""
    if not settings.smtp_enabled:
        logger.warning(
            "SMTP disabled; email to %s with subject %r was not sent.\n%s",
            to,
            subject,
            text_body,
        )
        return False

    if not settings.smtp_host or not _from_address():
        logger.error("SMTP is enabled but SMTP_HOST/SMTP_FROM are not configured")
        return False

    message = EmailMessage()
    message["From"] = _from_address()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_starttls,
            use_tls=settings.smtp_use_tls,
            timeout=settings.smtp_timeout,
        )
        logger.info("Sent %r email to %s", subject, to)
        return True
    except Exception:
        logger.exception("Failed to send %r email to %s", subject, to)
        return False


def _frontend_link(path: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?token={token}"


async def send_verification_email(user: User, token: str) -> bool:
    link = _frontend_link("/verify-email", token)
    text = (
        f"Hello {user.display_name},\n\n"
        "Confirm your email address to activate your Indic Books account:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not create this account, you can ignore this message.\n"
    )
    html = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Confirm your email address to activate your Indic Books account:</p>"
        f'<p><a href="{link}">Verify email</a></p>'
        f"<p>This link expires in {settings.email_verification_expire_hours} hours. "
        "If you did not create this account, you can ignore this message.</p>"
    )
    return await send_email(
        to=user.email,
        subject="Verify your Indic Books email",
        text_body=text,
        html_body=html,
    )


async def send_password_reset_email(user: User, token: str) -> bool:
    link = _frontend_link("/reset-password", token)
    text = (
        f"Hello {user.display_name},\n\n"
        "Use this link to reset your Indic Books password:\n\n"
        f"{link}\n\n"
        f"This link expires in {settings.password_reset_expire_minutes} minutes. "
        "If you did not request a reset, you can ignore this message.\n"
    )
    html = (
        f"<p>Hello {user.display_name},</p>"
        "<p>Use this link to reset your Indic Books password:</p>"
        f'<p><a href="{link}">Reset password</a></p>'
        f"<p>This link expires in {settings.password_reset_expire_minutes} minutes. "
        "If you did not request a reset, you can ignore this message.</p>"
    )
    return await send_email(
        to=user.email,
        subject="Reset your Indic Books password",
        text_body=text,
        html_body=html,
    )
