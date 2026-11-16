"""Admin operations: cross-book stats, delete, reset, re-run jobs.

These helpers keep DB transactions and storage cleanup together so the
HTTP layer stays thin.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, BookStatus
from app.models.stage import BookStageStatus, StageStatus
from app.models.job import Job, JobStatus, JobType
from app.models.metadata import BookMetadata
from app.models.metadata_field_evidence import MetadataFieldEvidence
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.models.user import AccountStatus, User
from app.services import notification_service, storage
from app.services.dashboard_service import queue_family
from app.services.stage_manager import StageManager

logger = logging.getLogger(__name__)

# Which lifecycle stage each cancellable job type drives. Used to terminalise
# the stage row when a job is cancelled.
_JOB_STAGE_NAME = {
    JobType.OCR: "ocr",
    JobType.LLM: "llm_extraction",
    JobType.PAGE_EXTRACTION: "page_selection",
    JobType.PREPROCESSING: "ocr",
}


def _revoke_task_ids(entries: Iterable[tuple[str | None, bool]]) -> None:
    """Revoke a batch of Celery tasks after their cancellation was committed.

    The task ids are captured before the commit because a deleted job row can
    no longer be read afterwards.
    """
    if not entries:
        return
    try:
        from app.tasks.celery_app import celery_app
    except Exception:  # noqa: BLE001
        logger.warning("Celery is unavailable; tasks were cancelled in the DB only", exc_info=True)
        return

    for task_id, terminate in entries:
        if not task_id:
            continue
        try:
            celery_app.control.revoke(task_id, terminate=terminate, reply=False)
        except Exception:  # noqa: BLE001
            logger.warning("Could not revoke Celery task %s", task_id, exc_info=True)


def _revoke_celery_task(job: Job, *, terminate: bool | None = None) -> None:
    """Stop a dispatched task from starting, or from continuing if running.

    ``terminate`` kills a prefork child that is already executing; callers that
    have just flipped the row to ``cancelled`` must pass ``terminate=True``
    explicitly, because the row no longer tells us what it was. Revocation is
    best-effort: the DB status is still the source of truth and every pipeline
    task re-checks it.
    """
    if not job.celery_task_id:
        return
    _revoke_task_ids(
        [
            (
                job.celery_task_id,
                job.status == JobStatus.RUNNING if terminate is None else terminate,
            )
        ]
    )


async def get_admin_stats(db: AsyncSession) -> dict:
    total_books = await db.scalar(select(func.count(Book.id))) or 0
    books_with_metadata = await db.scalar(select(func.count(BookMetadata.id))) or 0

    lang_result = await db.execute(select(Book.language, func.count(Book.id)).group_by(Book.language))
    languages = {row[0]: row[1] for row in lang_result.all()}

    status_result = await db.execute(select(Book.status, func.count(Book.id)).group_by(Book.status))
    statuses = {row[0]: row[1] for row in status_result.all()}

    queued = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.QUEUED)) or 0
    running = await db.scalar(select(func.count(Job.id)).where(Job.status == JobStatus.RUNNING)) or 0

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    failed_recent = (
        await db.scalar(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.FAILED,
                Job.created_at >= seven_days_ago,
            )
        )
        or 0
    )
    completed_recent = (
        await db.scalar(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.COMPLETED,
                Job.created_at >= seven_days_ago,
            )
        )
        or 0
    )

    disk_usage_bytes = _storage_disk_usage_bytes()
    disk_usage_mb = round(disk_usage_bytes / (1024 * 1024), 2)

    total_users = await db.scalar(select(func.count(User.id))) or 0
    active_users = await db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0
    pending_users = (
        await db.scalar(select(func.count(User.id)).where(User.account_status == AccountStatus.PENDING)) or 0
    )

    return {
        "total_books": total_books,
        "books_with_metadata": books_with_metadata,
        "languages": languages,
        "statuses": statuses,
        "jobs": {
            "queued": queued,
            "running": running,
            "failed_recent": failed_recent,
            "completed_recent": completed_recent,
        },
        "users": {
            "total": total_users,
            "active": active_users,
            "pending": pending_users,
        },
        "pending_user_count": pending_users,
        "disk_usage_mb": disk_usage_mb,
    }


_SORT_COLUMNS = {
    "created_at": Job.created_at,
    "started_at": Job.started_at,
    "completed_at": Job.completed_at,
    "status": Job.status,
    "job_type": Job.job_type,
    "owner": func.coalesce(User.display_name, User.email, ""),
    # Portable proxy for duration: most recent activity. Interval arithmetic
    # differs between PostgreSQL and SQLite, so keep the ORDER BY simple.
    "duration": func.coalesce(Job.completed_at, Job.started_at, Job.created_at),
}


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes even for timezone-aware columns."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _queue_positions(db: AsyncSession, jobs: list[Job]) -> dict[UUID, int]:
    """Queue position for the queued jobs on this page, in one query."""
    queued_ids = {job.id for job in jobs if job.status == JobStatus.QUEUED and job.created_at is not None}
    if not queued_ids:
        return {}

    rows = (
        await db.execute(select(Job.id, Job.job_type, Job.created_at).where(Job.status == JobStatus.QUEUED))
    ).all()

    families: dict[str, list[tuple[datetime, UUID]]] = {}
    for job_id, job_type, created_at in rows:
        aware = _as_aware(created_at)
        if aware is None:
            continue
        families.setdefault(queue_family(job_type), []).append((aware, job_id))

    positions: dict[UUID, int] = {}
    for entries in families.values():
        entries.sort(key=lambda item: item[0])
        for index, (_created_at, job_id) in enumerate(entries):
            positions[job_id] = index
    return {job_id: positions[job_id] for job_id in queued_ids if job_id in positions}


async def _latest_stages(db: AsyncSession, book_ids: list[UUID]) -> dict[UUID, tuple[str, str]]:
    """Most recently updated stage for each book, in one query."""
    if not book_ids:
        return {}
    rows = (
        await db.execute(
            select(BookStageStatus.book_id, BookStageStatus.stage_name, BookStageStatus.status)
            .where(BookStageStatus.book_id.in_(book_ids))
            .order_by(BookStageStatus.updated_at.desc(), BookStageStatus.created_at.desc())
        )
    ).all()
    latest: dict[UUID, tuple[str, str]] = {}
    for book_id, stage_name, status in rows:
        latest.setdefault(book_id, (stage_name, status))
    return latest


async def list_admin_jobs(
    db: AsyncSession,
    status: str | None,
    job_type: str | None,
    book_id: UUID | None,
    page: int,
    page_size: int,
    owner_id: UUID | None = None,
    sort: str | None = None,
    order: str | None = None,
) -> tuple[list[dict], int]:
    query = (
        select(
            Job,
            Book.title,
            Book.filename,
            User.display_name.label("owner_display_name"),
            User.email.label("owner_email"),
        )
        .outerjoin(Book, Job.book_id == Book.id)
        .outerjoin(
            User,
            User.id == func.coalesce(Job.requested_by_id, Book.owner_id),
        )
    )

    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if book_id:
        query = query.where(Job.book_id == book_id)
    if owner_id is not None:
        query = query.where(func.coalesce(Job.requested_by_id, Book.owner_id) == owner_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sort_key = sort if sort in _SORT_COLUMNS else "created_at"
    descending = (order or "desc").lower() != "asc"
    sort_column = _SORT_COLUMNS[sort_key]
    query = query.order_by(
        sort_column.desc() if descending else sort_column.asc(),
        Job.created_at.desc(),
        Job.id.desc(),
    )
    query = query.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(query)).all()
    jobs = [row[0] for row in rows]
    positions = await _queue_positions(db, jobs)
    stages = await _latest_stages(db, [job.book_id for job in jobs if job.book_id])

    now = datetime.now(timezone.utc)
    items = []
    for job, book_title, book_filename, owner_display_name, owner_email in rows:
        start = _as_aware(job.started_at or job.created_at)
        end = _as_aware(job.completed_at) or now
        duration_seconds = int((end - start).total_seconds()) if start else None

        if job.status == JobStatus.RUNNING:
            queue_ahead = 0
        elif job.status == JobStatus.QUEUED:
            queue_ahead = positions.get(job.id)
        else:
            queue_ahead = None

        stage_name, stage_status = stages.get(job.book_id, (None, None))

        items.append(
            {
                "id": str(job.id),
                "book_id": str(job.book_id) if job.book_id else None,
                "requested_by_id": str(job.requested_by_id) if job.requested_by_id else None,
                "book_title": book_title,
                "book_filename": book_filename or "(deleted book)",
                "owner_display_name": owner_display_name,
                "owner_email": owner_email,
                "job_type": job.job_type,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "last_progress_at": job.last_progress_at.isoformat() if job.last_progress_at else None,
                "error_log": job.error_log,
                "celery_task_id": job.celery_task_id,
                "duration_seconds": duration_seconds,
                "queue_ahead": queue_ahead,
                "stage_name": stage_name,
                "stage_status": stage_status,
            }
        )

    return items, total


async def get_job_summary(db: AsyncSession) -> dict:
    """Global job counts plus a per-user breakdown, in one grouped query."""
    owner = func.coalesce(Job.requested_by_id, Book.owner_id)
    rows = (
        await db.execute(
            select(
                owner.label("owner_id"),
                User.display_name,
                User.email,
                Job.status,
                func.count(Job.id),
            )
            .select_from(Job)
            .outerjoin(Book, Job.book_id == Book.id)
            .outerjoin(User, User.id == owner)
            .group_by(owner, User.display_name, User.email, Job.status)
        )
    ).all()

    by_user: dict[UUID | None, dict] = {}
    status_keys = ("queued", "running", "completed", "failed", "cancelled")
    totals = {key: 0 for key in status_keys}

    for owner_id, display_name, email, job_status, count in rows:
        bucket = by_user.setdefault(
            owner_id,
            {
                "user_id": owner_id,
                "display_name": display_name,
                "email": email,
                "total": 0,
                **{key: 0 for key in status_keys},
            },
        )
        bucket[job_status] = bucket.get(job_status, 0) + count
        bucket["total"] += count
        totals[job_status] = totals.get(job_status, 0) + count

    type_rows = (await db.execute(select(Job.job_type, func.count(Job.id)).group_by(Job.job_type))).all()
    by_type = {job_type: count for job_type, count in type_rows}

    return {
        "total": sum(totals.values()),
        **totals,
        "by_type": by_type,
        "by_user": sorted(by_user.values(), key=lambda row: row["total"], reverse=True),
    }


async def cancel_jobs_bulk(
    db: AsyncSession, job_ids: list[UUID], *, reason: str = "Cancelled by admin"
) -> tuple[list[dict], list[UUID]]:
    """Cancel each job independently; one terminal id must not abort the batch."""
    results: list[dict] = []
    notification_ids: list[UUID] = []

    for job_id in job_ids:
        job = await db.get(Job, job_id)
        if job is None:
            results.append({"id": job_id, "status": None, "ok": False, "error": "Job not found"})
            continue
        if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
            results.append(
                {
                    "id": job_id,
                    "status": job.status,
                    "ok": False,
                    "error": f"Job is already {job.status}",
                }
            )
            continue
        try:
            cancelled, notification_id = await cancel_job(db, job_id, reason=reason)
        except (LookupError, ValueError) as exc:
            results.append({"id": job_id, "status": None, "ok": False, "error": str(exc)})
            continue

        results.append({"id": job_id, "status": cancelled.status, "ok": True, "error": None})
        if notification_id is not None:
            notification_ids.append(notification_id)

    return results, notification_ids


async def retry_job(db: AsyncSession, job_id: UUID, *, requested_by_id: UUID | None = None) -> Job:
    """Re-dispatch a failed OCR or LLM job through the existing re-run paths."""
    job = await db.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    if job.status != JobStatus.FAILED:
        raise ValueError(f"Only failed jobs can be retried; job is '{job.status}'")
    if job.book_id is None:
        raise ValueError("The job's book no longer exists")

    if job.job_type == JobType.OCR:
        return await rerun_ocr(db, job.book_id, requested_by_id=requested_by_id)
    if job.job_type == JobType.LLM:
        return await rerun_extraction(db, job.book_id, requested_by_id=requested_by_id)
    raise ValueError(f"Retry is not supported for '{job.job_type}' jobs")


async def find_active_job(db: AsyncSession, book_id: UUID, job_type: str) -> Job | None:
    """The newest queued/running job of this type for the book, if any.

    Used to reject duplicate submissions instead of silently spawning a second
    job that would race the first.
    """
    result = await db.execute(
        select(Job)
        .where(
            Job.book_id == book_id,
            Job.job_type == job_type,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def cancel_job(db: AsyncSession, job_id: UUID, *, reason: str = "Cancelled by admin") -> tuple[Job, UUID | None]:
    """Cancel a queued/running job.

    Returns the job and the id of the notification created for its requester
    (None when this exact event already produced one), so the route can deliver
    the alert email after the response without holding the request open.
    """
    job = await db.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise ValueError(f"Cannot cancel job in status '{job.status}'")
    terminate = job.status == JobStatus.RUNNING
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    job.error_log = reason

    # Roll the book back to the stage that immediately precedes this job
    # type, so the UI re-enables the relevant "Run" button. Only do this
    # when the book is still in a state that implies this job is the
    # active one — never downgrade past OCR_COMPLETE for an LLM cancel
    # or past PAGES_SELECTED for an OCR cancel, even if a later stage
    # somehow already wrote to it.
    book = await db.get(Book, job.book_id)
    if book is not None:
        if job.job_type == JobType.LLM and book.status == BookStatus.LLM_RUNNING:
            book.status = BookStatus.OCR_COMPLETE
        elif job.job_type == JobType.OCR and book.status == BookStatus.OCR_RUNNING:
            book.status = BookStatus.PAGES_SELECTED

    # Terminalise the matching stage row too. Cancelling only the job leaves the
    # stage stuck in `processing`, and the book status is derived from stage
    # state, so the orphan wedges the next derivation exactly like a worker that
    # was killed mid-job.
    stage_name = _JOB_STAGE_NAME.get(job.job_type)
    if stage_name:
        row = await StageManager.get_stage(db, job.book_id, stage_name)
        if row is not None and row.status in (
            StageStatus.PROCESSING,
            StageStatus.INITIATED,
        ):
            await StageManager.cancel_stage(db, job.book_id, stage_name, reason)

    notification_id = await notification_service.notify_job_terminal(db, job=job, book=book, status=JobStatus.CANCELLED)
    await db.commit()
    _revoke_task_ids([(job.celery_task_id, terminate)])
    await db.refresh(job)
    return job, notification_id


async def delete_book(db: AsyncSession, book_id: UUID) -> None:
    """Delete a book and all its dependents, then clean up storage."""
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")

    # FKs: metadata_field_evidence.book_id, pages.book_id cascade from books;
    # llm_runs cascade from jobs; ocr_results cascade from pages. Book-level
    # cascade="all, delete-orphan" on relationships handles the fan-out.
    active_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    revoked: list[tuple[str | None, bool]] = []
    for j in active_jobs.scalars().all():
        revoked.append((j.celery_task_id, j.status == JobStatus.RUNNING))
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Book deleted by admin"
    await db.flush()

    await db.delete(book)
    await db.commit()

    _revoke_task_ids(revoked)
    _purge_book_storage(book_id)


async def reset_book(db: AsyncSession, book_id: UUID) -> Book:
    """Wipe pages/OCR/metadata/jobs/llm_runs; keep the original PDF."""
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")

    active_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    revoked: list[tuple[str | None, bool]] = []
    for j in active_jobs.scalars().all():
        revoked.append((j.celery_task_id, j.status == JobStatus.RUNNING))
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Book reset by admin"
    await db.flush()

    # Delete dependents in FK-safe order. The Page relationship cascades to
    # OcrResult, and the Job relationship cascades to LlmRun, so deleting
    # pages + jobs cleans up their children. BookMetadata + field evidence
    # cascade from Book, but we delete them explicitly first so we don't have
    # to fight ordering on the cascade config.
    await db.execute(delete(MetadataFieldEvidence).where(MetadataFieldEvidence.book_id == book_id))
    await db.execute(delete(BookMetadata).where(BookMetadata.book_id == book_id))
    await db.execute(delete(Job).where(Job.book_id == book_id))
    await db.execute(delete(Page).where(Page.book_id == book_id))

    book.status = BookStatus.UPLOADED
    await db.commit()
    _revoke_task_ids(revoked)
    await db.refresh(book)

    await StageManager.reset_book(db, book_id)
    await db.commit()

    # Clean page-derived artifacts on disk (keep the original PDF)
    _purge_book_artifacts(book_id, keep_original=True)

    return book


async def rerun_ocr(db: AsyncSession, book_id: UUID, *, requested_by_id: UUID | None = None) -> Job:
    """Cancel active jobs, clear OCR outputs, then dispatch a fresh OCR job.

    Mirrors the semantics of POST /api/books/{id}/run-ocr but is safe to
    call from any post-upload status.
    """
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id))
    pages = pages_result.scalars().all()
    if not pages:
        raise ValueError("No pages selected for this book. Select pages first.")

    # Cancel active OCR/LLM jobs
    active_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    revoked: list[tuple[str | None, bool]] = []
    for j in active_jobs.scalars().all():
        revoked.append((j.celery_task_id, j.status == JobStatus.RUNNING))
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Re-run OCR requested by admin"
    await db.flush()

    # Drop existing OCR results + processed images. Collect files to unlink
    # and only do so AFTER the DB commit succeeds so a commit failure
    # doesn't leave orphaned files behind.
    page_ids = [p.id for p in pages]
    await db.execute(delete(OcrResult).where(OcrResult.page_id.in_(page_ids)))
    files_to_unlink: list[Path] = []
    for p in pages:
        if p.processed_image_path:
            fp = Path(settings.storage_path) / p.processed_image_path
            files_to_unlink.append(fp)
        p.processed_image_path = None
        p.preprocessing_config = None
    # Extracted metadata and its evidence are KEPT. The confirm dialog tells the
    # user they are "kept but marked out of date until you re-run extraction",
    # and the stage reset already marks the downstream stages stale. Deleting
    # them here silently destroyed reviewed work.

    # Create new OCR job
    job = Job(
        book_id=book_id,
        requested_by_id=requested_by_id,
        job_type=JobType.OCR,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    book.status = BookStatus.OCR_RUNNING
    await db.commit()
    _revoke_task_ids(revoked)
    await db.refresh(job)

    # Reset the whole chain from OCR onward, not just the OCR row. A downstream
    # stage left in 'processing' by a worker that died (e.g. llm_extraction) is
    # never terminalised, and the book status is derived from stage state — so
    # leaving it behind wedges the book in llm_running with no way out, since
    # both run-extraction and rerun-extraction refuse a running status.
    await StageManager.reset_from_stage(db, book_id, "ocr", "Superseded by re-run OCR")
    await StageManager.initiate_stage(db, book_id, "ocr")
    await StageManager.start_stage(db, book_id, "ocr")
    await db.commit()

    # Commit succeeded — now safe to unlink the processed images.
    for fp in files_to_unlink:
        try:
            fp.unlink(missing_ok=True)
        except OSError:
            pass

    from app.tasks.ocr_tasks import preprocess_pages_for_book

    preprocess_pages_for_book.delay(str(job.id), str(book_id), book.language)

    return job


async def change_language(
    db: AsyncSession,
    book_id: UUID,
    language: str,
    *,
    requested_by_id: UUID | None = None,
) -> tuple[Book, Job | None]:
    """Correct a book's language, clearing and re-running OCR when pages exist.

    A wrong language silently sends Hindi through the Telugu line model / a
    ``tel+eng`` Tesseract pass (learnings/029). This keeps the original PDF and
    page images, but drops OCR output derived from the old language and, once
    pages exist, dispatches a fresh OCR job.
    """
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")
    if book.language == language:
        return book, None

    book.language = language
    await db.flush()

    has_page = (
        await db.execute(select(Page.id).where(Page.book_id == book_id).limit(1))
    ).scalar_one_or_none()
    if has_page is None:
        await db.commit()
        await db.refresh(book)
        return book, None

    job = await rerun_ocr(db, book_id, requested_by_id=requested_by_id)
    return book, job


async def rerun_extraction(db: AsyncSession, book_id: UUID, *, requested_by_id: UUID | None = None) -> Job:
    """Re-run LLM extraction on existing OCR outputs with default config."""
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")

    if book.status not in (
        BookStatus.OCR_COMPLETE,
        BookStatus.AWAITING_REVIEW,
        BookStatus.COMPLETE,
    ):
        raise ValueError(f"Book status must be 'ocr_complete', 'awaiting_review' or 'complete', got '{book.status}'")

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id))
    pages = pages_result.scalars().all()
    if not pages:
        raise ValueError("No pages selected for this book")

    page_ids = [p.id for p in pages]
    ocr_results = await db.execute(select(OcrResult).where(OcrResult.page_id.in_(page_ids)))
    ocr_list = ocr_results.scalars().all()
    if not any((o.corrected_text or o.raw_text or "").strip() for o in ocr_list):
        raise ValueError("No OCR text available. Run OCR first.")

    existing_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.job_type == JobType.LLM,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    if existing_jobs.scalars().first():
        raise ValueError("An LLM extraction job is already running or queued for this book")

    book.status = BookStatus.OCR_COMPLETE

    job = Job(
        book_id=book_id,
        requested_by_id=requested_by_id,
        job_type=JobType.LLM,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Same as rerun_ocr: release the downstream chain too, or an orphaned
    # metadata_review row keeps the derived book status stuck at the old stage.
    await StageManager.reset_from_stage(db, book_id, "llm_extraction", "Superseded by re-run extraction")
    await StageManager.initiate_stage(db, book_id, "llm_extraction")
    await StageManager.start_stage(db, book_id, "llm_extraction")
    await db.commit()

    from app.tasks.llm_tasks import run_llm_extraction

    run_llm_extraction.delay(str(job.id), str(book_id))

    return job


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------


def _purge_book_storage(book_id: UUID) -> None:
    """Remove all on-disk artifacts for a book."""
    base = Path(settings.storage_path).resolve()
    for sub in ("uploads", "thumbnails", "pages", "processed"):
        d = base / sub / str(book_id)
        if d.exists():
            try:
                shutil.rmtree(d)
            except OSError:
                logger.exception("Failed to remove %s", d)


def _purge_book_artifacts(book_id: UUID, *, keep_original: bool) -> None:
    """Remove page-derived artifacts; optionally keep the original PDF."""
    base = Path(settings.storage_path).resolve()
    for sub in ("thumbnails", "pages", "processed"):
        d = base / sub / str(book_id)
        if d.exists():
            try:
                shutil.rmtree(d)
            except OSError:
                logger.exception("Failed to remove %s", d)
    if not keep_original:
        pdf = storage.original_pdf_path(str(book_id))
        pdf.unlink(missing_ok=True)


def _storage_disk_usage_bytes() -> int:
    """Sum the size of every PDF under storage/uploads."""
    base = Path(settings.storage_path).resolve()
    uploads = base / "uploads"
    total = 0
    if uploads.exists():
        for pdf in uploads.rglob("original.pdf"):
            try:
                total += pdf.stat().st_size
            except OSError:
                continue
    return total
