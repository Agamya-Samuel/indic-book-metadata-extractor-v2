"""Per-user quotas for uploads and active pipeline jobs."""

from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_approved_user
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book
from app.models.job import Job, JobStatus
from app.models.user import User


def _too_many(detail: str) -> HTTPException:
    return HTTPException(status_code=429, detail=detail)


async def enforce_job_quota(
    user: User = Depends(require_approved_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Reject new work when the user already has too many active jobs."""
    limit = settings.max_active_jobs_per_user
    count = int(
        await db.scalar(
            select(func.count(Job.id)).where(
                Job.requested_by_id == user.id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        or 0
    )
    if count >= limit:
        raise _too_many(
            f"You already have {count} active job(s). Wait for them to finish before starting more (limit {limit})."
        )
    return user


async def enforce_book_quota(
    user: User = Depends(require_approved_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Reject an upload when the user already owns the maximum number of books."""
    limit = settings.max_books_per_user
    count = int(await db.scalar(select(func.count(Book.id)).where(Book.owner_id == user.id)) or 0)
    if count >= limit:
        raise _too_many(f"You already own {count} book(s); the limit is {limit}. Delete one before uploading another.")
    return user
