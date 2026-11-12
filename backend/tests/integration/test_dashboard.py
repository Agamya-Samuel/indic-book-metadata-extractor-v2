"""Dashboard summaries, queue estimates, and job cancellation."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from tests.conftest import TestSessionFactory


async def _make_owned_book(owner_id, status: str = BookStatus.UPLOADED) -> Book:
    async with TestSessionFactory() as session:
        book = Book(
            id=uuid.uuid4(),
            title="Dash Book",
            filename="dash.pdf",
            language="tel",
            total_pages=2,
            status=status,
            owner_id=owner_id,
        )
        session.add(book)
        await session.commit()
        await session.refresh(book)
        return book


async def _make_job(
    book_id,
    *,
    owner_id=None,
    job_type: str = JobType.OCR,
    status: str = JobStatus.QUEUED,
    created_at: datetime | None = None,
) -> Job:
    async with TestSessionFactory() as session:
        job = Job(
            id=uuid.uuid4(),
            book_id=book_id,
            requested_by_id=owner_id,
            job_type=job_type,
            status=status,
            progress=0.0,
            created_at=created_at or datetime.now(timezone.utc),
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


async def test_dashboard_summary_counts_owned_books_and_jobs(
    client, regular_user, admin_user
):
    own_one = await _make_owned_book(regular_user.id, BookStatus.UPLOADED)
    own_two = await _make_owned_book(regular_user.id, BookStatus.AWAITING_REVIEW)
    other = await _make_owned_book(admin_user.id, BookStatus.UPLOADED)

    now = datetime.now(timezone.utc)
    await _make_job(own_one.id, owner_id=regular_user.id, status=JobStatus.QUEUED)
    await _make_job(
        own_two.id,
        owner_id=regular_user.id,
        job_type=JobType.LLM,
        status=JobStatus.RUNNING,
        created_at=now - timedelta(minutes=1),
    )
    # Another user's job must not leak into this dashboard.
    await _make_job(other.id, owner_id=admin_user.id, status=JobStatus.QUEUED)

    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["books"]["total"] == 2
    assert data["books"]["by_status"][BookStatus.UPLOADED] == 1
    assert data["books"]["by_status"][BookStatus.AWAITING_REVIEW] == 1
    assert data["jobs"]["total"] == 2
    assert data["jobs"]["queued"] == 1
    assert data["jobs"]["running"] == 1
    assert data["queue"] == {"ocr": 1, "llm": 0}


async def test_dashboard_books_are_owner_scoped(client, regular_user, admin_user):
    await _make_owned_book(regular_user.id)
    await _make_owned_book(admin_user.id)

    response = await client.get("/api/dashboard/books")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["owner_id"] == str(regular_user.id)


async def test_dashboard_jobs_report_queue_ahead(client, regular_user):
    now = datetime.now(timezone.utc)
    book = await _make_owned_book(regular_user.id)

    first_ocr = await _make_job(
        book.id,
        owner_id=regular_user.id,
        job_type=JobType.OCR,
        created_at=now - timedelta(minutes=4),
    )
    preprocessing = await _make_job(
        book.id,
        owner_id=regular_user.id,
        job_type=JobType.PREPROCESSING,
        created_at=now - timedelta(minutes=3),
    )
    first_llm = await _make_job(
        book.id,
        owner_id=regular_user.id,
        job_type=JobType.LLM,
        created_at=now - timedelta(minutes=2),
    )
    running_ocr = await _make_job(
        book.id,
        owner_id=regular_user.id,
        job_type=JobType.OCR,
        status=JobStatus.RUNNING,
        created_at=now - timedelta(minutes=1),
    )

    response = await client.get("/api/dashboard/jobs?page_size=50")
    assert response.status_code == 200
    rows = {row["id"]: row for row in response.json()["items"]}

    assert rows[str(first_ocr.id)]["queue_ahead"] == 0
    # Preprocessing shares the OCR queue and was created after the first job.
    assert rows[str(preprocessing.id)]["queue_ahead"] == 1
    assert rows[str(first_llm.id)]["queue_ahead"] == 0
    # Running jobs are at the front of their queue.
    assert rows[str(running_ocr.id)]["queue_ahead"] == 0


async def test_owner_can_cancel_own_queued_job(client, regular_user):
    book = await _make_owned_book(regular_user.id, BookStatus.OCR_RUNNING)
    job = await _make_job(book.id, owner_id=regular_user.id)

    response = await client.post(f"/api/dashboard/jobs/{job.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.CANCELLED

    async with TestSessionFactory() as session:
        refreshed = await session.get(Job, job.id)
        assert refreshed.status == JobStatus.CANCELLED
        assert "owner" in (refreshed.error_log or "").lower()


async def test_other_user_cannot_cancel_job(
    client, regular_user, auth_client, create_user
):
    book = await _make_owned_book(regular_user.id)
    job = await _make_job(book.id, owner_id=regular_user.id)

    other = await create_user(email="canceller@example.com")
    other_client = await auth_client(other)
    response = await other_client.post(f"/api/dashboard/jobs/{job.id}/cancel")
    assert response.status_code == 404


async def test_admin_can_cancel_any_job(client, admin_client, regular_user):
    book = await _make_owned_book(regular_user.id)
    job = await _make_job(book.id, owner_id=regular_user.id)

    response = await admin_client.post(f"/api/dashboard/jobs/{job.id}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == JobStatus.CANCELLED


async def test_cannot_cancel_finished_job(client, regular_user):
    book = await _make_owned_book(regular_user.id)
    job = await _make_job(
        book.id, owner_id=regular_user.id, status=JobStatus.COMPLETED
    )
    response = await client.post(f"/api/dashboard/jobs/{job.id}/cancel")
    assert response.status_code == 400
