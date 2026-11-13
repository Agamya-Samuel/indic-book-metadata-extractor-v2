"""Stale-job reaper: fail lost jobs, free the book, tell the owner."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.notification import Notification
from app.models.user import AccountStatus, User
from app.services.job_reaper import reap_stale_jobs

NOW = datetime.now(timezone.utc)


async def _owner(db_session) -> User:
    user = User(
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        display_name="Reaper Owner",
        password_hash="x",
        account_status=AccountStatus.APPROVED,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _book(db_session, owner: User, status: str) -> Book:
    book = Book(
        id=uuid.uuid4(),
        title="Wedged Book",
        filename="wedged.pdf",
        language="tel",
        total_pages=3,
        owner_id=owner.id,
        status=status,
    )
    db_session.add(book)
    await db_session.commit()
    return book


async def _job(
    db_session, book: Book, owner: User, *, status: str = JobStatus.RUNNING, **kwargs
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=owner.id,
        job_type=JobType.LLM,
        status=status,
        progress=0,
        **kwargs,
    )
    db_session.add(job)
    await db_session.commit()
    return job


async def test_reaps_a_job_past_the_threshold(db_session) -> None:
    owner = await _owner(db_session)
    book = await _book(db_session, owner, BookStatus.LLM_RUNNING)
    stale = await _job(
        db_session, book, owner, started_at=NOW - timedelta(minutes=settings.stale_job_minutes + 5)
    )

    reaped = await reap_stale_jobs(db_session, now=NOW)

    assert reaped == 1
    await db_session.refresh(stale)
    assert stale.status == JobStatus.FAILED
    assert "Worker lost" in (stale.error_log or "")
    assert stale.completed_at is not None

    await db_session.refresh(book)
    assert book.status == BookStatus.OCR_COMPLETE

    notification = (
        await db_session.execute(
            Notification.__table__.select().where(Notification.user_id == owner.id)
        )
    ).first()
    assert notification is not None
    assert notification.type == "job_failed"


async def test_leaves_recent_and_queued_jobs_alone(db_session) -> None:
    owner = await _owner(db_session)
    book = await _book(db_session, owner, BookStatus.LLM_RUNNING)
    recent = await _job(db_session, book, owner, started_at=NOW - timedelta(minutes=5))
    queued = await _job(db_session, book, owner, status=JobStatus.QUEUED, started_at=None)

    reaped = await reap_stale_jobs(db_session, now=NOW)

    assert reaped == 0
    await db_session.refresh(recent)
    await db_session.refresh(queued)
    assert recent.status == JobStatus.RUNNING
    assert queued.status == JobStatus.QUEUED


async def test_second_sweep_is_a_no_op(db_session) -> None:
    owner = await _owner(db_session)
    book = await _book(db_session, owner, BookStatus.LLM_RUNNING)
    await _job(
        db_session, book, owner, started_at=NOW - timedelta(minutes=settings.stale_job_minutes + 30)
    )

    assert await reap_stale_jobs(db_session, now=NOW) == 1
    assert await reap_stale_jobs(db_session, now=NOW) == 0