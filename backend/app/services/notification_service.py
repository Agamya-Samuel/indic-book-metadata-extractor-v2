"""Creation and email delivery for in-app notifications.

One row per (recipient, event). ``event_key`` makes creation idempotent so a
redelivered Celery task cannot produce a second row or a second email.

Rows are created inside the caller's transaction so the record lands atomically
with the event that caused it. Email is delivered afterwards, off the request
path, and never affects the outcome of the event.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book
from app.models.job import Job, JobStatus, JobType
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

STAGE_LABELS: dict[str, str] = {
    JobType.PAGE_EXTRACTION: "Page rendering",
    JobType.PREPROCESSING: "Preprocessing",
    JobType.OCR: "OCR",
    JobType.LLM: "Metadata extraction",
}

# Where the user should land when they act on the notification.
STAGE_PATHS: dict[str, str] = {
    JobType.PAGE_EXTRACTION: "select-pages",
    JobType.PREPROCESSING: "ocr-review",
    JobType.OCR: "ocr-review",
    JobType.LLM: "metadata-review",
}

_STATUS_TYPES: dict[str, str] = {
    JobStatus.COMPLETED: NotificationType.JOB_COMPLETED,
    JobStatus.FAILED: NotificationType.JOB_FAILED,
    JobStatus.CANCELLED: NotificationType.JOB_CANCELLED,
}


def _book_label(book: Book | None) -> str:
    if book is None:
        return "Your book"
    return book.title or book.filename or "Your book"


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str,
    event_key: str,
    link_url: str | None = None,
    book_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """Insert a notification, or return None when this event already exists.

    The unique constraint on ``(user_id, event_key)`` is the real guard; the
    pre-check only avoids a needless savepoint on the common path.
    """
    existing = await db.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id, Notification.event_key == event_key
        )
    )
    if existing is not None:
        return None

    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link_url=link_url,
        book_id=book_id,
        event_key=event_key,
    )
    try:
        # A savepoint keeps a losing race from poisoning the caller's
        # transaction, which for worker paths already holds committed state.
        async with db.begin_nested():
            db.add(notification)
            await db.flush()
    except IntegrityError:
        logger.debug("Notification %s already exists; skipping", event_key)
        return None
    return notification.id


_TERMINAL_TITLES: dict[str, str] = {
    NotificationType.JOB_COMPLETED: "finished",
    NotificationType.JOB_FAILED: "failed",
    NotificationType.JOB_CANCELLED: "was cancelled",
}


async def notify_job_terminal(
    db: AsyncSession,
    *,
    job: Job,
    book: Book | None,
    status: str,
) -> uuid.UUID | None:
    """Create the notification for a job that reached a terminal status."""
    type_ = _STATUS_TYPES.get(status)
    if type_ is None:
        return None

    recipient_id = job.requested_by_id
    if recipient_id is None and book is not None:
        recipient_id = book.owner_id
    if recipient_id is None:
        return None

    label = _book_label(book)
    stage = STAGE_LABELS.get(job.job_type, "Job")
    tail = _TERMINAL_TITLES[type_]
    title = f"{stage} {tail}: {label}"

    body = f"{stage} {tail} for “{label}”."
    if type_ == NotificationType.JOB_FAILED and job.error_log:
        body = f"{body}\n\n{job.error_log[:400]}"

    link_url = None
    if book is not None:
        path = STAGE_PATHS.get(job.job_type)
        if path:
            link_url = f"/books/{book.id}/{path}"

    return await create_notification(
        db,
        user_id=recipient_id,
        type=type_,
        title=title[:200],
        body=body[:1000],
        event_key=f"job:{job.id}:{status}",
        link_url=link_url,
        book_id=book.id if book is not None else None,
    )


async def notify_admins_registration(
    db: AsyncSession, user: User
) -> list[uuid.UUID]:
    """One row per active admin for a newly registered account."""
    admin_ids = (
        await db.execute(
            select(User.id).where(
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
    ).scalars().all()

    title = f"New registration: {user.display_name}"
    body = (
        f"{user.display_name} ({user.email}) registered and is awaiting "
        "administrative approval."
    )

    ids: list[uuid.UUID] = []
    for admin_id in admin_ids:
        created = await create_notification(
            db,
            user_id=admin_id,
            type=NotificationType.PENDING_REGISTRATION,
            title=title[:200],
            body=body[:1000],
            event_key=f"pending-registration:{user.id}",
            link_url="/admin/users?status=pending",
        )
        if created is not None:
            ids.append(created)
    return ids


async def notify_account_approved(db: AsyncSession, user: User) -> uuid.UUID | None:
    return await create_notification(
        db,
        user_id=user.id,
        type=NotificationType.ACCOUNT_APPROVED,
        title="Your account is approved",
        body=(
            "An administrator approved your account. You can now upload and "
            "process books."
        ),
        event_key=f"account-approved:{user.id}",
        link_url="/dashboard",
    )


async def mark_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification | None:
    notification = (
        await db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if notification is None:
        return None
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        await db.commit()
    return notification


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return int(result.rowcount or 0)


async def unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
        or 0
    )


async def set_email_preference(
    db: AsyncSession, user: User, enabled: bool
) -> User:
    user.email_notifications_enabled = enabled
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Email delivery — always off the request path, best-effort
# ---------------------------------------------------------------------------


async def deliver_notification_emails(notification_ids: list[uuid.UUID]) -> None:
    """Send emails for notifications whose recipient allows it, in a new session.

    Used by request paths via ``BackgroundTasks``, where the request's session is
    already closed. Every failure is logged and swallowed: a broken SMTP host
    must never surface as a failed request or job.
    """
    if not notification_ids:
        return
    if not settings.smtp_enabled:
        # Nothing to do, and no reason to open a session: local development and
        # the test suite run with SMTP off.
        logger.debug("SMTP disabled; skipping notification emails")
        return
    try:
        async with async_session_factory() as db:
            await deliver_emails_in_session(db, notification_ids)
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Notification email delivery failed")


async def deliver_emails_in_session(
    db: AsyncSession, notification_ids: list[uuid.UUID]
) -> int:
    """Send emails on the caller's session; returns how many were sent.

    Celery tasks use this so creation and delivery share one session — a second
    session during a worker's finalization is exactly what the stage-manager
    comments warn against.
    """
    if not notification_ids:
        return 0
    try:
        rows = (
            await db.execute(
                select(Notification, User)
                .join(User, User.id == Notification.user_id)
                .where(Notification.id.in_(notification_ids))
            )
        ).all()

        sent = 0
        skipped = 0
        for notification, user in rows:
            if notification.emailed_at is not None:
                continue
            if not user.email_notifications_enabled:
                skipped += 1
                continue
            if await _send_one(notification, user):
                notification.emailed_at = datetime.now(timezone.utc)
                sent += 1
        await db.flush()
        logger.info(
            "Notification email delivery: %d sent, %d skipped (preference off)",
            sent,
            skipped,
        )
        return sent
    except Exception:  # noqa: BLE001
        logger.exception("Notification email delivery failed")
        return 0


async def _send_one(notification: Notification, user: User) -> bool:
    link = (
        f"{settings.frontend_url.rstrip('/')}{notification.link_url}"
        if notification.link_url
        else settings.frontend_url
    )
    text = f"Hello {user.display_name},\n\n{notification.body}\n\n{link}\n"
    return await send_email(
        to=user.email,
        subject=notification.title,
        text_body=text,
    )


async def notify_and_deliver(
    db: AsyncSession,
    notifications: list[uuid.UUID | None],
) -> int:
    """Commit pending notification rows, then deliver their emails inline.

    Used by Celery tasks, which have no ``BackgroundTasks`` and whose queue the
    user is already waiting on. Delivery reuses the caller's session.
    """
    ids = [n for n in notifications if n is not None]
    if not ids:
        return 0
    await db.commit()
    sent = await deliver_emails_in_session(db, ids)
    await db.commit()
    return sent


__all__ = [
    "create_notification",
    "deliver_emails_in_session",
    "deliver_notification_emails",
    "mark_all_read",
    "mark_read",
    "notify_account_approved",
    "notify_admins_registration",
    "notify_and_deliver",
    "notify_job_terminal",
    "set_email_preference",
    "unread_count",
]
