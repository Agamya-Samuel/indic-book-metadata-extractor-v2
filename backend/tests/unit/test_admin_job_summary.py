"""Admin job summary aggregates and enriched job rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.stage import BookStageStatus, StageStatus
from app.models.user import AccountStatus, User
from app.services import admin_service

NOW = datetime.now(timezone.utc)


async def _user(db_session, display_name: str) -> User:
    user = User(
        email=f"{uuid.uuid4().hex[:10]}@example.com",
        display_name=display_name,
        password_hash="x",
        account_status=AccountStatus.APPROVED,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _book(db_session, owner: User, *, title: str = "Queue Book") -> Book:
    book = Book(
        id=uuid.uuid4(),
        title=title,
        filename="queue.pdf",
        language="tel",
        total_pages=2,
        owner_id=owner.id,
        status=BookStatus.OCR_RUNNING,
    )
    db_session.add(book)
    await db_session.commit()
    return book


async def _job(
    db_session,
    book: Book,
    owner: User,
    *,
    job_type: str = JobType.OCR,
    status: str = JobStatus.QUEUED,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> Job:
    job = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=owner.id,
        job_type=job_type,
        status=status,
        progress=0.0,
        created_at=created_at or NOW,
        started_at=started_at,
        completed_at=completed_at,
    )
    db_session.add(job)
    await db_session.commit()
    return job


class TestJobSummary:
    async def test_counts_per_user_and_status(self, db_session) -> None:
        alice = await _user(db_session, "Alice")
        bob = await _user(db_session, "Bob")
        book_a = await _book(db_session, alice)
        book_b = await _book(db_session, bob)

        await _job(db_session, book_a, alice, status=JobStatus.QUEUED)
        await _job(db_session, book_a, alice, status=JobStatus.QUEUED)
        await _job(db_session, book_a, alice, job_type=JobType.LLM, status=JobStatus.COMPLETED)
        await _job(db_session, book_b, bob, status=JobStatus.FAILED)

        summary = await admin_service.get_job_summary(db_session)

        assert summary["total"] == 4
        assert summary["queued"] == 2
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert summary["by_type"].get("ocr") == 3
        assert summary["by_type"].get("llm") == 1

        by_name = {row["display_name"]: row for row in summary["by_user"]}
        assert by_name["Alice"]["total"] == 3
        assert by_name["Alice"]["queued"] == 2
        assert by_name["Alice"]["completed"] == 1
        assert by_name["Bob"]["total"] == 1
        assert by_name["Bob"]["failed"] == 1

    async def test_empty_summary(self, db_session) -> None:
        summary = await admin_service.get_job_summary(db_session)
        assert summary["total"] == 0
        assert summary["by_user"] == []


class TestListAdminJobsEnrichment:
    async def test_queue_positions_and_duration(self, db_session) -> None:
        owner = await _user(db_session, "Owner")
        book = await _book(db_session, owner)

        first = await _job(db_session, book, owner, created_at=NOW - timedelta(minutes=10))
        second = await _job(db_session, book, owner, created_at=NOW - timedelta(minutes=5))
        running = await _job(
            db_session,
            book,
            owner,
            status=JobStatus.RUNNING,
            created_at=NOW - timedelta(minutes=3),
            started_at=NOW - timedelta(seconds=100),
        )
        done = await _job(
            db_session,
            book,
            owner,
            status=JobStatus.COMPLETED,
            created_at=NOW - timedelta(minutes=20),
            started_at=NOW - timedelta(minutes=19),
            completed_at=NOW - timedelta(minutes=18),
        )

        items, total = await admin_service.list_admin_jobs(
            db_session,
            status=None,
            job_type=None,
            book_id=None,
            page=1,
            page_size=50,
        )
        assert total == 4
        rows = {item["id"]: item for item in items}

        assert rows[str(first.id)]["queue_ahead"] == 0
        assert rows[str(second.id)]["queue_ahead"] == 1
        assert rows[str(running.id)]["queue_ahead"] == 0
        assert rows[str(done.id)]["queue_ahead"] is None
        assert rows[str(done.id)]["duration_seconds"] == 60
        assert rows[str(running.id)]["duration_seconds"] >= 100

    async def test_stage_and_sort(self, db_session) -> None:
        owner = await _user(db_session, "Stage Owner")
        book = await _book(db_session, owner)
        await _job(db_session, book, owner, status=JobStatus.RUNNING, created_at=NOW - timedelta(minutes=1))
        db_session.add(
            BookStageStatus(
                book_id=book.id,
                stage_name="ocr",
                attempt=1,
                status=StageStatus.PROCESSING.value,
            )
        )
        await db_session.commit()

        items, _ = await admin_service.list_admin_jobs(
            db_session,
            status=None,
            job_type=None,
            book_id=None,
            page=1,
            page_size=10,
            sort="created_at",
            order="asc",
        )
        assert items[0]["stage_name"] == "ocr"
        assert items[0]["stage_status"] == StageStatus.PROCESSING.value

    async def test_invalid_sort_falls_back(self, db_session) -> None:
        owner = await _user(db_session, "Fallback Owner")
        book = await _book(db_session, owner)
        await _job(db_session, book, owner)
        items, total = await admin_service.list_admin_jobs(
            db_session,
            status=None,
            job_type=None,
            book_id=None,
            page=1,
            page_size=10,
            sort="not-a-column",
            order="sideways",
        )
        assert total == 1
        assert len(items) == 1


class TestBulkCancel:
    async def test_cancels_queued_and_reports_terminal(self, db_session) -> None:
        owner = await _user(db_session, "Bulk Owner")
        book = await _book(db_session, owner)
        queued = await _job(db_session, book, owner, status=JobStatus.QUEUED)
        completed = await _job(db_session, book, owner, status=JobStatus.COMPLETED)

        results, _notification_ids = await admin_service.cancel_jobs_bulk(
            db_session, [queued.id, completed.id, uuid.uuid4()]
        )
        by_id = {str(row["id"]): row for row in results}

        assert by_id[str(queued.id)]["ok"] is True
        assert by_id[str(queued.id)]["status"] == JobStatus.CANCELLED
        assert by_id[str(completed.id)]["ok"] is False
        assert "already" in by_id[str(completed.id)]["error"]
        assert by_id[str(completed.id)]["status"] == JobStatus.COMPLETED

        await db_session.refresh(queued)
        assert queued.status == JobStatus.CANCELLED
        await db_session.refresh(completed)
        assert completed.status == JobStatus.COMPLETED


class TestRetryJob:
    async def test_retries_failed_ocr(self, db_session) -> None:
        owner = await _user(db_session, "Retry Owner")
        book = await _book(db_session, owner)
        failed = await _job(db_session, book, owner, status=JobStatus.FAILED)
        replacement = Job(
            id=uuid.uuid4(),
            book_id=book.id,
            job_type=JobType.OCR,
            status=JobStatus.QUEUED,
            progress=0.0,
        )

        with patch("app.services.admin_service.rerun_ocr", AsyncMock(return_value=replacement)) as rerun:
            job = await admin_service.retry_job(db_session, failed.id, requested_by_id=owner.id)

        assert job is replacement
        rerun.assert_awaited_once()

    async def test_refuses_non_failed(self, db_session) -> None:
        owner = await _user(db_session, "Retry Guard")
        book = await _book(db_session, owner)
        queued = await _job(db_session, book, owner, status=JobStatus.QUEUED)

        try:
            await admin_service.retry_job(db_session, queued.id)
        except ValueError as exc:
            assert "Only failed" in str(exc)
        else:  # pragma: no cover - assertion failure path
            raise AssertionError("retry_job should reject non-failed jobs")

    async def test_refuses_unsupported_type(self, db_session) -> None:
        owner = await _user(db_session, "Retry Type")
        book = await _book(db_session, owner)
        failed = await _job(db_session, book, owner, job_type=JobType.PAGE_EXTRACTION, status=JobStatus.FAILED)

        try:
            await admin_service.retry_job(db_session, failed.id)
        except ValueError as exc:
            assert "not supported" in str(exc)
        else:  # pragma: no cover - assertion failure path
            raise AssertionError("retry_job should reject unsupported job types")
