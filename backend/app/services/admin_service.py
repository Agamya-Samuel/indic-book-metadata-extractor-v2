"""Admin operations: cross-book stats, delete, reset, re-run jobs.

These helpers keep DB transactions and storage cleanup together so the
HTTP layer stays thin.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.metadata import BookMetadata
from app.models.metadata_field_evidence import MetadataFieldEvidence
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services import storage

logger = logging.getLogger(__name__)


async def get_admin_stats(db: AsyncSession) -> dict:
    total_books = await db.scalar(select(func.count(Book.id))) or 0
    books_with_metadata = await db.scalar(select(func.count(BookMetadata.id))) or 0

    lang_result = await db.execute(
        select(Book.language, func.count(Book.id)).group_by(Book.language)
    )
    languages = {row[0]: row[1] for row in lang_result.all()}

    status_result = await db.execute(
        select(Book.status, func.count(Book.id)).group_by(Book.status)
    )
    statuses = {row[0]: row[1] for row in status_result.all()}

    queued = await db.scalar(
        select(func.count(Job.id)).where(Job.status == JobStatus.QUEUED)
    ) or 0
    running = await db.scalar(
        select(func.count(Job.id)).where(Job.status == JobStatus.RUNNING)
    ) or 0

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    failed_recent = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.FAILED,
            Job.created_at >= seven_days_ago,
        )
    ) or 0
    completed_recent = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.COMPLETED,
            Job.created_at >= seven_days_ago,
        )
    ) or 0

    disk_usage_bytes = _storage_disk_usage_bytes()
    disk_usage_mb = round(disk_usage_bytes / (1024 * 1024), 2)

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
        "disk_usage_mb": disk_usage_mb,
    }


async def list_admin_jobs(
    db: AsyncSession,
    status: str | None,
    job_type: str | None,
    book_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    query = select(Job, Book.title, Book.filename).outerjoin(
        Book, Job.book_id == Book.id
    )

    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)
    if book_id:
        query = query.where(Job.book_id == book_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Job.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    rows = (await db.execute(query)).all()

    items = []
    for job, book_title, book_filename in rows:
        items.append({
            "id": str(job.id),
            "book_id": str(job.book_id) if job.book_id else None,
            "book_title": book_title,
            "book_filename": book_filename or "(deleted book)",
            "job_type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_log": job.error_log,
        })

    return items, total


async def cancel_job(db: AsyncSession, job_id: UUID) -> Job:
    job = await db.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    if job.status not in (JobStatus.QUEUED, JobStatus.RUNNING):
        raise ValueError(f"Cannot cancel job in status '{job.status}'")
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    job.error_log = "Cancelled by admin"
    await db.commit()
    await db.refresh(job)
    return job


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
    for j in active_jobs.scalars().all():
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Book deleted by admin"
    await db.flush()

    await db.delete(book)
    await db.commit()

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
    for j in active_jobs.scalars().all():
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
    await db.refresh(book)

    # Clean page-derived artifacts on disk (keep the original PDF)
    _purge_book_artifacts(book_id, keep_original=True)

    return book


async def rerun_ocr(db: AsyncSession, book_id: UUID) -> Job:
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
    for j in active_jobs.scalars().all():
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Re-run OCR requested by admin"
    await db.flush()

    # Drop existing OCR results + processed images
    page_ids = [p.id for p in pages]
    await db.execute(delete(OcrResult).where(OcrResult.page_id.in_(page_ids)))
    await db.execute(delete(MetadataFieldEvidence).where(MetadataFieldEvidence.book_id == book_id))
    for p in pages:
        if p.processed_image_path:
            fp = Path(settings.storage_path) / p.processed_image_path
            fp.unlink(missing_ok=True)
        p.processed_image_path = None
        p.preprocessing_config = None
    # LLM outputs are stale once OCR changes; clear them too.
    await db.execute(delete(BookMetadata).where(BookMetadata.book_id == book_id))

    # Create new OCR job
    job = Job(
        book_id=book_id,
        job_type=JobType.OCR,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    book.status = BookStatus.OCR_RUNNING
    await db.commit()
    await db.refresh(job)

    from app.tasks.ocr_tasks import preprocess_pages_for_book
    preprocess_pages_for_book.delay(str(job.id), str(book_id), book.language)

    return job


async def rerun_extraction(db: AsyncSession, book_id: UUID) -> Job:
    """Re-run LLM extraction on existing OCR outputs with default config."""
    book = await db.get(Book, book_id)
    if book is None:
        raise LookupError("Book not found")

    if book.status not in (BookStatus.OCR_COMPLETE, BookStatus.COMPLETE):
        raise ValueError(
            f"Book status must be 'ocr_complete' or 'complete', got '{book.status}'"
        )

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id))
    pages = pages_result.scalars().all()
    if not pages:
        raise ValueError("No pages selected for this book")

    page_ids = [p.id for p in pages]
    ocr_results = await db.execute(
        select(OcrResult).where(OcrResult.page_id.in_(page_ids))
    )
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
        job_type=JobType.LLM,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

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