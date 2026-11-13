"""Age out jobs whose worker died and never came back.

A worker restart usually resumes the task (Celery restores unacked messages),
and an operator can always cancel a stuck job. But neither is guaranteed: an
observed restart mid-extraction left ``jobs.status='running'`` forever and the
book locked in ``llm_running``, which blocks every re-run. This sweep marks such
jobs failed once they are far past any legitimate runtime, releases the book the
same way a task failure does, and tells the owner.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.services import notification_service
from app.services.stage_manager import StageManager

logger = logging.getLogger(__name__)

STAGE_FOR_JOB: dict[str, str] = {
    JobType.PAGE_EXTRACTION: "page_selection",
    JobType.PREPROCESSING: "ocr",
    JobType.OCR: "ocr",
    JobType.LLM: "llm_extraction",
}


def _release_book(book: Book, job_type: str) -> None:
    """Undo the in-flight status the job set, without skipping a stage back."""
    if job_type == JobType.LLM and book.status == BookStatus.LLM_RUNNING:
        book.status = BookStatus.OCR_COMPLETE
    elif job_type in (JobType.OCR, JobType.PREPROCESSING) and book.status == BookStatus.OCR_RUNNING:
        book.status = BookStatus.PAGES_SELECTED


async def reap_stale_jobs(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    """Fail running jobs older than the threshold; returns how many were reaped."""
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(
        minutes=settings.stale_job_minutes
    )
    jobs = (
        await db.execute(
            select(Job).where(
                Job.status == JobStatus.RUNNING,
                Job.started_at.is_not(None),
                Job.started_at < cutoff,
            )
        )
    ).scalars().all()

    reaped = 0
    notification_ids: list = []
    reference_now = now or datetime.now(timezone.utc)
    for job in jobs:
        started = job.started_at
        if started.tzinfo is None:
            # SQLite hands back naive datetimes in tests.
            started = started.replace(tzinfo=timezone.utc)
        age_minutes = int((reference_now - started).total_seconds() // 60)
        job.status = JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        job.error_log = (
            f"Worker lost: no completion {age_minutes} minutes after start "
            f"(threshold {settings.stale_job_minutes}). Job marked failed so the "
            "book can be run again."
        )

        book = await db.get(Book, job.book_id) if job.book_id else None
        if book is not None:
            _release_book(book, job.job_type)

        stage = STAGE_FOR_JOB.get(job.job_type)
        if job.book_id and stage:
            try:
                await StageManager.fail_stage(db, job.book_id, stage, job.error_log)
            except Exception:  # noqa: BLE001
                logger.debug("Could not fail stage %s for job %s", stage, job.id, exc_info=True)

        notification_ids.append(
            await notification_service.notify_job_terminal(
                db, job=job, book=book, status=JobStatus.FAILED
            )
        )
        reaped += 1
        logger.warning("Reaped stale %s job %s (age %d min)", job.job_type, job.id, age_minutes)

    if reaped:
        await db.commit()
        await notification_service.notify_and_deliver(db, notification_ids)
    return reaped