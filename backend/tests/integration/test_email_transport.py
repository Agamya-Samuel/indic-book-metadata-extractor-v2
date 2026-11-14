"""End-to-end SMTP transport tests against a local in-process SMTP sink.

Production mail is not configured yet, so this is the only way to prove the
client half: real aiosmtplib conversation, real MIME message, real link. The
sink speaks just enough SMTP for aiosmtplib's plaintext send path (EHLO, MAIL,
RCPT, DATA, QUIT) and records the DATA payload.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from app.core.config import settings
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.services import notification_service
from app.services.email_service import send_email

EXPECTED_FROM = "noreply@test.local"


class _SMTPSink:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self._server: asyncio.AbstractServer | None = None
        self.port: int = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 test-smtp ready\r\n")
        await writer.drain()
        data_mode = False
        buffer = bytearray()
        while True:
            line = await reader.readline()
            if not line:
                break
            if data_mode:
                if line in (b".\r\n", b".\n"):
                    self.messages.append(buffer.decode("utf-8", "replace"))
                    buffer.clear()
                    data_mode = False
                    writer.write(b"250 OK\r\n")
                else:
                    buffer.extend(line)
                await writer.drain()
                continue

            command = line.strip().upper()
            if command.startswith(b"EHLO") or command.startswith(b"HELO"):
                writer.write(b"250-test-smtp\r\n250 HELP\r\n")
            elif command == b"DATA":
                writer.write(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                data_mode = True
            elif command == b"QUIT":
                writer.write(b"221 Bye\r\n")
                await writer.drain()
                break
            else:
                # MAIL FROM / RCPT TO / RSET / NOOP
                writer.write(b"250 OK\r\n")
            await writer.drain()
        writer.close()


@pytest.fixture
async def smtp_sink(monkeypatch):
    sink = _SMTPSink()
    await sink.start()
    monkeypatch.setattr(settings, "smtp_enabled", True)
    monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(settings, "smtp_port", sink.port)
    monkeypatch.setattr(settings, "smtp_username", "")
    monkeypatch.setattr(settings, "smtp_password", "")
    monkeypatch.setattr(settings, "smtp_from", EXPECTED_FROM)
    monkeypatch.setattr(settings, "smtp_starttls", False)
    monkeypatch.setattr(settings, "smtp_use_tls", False)
    monkeypatch.setattr(settings, "smtp_timeout", 10)
    try:
        yield sink
    finally:
        await sink.stop()


async def test_send_email_reaches_the_server(smtp_sink) -> None:
    ok = await send_email(
        to="recipient@example.com",
        subject="A subject line",
        text_body="Plain body",
        html_body="<p>Html body</p>",
    )

    assert ok is True
    assert len(smtp_sink.messages) == 1
    message = smtp_sink.messages[0]
    assert "To: recipient@example.com" in message
    assert f"From: {EXPECTED_FROM}" in message
    assert "Subject: A subject line" in message
    assert "Plain body" in message
    assert "<p>Html body</p>" in message


async def test_notification_email_carries_title_body_and_link(db_session, smtp_sink) -> None:
    user = User(
        email="notify@example.com",
        display_name="Notify Me",
        password_hash="not-a-real-hash",
        email_notifications_enabled=True,
    )
    db_session.add(user)
    await db_session.commit()

    notification = Notification(
        user_id=user.id,
        type=NotificationType.ACCOUNT_APPROVED,
        title="Your account is approved",
        body="An administrator approved your account.",
        link_url="/dashboard",
        event_key=f"account-approved:{uuid.uuid4()}",
    )
    db_session.add(notification)
    await db_session.commit()

    sent = await notification_service.deliver_emails_in_session(db_session, [notification.id])
    await db_session.commit()

    assert sent == 1
    assert (await db_session.get(Notification, notification.id)).emailed_at is not None
    assert len(smtp_sink.messages) == 1
    message = smtp_sink.messages[0]
    assert "Subject: Your account is approved" in message
    assert "An administrator approved your account." in message
    expected_link = f"{settings.frontend_url.rstrip('/')}/dashboard"
    assert expected_link in message


async def test_preference_off_sends_nothing(db_session, smtp_sink) -> None:
    user = User(
        email="quiet@example.com",
        display_name="Quiet",
        password_hash="not-a-real-hash",
        email_notifications_enabled=False,
    )
    db_session.add(user)
    await db_session.commit()

    notification = Notification(
        user_id=user.id,
        type=NotificationType.JOB_COMPLETED,
        title="OCR finished",
        body="Body",
        event_key=f"job:{uuid.uuid4()}:completed",
    )
    db_session.add(notification)
    await db_session.commit()

    sent = await notification_service.deliver_emails_in_session(db_session, [notification.id])
    await db_session.commit()

    assert sent == 0
    assert smtp_sink.messages == []
    assert (await db_session.get(Notification, notification.id)).emailed_at is None
