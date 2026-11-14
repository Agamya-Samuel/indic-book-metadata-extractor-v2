"""Celery task: render selected PDF pages into page images.

Page extraction used to run synchronously inside ``POST /books/{id}/pages``,
which blocked the request for the whole render and gave the user no cancel or
progress. It now creates a PAGE_EXTRACTION job and this task renders pages
one-by-one, updating progress and honouring cancellation.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import newrelic.agent
from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus
from app.models.page import Page
from app.services import notification_service, pdf_service, preprocessing, storage
from app.services.sse_service import event_id, publish_sync
from app.services.stage_manager import StageManager
from app.tasks.async_utils import run_async, run_async_threadsafe
from app.tasks.cancellation import is_superseded_async
from app.tasks.pipeline_lock import refresh as refresh_pipeline_lock
from app.tasks.pipeline_lock import single_book_task
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _publish_progress(book_id: uuid.UUID, job_id: uuid.UUID, progress: float) -> None:
    publish_sync(
        book_id,
        {
            "id": event_id("job-progress"),
            "type": "job.progress",
            "book_id": str(book_id),
            "job_id": str(job_id),
            "job_type": "page_extraction",
            "progress": progress,
        },
    )


def _publish_terminal(
    book_id: uuid.UUID,
    job_id: uuid.UUID,
    status: str,
    error_log: str | None = None,
) -> None:
    publish_sync(
        book_id,
        {
            "id": event_id(f"job-{status}"),
            "type": "job.terminal",
            "book_id": str(book_id),
            "job_id": str(job_id),
            "status": status,
            "error_log": error_log,
        },
    )


def _is_cancelled(job_id: uuid.UUID) -> bool:
    async def _do():
        async with async_session_factory() as db:
            status = (
                await db.execute(select(Job.status).where(Job.id == job_id))
            ).scalar_one_or_none()
            return status is None or status == JobStatus.CANCELLED

    try:
        return bool(run_async_threadsafe(_do()))
    except Exception:
        return False


def _update_progress(
    job_id: uuid.UUID, book_id: uuid.UUID, done: int, total: int
) -> None:
    pct = round(done / total * 100, 2) if total else 0.0

    async def _do():
        async with async_session_factory() as db:
            job = (
                await db.execute(
                    select(Job).where(Job.id == job_id).with_for_update()
                )
            ).scalar_one_or_none()
            if job is None or job.status == JobStatus.CANCELLED:
                return None
            job.last_progress_at = datetime.now(timezone.utc)
            if pct > (job.progress or 0.0):
                job.progress = pct
            await db.commit()
            return job.progress or 0.0

    try:
        value = run_async_threadsafe(_do())
    except Exception:
        logger.debug("Progress update failed for page job %s", job_id, exc_info=True)
        return
    if value is not None:
        refresh_pipeline_lock(str(job_id))
        _publish_progress(book_id, job_id, value)


def _insert_page(book_id: uuid.UUID, page_number: int, rel_path: str) -> None:
    async def _do():
        async with async_session_factory() as db:
            existing = (
                await db.execute(
                    select(Page).where(
                        Page.book_id == book_id, Page.page_number == page_number
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.image_path = rel_path
                existing.preprocessing_config = preprocessing.DEFAULT_PREPROCESSING_CONFIG
                existing.processed_image_path = None
            else:
                db.add(
                    Page(
                        book_id=book_id,
                        page_number=page_number,
                        image_path=rel_path,
                        preprocessing_config=preprocessing.DEFAULT_PREPROCESSING_CONFIG,
                    )
                )
            await db.commit()

    run_async_threadsafe(_do())


def _fail(job_id: uuid.UUID, book_id: uuid.UUID, message: str) -> None:
    async def _do():
        async with async_session_factory() as db:
            job = (
                await db.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if job is not None and job.status not in (
                JobStatus.CANCELLED,
                JobStatus.COMPLETED,
            ):
                job.status = JobStatus.FAILED
                job.error_log = message[:2000]
                job.completed_at = datetime.now(timezone.utc)
            try:
                await StageManager.fail_stage(
                    db, book_id, "page_selection", message[:2000]
                )
            except Exception:
                logger.debug("Could not fail page_selection stage", exc_info=True)
            await db.commit()
            if job is not None and job.status == JobStatus.FAILED:
                book = await db.get(Book, book_id)
                notification_id = await notification_service.notify_job_terminal(
                    db, job=job, book=book, status=JobStatus.FAILED
                )
                await notification_service.notify_and_deliver(db, [notification_id])

    try:
        run_async_threadsafe(_do())
    except Exception:
        logger.exception("Could not mark page extraction job %s failed", job_id)
    _publish_terminal(book_id, job_id, "failed", message)


def _finalize(
    job_id: uuid.UUID,
    book_id: uuid.UUID,
    errors: list[str],
    total: int,
) -> None:
    async def _do():
        async with async_session_factory() as db:
            job = (
                await db.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if job is None:
                return None
            if job.status == JobStatus.CANCELLED:
                logger.info("Page extraction job %s was cancelled; not finalising", job_id)
                return None
            if await is_superseded_async(db, job):
                logger.info("Page extraction job %s was superseded; not finalising", job_id)
                return None
            book = (
                await db.execute(select(Book).where(Book.id == book_id))
            ).scalar_one_or_none()
            page_count = (
                await db.execute(
                    select(func.count()).select_from(Page).where(Page.book_id == book_id)
                )
            ).scalar() or 0

            if page_count == 0:
                job.status = JobStatus.FAILED
                job.error_log = (
                    "No pages could be rendered:\n" + "\n".join(errors)
                    if errors
                    else "No pages were rendered"
                )[:2000]
                try:
                    await StageManager.fail_stage(
                        db, book_id, "page_selection", job.error_log
                    )
                except Exception:
                    logger.debug("Could not fail page_selection stage", exc_info=True)
            else:
                job.status = JobStatus.COMPLETED
                if errors:
                    job.error_log = ("Some pages failed:\n" + "\n".join(errors))[:2000]
                if book is not None:
                    book.status = BookStatus.PAGES_SELECTED
                try:
                    await StageManager.complete_stage(db, book_id, "page_selection")
                except Exception:
                    logger.exception("Could not complete page_selection stage")

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            terminal_status = job.status
            notification_id = await notification_service.notify_job_terminal(
                db, job=job, book=book, status=terminal_status
            )
            await notification_service.notify_and_deliver(db, [notification_id])
            return terminal_status, job.error_log, (book.status if book else None)

    try:
        result = run_async_threadsafe(_do())
    except Exception as exc:
        _fail(job_id, book_id, f"Page extraction failed: {exc}")
        return

    if result is None:
        return
    status, error_log, book_status = result
    _publish_terminal(book_id, job_id, status, error_log)
    if book_status is not None:
        publish_sync(
            book_id,
            {
                "id": event_id("book-status"),
                "type": "book.status_changed",
                "book_id": str(book_id),
                "status": book_status,
                "job_id": str(job_id),
            },
        )


@celery_app.task(
    bind=True,
    name="render_pages_for_book",
    acks_late=True,
    max_retries=2,
    default_retry_delay=15,
)
@newrelic.agent.background_task(name="Pages: Render", group="CeleryTask")
@single_book_task
def render_pages_for_book(
    self, job_id_str: str, book_id_str: str, page_numbers: list[int]
) -> None:
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)

    job_id = uuid.UUID(job_id_str)
    book_id = uuid.UUID(book_id_str)
    total = len(page_numbers)

    async def _start() -> bool:
        async with async_session_factory() as db:
            job = (
                await db.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id_str} not found")
            if job.status == JobStatus.CANCELLED:
                return False
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.last_progress_at = job.started_at
            if self.request.id:
                job.celery_task_id = self.request.id
            await db.commit()
            return True

    try:
        if not run_async(_start()):
            return
    except Exception as exc:
        logger.exception("Page extraction job %s setup failed", job_id_str)
        _fail(job_id, book_id, f"Page extraction failed: {exc}")
        return

    pdf_path = storage.original_pdf_path(book_id_str)
    if not pdf_path.exists():
        _fail(job_id, book_id, "Original PDF not found")
        return

    errors: list[str] = []
    for index, raw_page_number in enumerate(page_numbers, start=1):
        if _is_cancelled(job_id):
            logger.info("Page extraction job %s cancelled", job_id_str)
            return
        page_number = int(raw_page_number)
        try:
            output_path = storage.full_page_path(book_id_str, page_number)
            pdf_service.render_full_page(pdf_path, page_number, output_path)
            _insert_page(book_id, page_number, storage.relative(output_path))
        except Exception as exc:
            logger.error("Failed to render page %s: %s", page_number, exc)
            errors.append(f"Page {page_number}: {exc}")
        _update_progress(job_id, book_id, index, total)

    _finalize(job_id, book_id, errors, total)

# ---------------------------------------------------------------------------
# Bulk preprocessing: apply one config to every page of a book
# ---------------------------------------------------------------------------
def _store_preprocessed(
    page_id_str: str, config: dict, processed_rel: str
) -> None:
    async def _do():
        async with async_session_factory() as db:
            page = (
                await db.execute(select(Page).where(Page.id == uuid.UUID(page_id_str)))
            ).scalar_one_or_none()
            if page is None:
                return
            page.preprocessing_config = config
            page.processed_image_path = processed_rel
            await db.commit()

    run_async_threadsafe(_do())


def _finalize_bulk(job_id: uuid.UUID, errors: list[str]) -> None:
    async def _do():
        async with async_session_factory() as db:
            job = (
                await db.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if job is None or job.status == JobStatus.CANCELLED:
                return None
            if await is_superseded_async(db, job):
                logger.info("Bulk preprocessing job %s was superseded", job_id)
                return None
            job.status = JobStatus.FAILED if errors else JobStatus.COMPLETED
            if errors:
                job.error_log = ("Some pages failed:\n" + "\n".join(errors))[:2000]
            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return job.status, job.error_log, job.book_id

    try:
        result = run_async_threadsafe(_do())
    except Exception:
        logger.exception("Could not finalize bulk preprocessing job %s", job_id)
        return
    if result is None:
        return
    status, error_log, book_id = result
    if book_id is not None:
        _publish_terminal(book_id, job_id, status, error_log)


@celery_app.task(
    bind=True,
    name="apply_preprocessing_bulk",
    acks_late=True,
    max_retries=1,
    default_retry_delay=15,
)
@newrelic.agent.background_task(name="Preprocessing: Bulk Apply", group="CeleryTask")
@single_book_task
def apply_preprocessing_bulk(
    self, job_id_str: str, book_id_str: str, config: dict
) -> None:
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)

    job_id = uuid.UUID(job_id_str)
    book_id = uuid.UUID(book_id_str)

    async def _setup():
        async with async_session_factory() as db:
            job = (
                await db.execute(select(Job).where(Job.id == job_id))
            ).scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id_str} not found")
            if job.status == JobStatus.CANCELLED:
                return None
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.last_progress_at = job.started_at
            if self.request.id:
                job.celery_task_id = self.request.id
            await db.commit()
            rows = (
                await db.execute(
                    select(Page)
                    .where(Page.book_id == book_id)
                    .order_by(Page.page_number)
                )
            ).scalars().all()
            return [(str(p.id), p.page_number, p.image_path) for p in rows]

    try:
        pages = run_async(_setup())
    except Exception as exc:
        logger.exception("Bulk preprocessing job %s setup failed", job_id_str)
        _fail(job_id, book_id, f"Bulk preprocessing failed: {exc}")
        return

    if not pages:
        _fail(job_id, book_id, "No pages selected for this book")
        return

    total = len(pages)
    errors: list[str] = []
    for index, (page_id_str, page_number, image_rel) in enumerate(pages, start=1):
        if _is_cancelled(job_id):
            logger.info("Bulk preprocessing job %s cancelled", job_id_str)
            return
        try:
            if not image_rel:
                raise ValueError("page has no source image")
            source = Path(settings.storage_path) / image_rel
            if not source.exists():
                raise ValueError("source image file missing")
            output_path = storage.processed_image_path(book_id_str, page_number)
            preprocessing.run_pipeline(source, config, output_path)
            _store_preprocessed(page_id_str, config, storage.relative(output_path))
        except Exception as exc:
            logger.error("Bulk preprocessing failed for page %s: %s", page_number, exc)
            errors.append(f"Page {page_number}: {exc}")
        _update_progress(job_id, book_id, index, total)

    _finalize_bulk(job_id, errors)
