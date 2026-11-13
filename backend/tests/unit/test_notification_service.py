"""Unit tests for notification creation, idempotency, and email gating."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from app.models.book import Book
from app.models.job import Job, JobStatus, JobType
from app.models.notification import Notification, NotificationType
from app.models.user import AccountStatus, User, UserRole
from app.services import notification_service


async def _make_user(
    db_session,
    *,
    role: str = UserRole.USER,
    is_active: bool = True,
    email_notifications_enabled: bool = True,
) -> User:
    user = User(
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        display_name="Test Person",
        password_hash="not-a-real-hash",
        role=role,
        is_active=is_active,
        account_status=AccountStatus.APPROVED,
        email_notifications_enabled=email_notifications_enabled,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _make_book(db_session, owner: User, title: str = "Test Book") -> Book:
    book = Book(
        id=uuid.uuid4(),
        title=title,
        filename="test.pdf",
        language="tel",
        total_pages=3,
        owner_id=owner.id,
    )
    db_session.add(book)
    await db_session.commit()
    return book


async def _count(db_session, where_clause=None) -> int:
    stmt = select(func.count(Notification.id))
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    return int(await db_session.scalar(stmt) or 0)


async def test_create_notification_is_idempotent(db_session) -> None:
    user = await _make_user(db_session)
    kwargs = dict(
        user_id=user.id,
        type=NotificationType.JOB_COMPLETED,
        title="OCR finished",
        body="Body",
        event_key=f"job:{uuid.uuid4()}:completed",
    )

    first = await notification_service.create_notification(db_session, **kwargs)
    await db_session.commit()
    second = await notification_service.create_notification(db_session, **kwargs)
    await db_session.commit()

    assert first is not None
    assert second is None
    assert await _count(db_session) == 1


async def test_same_event_key_is_per_recipient(db_session) -> None:
    one = await _make_user(db_session)
    two = await _make_user(db_session)
    key = "pending-registration:abc"

    for user in (one, two):
        await notification_service.create_notification(
            db_session,
            user_id=user.id,
            type=NotificationType.PENDING_REGISTRATION,
            title="New registration",
            body="Body",
            event_key=key,
        )
    await db_session.commit()

    assert await _count(db_session) == 2


@pytest.mark.parametrize(
    "status,type_,link_suffix",
    [
        (JobStatus.COMPLETED, NotificationType.JOB_COMPLETED, "metadata-review"),
        (JobStatus.FAILED, NotificationType.JOB_FAILED, "metadata-review"),
        (JobStatus.CANCELLED, NotificationType.JOB_CANCELLED, "metadata-review"),
    ],
)
async def test_job_terminal_maps_status_to_notification(
    db_session, status, type_, link_suffix
) -> None:
    owner = await _make_user(db_session)
    book = await _make_book(db_session, owner)
    job = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=owner.id,
        job_type=JobType.LLM,
        status=status,
        error_log="boom" if status == JobStatus.FAILED else None,
    )
    db_session.add(job)
    await db_session.commit()

    notification_id = await notification_service.notify_job_terminal(
        db_session, job=job, book=book, status=status
    )
    await db_session.commit()

    row = await db_session.get(Notification, notification_id)
    assert row is not None
    assert row.type == type_
    assert row.link_url == f"/books/{book.id}/{link_suffix}"
    assert row.book_id == book.id
    if status == JobStatus.FAILED:
        assert "boom" in row.body


async def test_job_terminal_prefers_requester_and_falls_back_to_owner(db_session) -> None:
    owner = await _make_user(db_session)
    requester = await _make_user(db_session)
    book = await _make_book(db_session, owner)

    with_requester = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=requester.id,
        job_type=JobType.OCR,
        status=JobStatus.COMPLETED,
    )
    without_requester = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=None,
        job_type=JobType.OCR,
        status=JobStatus.COMPLETED,
    )
    db_session.add_all([with_requester, without_requester])
    await db_session.commit()

    first = await notification_service.notify_job_terminal(
        db_session, job=with_requester, book=book, status=JobStatus.COMPLETED
    )
    second = await notification_service.notify_job_terminal(
        db_session, job=without_requester, book=book, status=JobStatus.COMPLETED
    )
    await db_session.commit()

    assert (await db_session.get(Notification, first)).user_id == requester.id
    assert (await db_session.get(Notification, second)).user_id == owner.id


async def test_registration_alert_reaches_only_active_admins(db_session) -> None:
    active = await _make_user(db_session, role=UserRole.ADMIN)
    await _make_user(db_session, role=UserRole.ADMIN, is_active=False)
    await _make_user(db_session, role=UserRole.USER)
    newcomer = await _make_user(db_session)

    ids = await notification_service.notify_admins_registration(db_session, newcomer)
    await db_session.commit()

    assert len(ids) == 1
    assert (await db_session.get(Notification, ids[0])).user_id == active.id


async def test_account_approved_points_at_dashboard(db_session) -> None:
    user = await _make_user(db_session)
    notification_id = await notification_service.notify_account_approved(db_session, user)
    await db_session.commit()

    row = await db_session.get(Notification, notification_id)
    assert row.type == NotificationType.ACCOUNT_APPROVED
    assert row.link_url == "/dashboard"


async def test_email_delivery_respects_preference(db_session, monkeypatch) -> None:
    opted_in = await _make_user(db_session)
    opted_out = await _make_user(db_session, email_notifications_enabled=False)

    ids = []
    for user in (opted_in, opted_out):
        ids.append(
            await notification_service.create_notification(
                db_session,
                user_id=user.id,
                type=NotificationType.ACCOUNT_APPROVED,
                title="Approved",
                body="Body",
                event_key=f"account-approved:{user.id}",
                link_url="/dashboard",
            )
        )
    await db_session.commit()

    send = AsyncMock(return_value=True)
    monkeypatch.setattr(notification_service, "send_email", send)

    sent = await notification_service.deliver_emails_in_session(db_session, ids)
    await db_session.commit()

    assert sent == 1
    assert send.await_count == 1
    assert send.await_args.kwargs["to"] == opted_in.email
    assert "http" in send.await_args.kwargs["text_body"]

    rows = (await db_session.execute(select(Notification))).scalars().all()
    stamped = {row.user_id: row.emailed_at is not None for row in rows}
    assert stamped[opted_in.id] is True
    assert stamped[opted_out.id] is False


async def test_email_failure_is_swallowed(db_session, monkeypatch) -> None:
    user = await _make_user(db_session)
    notification_id = await notification_service.create_notification(
        db_session,
        user_id=user.id,
        type=NotificationType.JOB_COMPLETED,
        title="Done",
        body="Body",
        event_key="job:x:completed",
    )
    await db_session.commit()

    monkeypatch.setattr(
        notification_service, "send_email", AsyncMock(side_effect=RuntimeError("smtp down"))
    )

    sent = await notification_service.deliver_emails_in_session(db_session, [notification_id])
    assert sent == 0
    assert (await db_session.get(Notification, notification_id)).emailed_at is None


async def test_unread_count_and_read_transitions(db_session) -> None:
    user = await _make_user(db_session)
    other = await _make_user(db_session)
    ids = []
    for index in range(2):
        ids.append(
            await notification_service.create_notification(
                db_session,
                user_id=user.id,
                type=NotificationType.JOB_COMPLETED,
                title=f"Done {index}",
                body="Body",
                event_key=f"job:{index}:completed",
            )
        )
    await notification_service.create_notification(
        db_session,
        user_id=other.id,
        type=NotificationType.JOB_COMPLETED,
        title="Other",
        body="Body",
        event_key="job:other:completed",
    )
    await db_session.commit()

    assert await notification_service.unread_count(db_session, user.id) == 2

    assert await notification_service.mark_read(db_session, other.id, ids[0]) is None
    assert await notification_service.unread_count(db_session, user.id) == 2

    await notification_service.mark_read(db_session, user.id, ids[0])
    assert await notification_service.unread_count(db_session, user.id) == 1

    updated = await notification_service.mark_all_read(db_session, user.id)
    assert updated == 1
    assert await notification_service.unread_count(db_session, user.id) == 0