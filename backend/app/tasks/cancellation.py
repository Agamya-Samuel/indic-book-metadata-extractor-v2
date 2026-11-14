"""Cooperative cancellation and supersession checks for pipeline tasks.

The DB row is the source of truth: a job the API cancelled may still be
running inside a worker, and a re-run creates a newer job for the same book
and type. Tasks ask these helpers before each unit of work and before they
write a terminal status, so a cancelled or superseded run can never overwrite
the state a replacement run has already produced.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.job import Job, JobStatus


logger = logging.getLogger(__name__)


async def is_cancelled_async(db: AsyncSession, job_id: uuid.UUID) -> bool:
    """True when the job is cancelled or its row no longer exists."""
    status = (await db.execute(select(Job.status).where(Job.id == job_id))).scalar_one_or_none()
    return status is None or status == JobStatus.CANCELLED


async def is_superseded_async(db: AsyncSession, job: Job, *, newer_statuses: tuple[str, ...] | None = None) -> bool:
    """True when a newer job of the same type exists for the same book.

    A re-run cancels the old row and creates a new one. If the old worker is
    still alive it must not touch the stage row, which now belongs to the new
    attempt.
    """
    if job.book_id is None or job.created_at is None:
        return False

    query = select(Job.id).where(
        Job.book_id == job.book_id,
        Job.job_type == job.job_type,
        Job.id != job.id,
        Job.created_at > job.created_at,
    )
    if newer_statuses:
        query = query.where(Job.status.in_(newer_statuses))
    result = await db.execute(query.limit(1))
    return result.scalar_one_or_none() is not None


async def is_cancelled_or_superseded_async(db: AsyncSession, job: Job) -> bool:
    if await is_cancelled_async(db, job.id):
        return True
    return await is_superseded_async(db, job)


def _run_threadsafe(coro, *, default: bool = False) -> bool:
    from app.tasks.async_utils import run_async_threadsafe

    try:
        return bool(run_async_threadsafe(coro))
    except Exception:  # noqa: BLE001
        logger.debug("Cancellation check failed; assuming not cancelled", exc_info=True)
        return default


def is_cancelled(job_id: uuid.UUID) -> bool:
    """Synchronous wrapper for sync Celery task bodies."""

    async def _do() -> bool:
        async with async_session_factory() as db:
            return await is_cancelled_async(db, job_id)

    return _run_threadsafe(_do(), default=False)


def is_superseded(job_id: uuid.UUID) -> bool:
    """Synchronous wrapper; a missing row counts as cancelled, not superseded."""

    async def _do() -> bool:
        async with async_session_factory() as db:
            job = await db.get(Job, job_id)
            if job is None:
                return False
            return await is_superseded_async(db, job)

    return _run_threadsafe(_do(), default=False)


def should_stop(job_id: uuid.UUID) -> bool:
    """Synchronous one-query check: cancelled, deleted, or superseded."""

    async def _do() -> bool:
        async with async_session_factory() as db:
            job = await db.get(Job, job_id)
            if job is None or job.status == JobStatus.CANCELLED:
                return True
            return await is_superseded_async(db, job)

    try:
        return bool(_run_threadsafe(_do(), default=False))
    except Exception:  # noqa: BLE001
        return False
