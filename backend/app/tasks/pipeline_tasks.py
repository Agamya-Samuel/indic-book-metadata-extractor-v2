"""
Pipeline orchestrator: a single Celery task that drives a book through every
automated stage (page selection -> OCR -> LLM extraction) and emits SSE
events for each transition.

The orchestrator is **idempotent** — it inspects ``book.status`` on entry
and resumes from wherever the book currently is. A retry from any stage
just re-dispatches this task; already-completed stages are skipped.

The task is the only entry point that turns an uploaded book into a
``AWAITING_REVIEW`` book. It is dispatched from:

* ``POST /api/books/upload`` — fresh upload
* ``POST /api/books/{id}/retry-extraction`` — re-run LLM
* ``POST /api/admin/books/{id}/reset`` — re-run the whole chain
* ``POST /api/admin/books/{id}/rerun-ocr`` — re-run OCR (then LLM)
* ``POST /api/admin/books/{id}/rerun-extraction`` — re-run LLM

Real-time progress is delivered via the SSE service (``publish_sync``),
which fans out to connected clients on the ``book:{id}:events`` channel.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import newrelic.agent
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.page import Page
from app.services import pdf_service, storage
from app.services.sse_service import event_id, publish_sync
from app.tasks.async_utils import run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# How long the orchestrator will wait between polls for a sub-job to reach
# a terminal state before declaring the stage failed.
_STAGE_POLL_INTERVAL_SECONDS = 2.0
_STAGE_POLL_TIMEOUT_SECONDS = 60 * 60  # 1 hour per stage


def _publish(book_id: uuid.UUID, event: dict[str, Any]) -> None:
    publish_sync(book_id, event)


def _load_book(book_id: uuid.UUID) -> Book | None:
    async def _do():
        async with async_session_factory() as db:
            result = await db.execute(select(Book).where(Book.id == book_id))
            return result.scalar_one_or_none()

    return run_async(_do())


def _load_latest_job(book_id: uuid.UUID, job_type: JobType) -> Job | None:
    async def _do():
        async with async_session_factory() as db:
            result = await db.execute(
                select(Job)
                .where(Job.book_id == book_id, Job.job_type == job_type)
                .order_by(Job.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    return run_async(_do())


def _set_book_status(book_id: uuid.UUID, status: BookStatus) -> None:
    async def _do():
        async with async_session_factory() as db:
            result = await db.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            if book is None:
                return
            book.status = status
            await db.commit()

    run_async(_do())


def _select_all_pages(book_id: uuid.UUID, total_pages: int) -> int:
    """Render and register all pages of a book. Returns the count."""
    async def _do():
        async with async_session_factory() as db:
            existing = await db.execute(select(Page).where(Page.book_id == book_id))
            for p in existing.scalars().all():
                if p.image_path:
                    fp = Path(settings.storage_path) / p.image_path
                    fp.unlink(missing_ok=True)
                await db.delete(p)
            await db.flush()

            pdf_path = storage.original_pdf_path(str(book_id))
            if not pdf_path.exists():
                raise RuntimeError(f"Original PDF missing for book {book_id}")

            rendered = 0
            for pn in range(1, total_pages + 1):
                out = storage.full_page_path(str(book_id), pn)
                pdf_service.render_full_page(pdf_path, pn, out)
                page = Page(
                    book_id=book_id,
                    page_number=pn,
                    image_path=storage.relative(out),
                )
                db.add(page)
                rendered += 1

            result = await db.execute(select(Book).where(Book.id == book_id))
            book = result.scalar_one_or_none()
            if book is not None:
                book.status = BookStatus.PAGES_SELECTED
            await db.commit()
            return rendered

    return run_async(_do())


def _create_ocr_job(book_id: uuid.UUID) -> Job:
    async def _do():
        async with async_session_factory() as db:
            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()
            if book is None:
                raise RuntimeError(f"Book {book_id} not found")
            book.status = BookStatus.OCR_RUNNING
            job = Job(
                book_id=book_id,
                job_type=JobType.OCR,
                status=JobStatus.QUEUED,
                progress=0.0,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            return job

    return run_async(_do())


def _create_llm_job(book_id: uuid.UUID) -> Job:
    async def _do():
        async with async_session_factory() as db:
            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()
            if book is None:
                raise RuntimeError(f"Book {book_id} not found")
            book.status = BookStatus.LLM_RUNNING
            job = Job(
                book_id=book_id,
                job_type=JobType.LLM,
                status=JobStatus.QUEUED,
                progress=0.0,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            return job

    return run_async(_do())


def _wait_for_terminal(book_id: uuid.UUID, job_id: uuid.UUID) -> str:
    """Block (Celery worker thread) until the job reaches a terminal state.

    Returns the final status string. Raises ``TimeoutError`` if the stage
    does not complete within ``_STAGE_POLL_TIMEOUT_SECONDS``.
    """
    deadline = time.monotonic() + _STAGE_POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        async def _check():
            async with async_session_factory() as db:
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()
                if job is None:
                    return None
                return job.status

        status = run_async(_check())
        if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return status
        time.sleep(_STAGE_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Job {job_id} did not reach terminal state in time")




@celery_app.task(
    bind=True,
    name="process_book_pipeline",
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
@newrelic.agent.background_task(name="Pipeline: Book Orchestration", group="CeleryTask")
def process_book_pipeline(self, book_id_str: str, language: str) -> None:
    """Drive a book through every automated stage end-to-end.

    Idempotent: re-dispatching the same task for a book picks up from the
    current ``book.status`` rather than restarting from the beginning.
    """
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    run_async(_process_book_pipeline_async(book_id_str, language))


async def _process_book_pipeline_async(book_id_str: str, language: str) -> None:
    """Async body of the orchestrator. Exposed for tests."""
    try:
        book_uuid = uuid.UUID(book_id_str)
    except (TypeError, ValueError):
        logger.error("process_book_pipeline received invalid book_id %r", book_id_str)
        return

    book = await _load_book_async(book_uuid)
    if book is None:
        logger.error("process_book_pipeline: book %s not found", book_id_str)
        return

    _publish(
        book_uuid,
        {
            "id": event_id("pipeline-started"),
            "type": "pipeline.started",
            "book_id": book_id_str,
            "language": language,
            "from_status": book.status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    try:
        if book.status == BookStatus.UPLOADED:
            await _stage_pages_selected_async(book_uuid)
            book = await _load_book_async(book_uuid) or book

        if book.status in (BookStatus.PAGES_SELECTED, BookStatus.OCR_RUNNING):
            await _stage_ocr_async(book_uuid, language)
            book = await _load_book_async(book_uuid) or book

        if book.status in (BookStatus.OCR_COMPLETE, BookStatus.LLM_RUNNING):
            await _stage_llm_async(book_uuid)
            book = await _load_book_async(book_uuid) or book

        if book is not None and book.status == BookStatus.AWAITING_REVIEW:
            _publish(
                book_uuid,
                {
                    "id": event_id("pipeline-completed"),
                    "type": "pipeline.completed",
                    "book_id": book_id_str,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline for book %s failed: %s", book_id_str, exc)
        _publish(
            book_uuid,
            {
                "id": event_id("pipeline-failed"),
                "type": "pipeline.failed",
                "book_id": book_id_str,
                "error": str(exc),
            },
        )
        # Re-raise so Celery retry/backoff can apply.
        raise


async def _load_book_async(book_id: uuid.UUID) -> Book | None:
    async with async_session_factory() as db:
        result = await db.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()


async def _stage_pages_selected_async(book_id: uuid.UUID) -> None:
    book = await _load_book_async(book_id)
    if book is None or book.total_pages is None:
        raise RuntimeError(f"Book {book_id} not found or has no total_pages")
    if book.status != BookStatus.UPLOADED:
        return
    _publish(
        book_id,
        {
            "id": event_id("pipeline-stage-started"),
            "type": "pipeline.stage_started",
            "book_id": str(book_id),
            "stage": "pages_selected",
        },
    )
    try:
        count = _select_all_pages(book_id, book.total_pages)
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-completed"),
                "type": "pipeline.stage_completed",
                "book_id": str(book_id),
                "stage": "pages_selected",
                "selected_count": count,
            },
        )
    except Exception as exc:  # noqa: BLE001
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-failed"),
                "type": "pipeline.stage_failed",
                "book_id": str(book_id),
                "stage": "pages_selected",
                "error": str(exc),
            },
        )
        raise


async def _stage_ocr_async(book_id: uuid.UUID, language: str) -> Job:
    book = await _load_book_async(book_id)
    if book is None:
        raise RuntimeError(f"Book {book_id} not found")

    if book.status == BookStatus.OCR_COMPLETE:
        latest = _load_latest_job(book_id, JobType.OCR)
        if latest is not None and latest.status == JobStatus.COMPLETED:
            return latest

    _publish(
        book_id,
        {
            "id": event_id("pipeline-stage-started"),
            "type": "pipeline.stage_started",
            "book_id": str(book_id),
            "stage": "ocr",
        },
    )
    try:
        job = _create_ocr_job(book_id)
    except Exception as exc:  # noqa: BLE001
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-failed"),
                "type": "pipeline.stage_failed",
                "book_id": str(book_id),
                "stage": "ocr",
                "error": str(exc),
            },
        )
        raise

    from app.tasks.ocr_tasks import preprocess_pages_for_book

    preprocess_pages_for_book.delay(str(job.id), str(book_id), language)

    status = _wait_for_terminal(book_id, job.id)
    if status != JobStatus.COMPLETED:
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-failed"),
                "type": "pipeline.stage_failed",
                "book_id": str(book_id),
                "stage": "ocr",
                "job_id": str(job.id),
                "status": status,
            },
        )
        raise RuntimeError(f"OCR job {job.id} ended with status {status}")
    _publish(
        book_id,
        {
            "id": event_id("pipeline-stage-completed"),
            "type": "pipeline.stage_completed",
            "book_id": str(book_id),
            "stage": "ocr",
            "job_id": str(job.id),
        },
    )
    return job


async def _stage_llm_async(book_id: uuid.UUID) -> Job:
    book = await _load_book_async(book_id)
    if book is None:
        raise RuntimeError(f"Book {book_id} not found")

    if book.status in (BookStatus.AWAITING_REVIEW, BookStatus.COMPLETE):
        latest = _load_latest_job(book_id, JobType.LLM)
        if latest is not None and latest.status == JobStatus.COMPLETED:
            return latest

    _publish(
        book_id,
        {
            "id": event_id("pipeline-stage-started"),
            "type": "pipeline.stage_started",
            "book_id": str(book_id),
            "stage": "llm",
        },
    )
    try:
        job = _create_llm_job(book_id)
    except Exception as exc:  # noqa: BLE001
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-failed"),
                "type": "pipeline.stage_failed",
                "book_id": str(book_id),
                "stage": "llm",
                "error": str(exc),
            },
        )
        raise

    from app.tasks.llm_tasks import run_llm_extraction

    run_llm_extraction.delay(
        str(job.id),
        str(book_id),
    )

    status = _wait_for_terminal(book_id, job.id)
    if status != JobStatus.COMPLETED:
        _publish(
            book_id,
            {
                "id": event_id("pipeline-stage-failed"),
                "type": "pipeline.stage_failed",
                "book_id": str(book_id),
                "stage": "llm",
                "job_id": str(job.id),
                "status": status,
            },
        )
        raise RuntimeError(f"LLM job {job.id} ended with status {status}")
    _publish(
        book_id,
        {
            "id": event_id("pipeline-stage-completed"),
            "type": "pipeline.stage_completed",
            "book_id": str(book_id),
            "stage": "llm",
            "job_id": str(job.id),
        },
    )
    return job
