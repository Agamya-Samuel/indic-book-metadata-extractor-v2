"""Per-user dashboard queries: owned books, jobs, and queue estimates."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book
from app.models.job import Job, JobStatus, JobType


def queue_family(job_type: str) -> str:
    """Map a job type to the Celery queue that executes it.

    Preprocessing and OCR both run on the ``ocr`` worker; LLM extraction runs
    on the ``llm`` worker.
    """
    return "llm" if job_type == JobType.LLM else "ocr"


def _job_ownership_condition(user_id: UUID):
    """Jobs requested by the user, or attached to a book the user owns."""
    return or_(Job.requested_by_id == user_id, Book.owner_id == user_id)


async def _queue_ahead(db: AsyncSession, job: Job) -> int | None:
    """Estimate how many same-family queued jobs were created before this one."""
    if job.status == JobStatus.RUNNING:
        return 0
    if job.status != JobStatus.QUEUED or job.created_at is None:
        return None

    family = queue_family(job.job_type)
    if family == "llm":
        family_filter = Job.job_type == JobType.LLM
    else:
        family_filter = Job.job_type.in_((JobType.OCR, JobType.PREPROCESSING))

    count = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.QUEUED,
            family_filter,
            Job.created_at < job.created_at,
        )
    )
    return int(count or 0)


async def get_summary(db: AsyncSession, user_id: UUID) -> dict:
    book_status_rows = (
        await db.execute(
            select(Book.status, func.count(Book.id))
            .where(Book.owner_id == user_id)
            .group_by(Book.status)
        )
    ).all()
    books_by_status = {status: count for status, count in book_status_rows}
    total_books = sum(books_by_status.values())

    base = (
        select(Job.status, func.count(Job.id))
        .select_from(Job)
        .outerjoin(Book, Job.book_id == Book.id)
        .where(_job_ownership_condition(user_id))
        .group_by(Job.status)
    )
    job_status_rows = (await db.execute(base)).all()
    jobs_by_status = {status: count for status, count in job_status_rows}
    total_jobs = sum(jobs_by_status.values())

    queued_jobs = (
        await db.execute(
            select(Job.job_type, func.count(Job.id))
            .select_from(Job)
            .outerjoin(Book, Job.book_id == Book.id)
            .where(
                _job_ownership_condition(user_id),
                Job.status == JobStatus.QUEUED,
            )
            .group_by(Job.job_type)
        )
    ).all()
    queue_counts = {"ocr": 0, "llm": 0}
    for job_type, count in queued_jobs:
        queue_counts[queue_family(job_type)] += count

    return {
        "books": {
            "total": total_books,
            "by_status": books_by_status,
        },
        "jobs": {
            "total": total_jobs,
            "queued": jobs_by_status.get(JobStatus.QUEUED, 0),
            "running": jobs_by_status.get(JobStatus.RUNNING, 0),
            "completed": jobs_by_status.get(JobStatus.COMPLETED, 0),
            "failed": jobs_by_status.get(JobStatus.FAILED, 0),
            "cancelled": jobs_by_status.get(JobStatus.CANCELLED, 0),
        },
        "queue": queue_counts,
    }


async def list_jobs(
    db: AsyncSession,
    user_id: UUID,
    *,
    status: str | None,
    job_type: str | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    query = (
        select(Job, Book.title, Book.filename)
        .outerjoin(Book, Job.book_id == Book.id)
        .where(_job_ownership_condition(user_id))
    )
    count_query = (
        select(func.count(Job.id))
        .select_from(Job)
        .outerjoin(Book, Job.book_id == Book.id)
        .where(_job_ownership_condition(user_id))
    )

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
        count_query = count_query.where(Job.job_type == job_type)

    total = int(await db.scalar(count_query) or 0)

    query = (
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(query)).all()

    items: list[dict] = []
    for job, book_title, book_filename in rows:
        items.append(
            {
                "id": job.id,
                "book_id": job.book_id,
                "book_title": book_title,
                "book_filename": book_filename,
                "job_type": job.job_type,
                "status": job.status,
                "progress": job.progress,
                "queue_ahead": await _queue_ahead(db, job),
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "error_log": job.error_log,
            }
        )

    return items, total
