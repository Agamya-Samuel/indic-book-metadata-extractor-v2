import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import newrelic.agent
from sqlalchemy import exc as sa_exc, select
from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services import ocr_service, ocr_postprocess, preprocessing, storage
from app.services.sse_service import event_id, publish_sync
from app.tasks.async_utils import run_async, run_async_threadsafe
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core page processing (async)
# ---------------------------------------------------------------------------
async def _process_page_async(page_id_str: str, book_id_str: str, language: str) -> dict:
    """Process a single page: run preprocessing (if needed), OCR, and persist results."""
    async with async_session_factory() as db:
        result = await db.execute(select(Page).where(Page.id == uuid.UUID(page_id_str)))
        page = result.scalar_one_or_none()
        if page is None:
            raise ValueError(f"Page {page_id_str} not found")

        image_rel = page.processed_image_path or page.image_path
        if not image_rel:
            raise ValueError(f"Page {page_id_str} has no image")

        image_path = Path(settings.storage_path) / image_rel
        if not image_path.exists():
            raise ValueError(f"Image file not found: {image_path}")

        config = page.preprocessing_config
        if config and not page.processed_image_path:
            output_path = storage.processed_image_path(book_id_str, page.page_number)
            preprocessing.run_pipeline(image_path, config, output_path)
            page.processed_image_path = storage.relative(output_path)
            await db.flush()
            image_path = output_path

        ocr_data = ocr_service.run_ocr(image_path, language, page_position=page.page_number - 1)

        words = ocr_data["words"]
        if settings.ocr_low_conf_retry:
            words = ocr_service.retry_low_confidence_words(
                image_path, words, language, threshold=settings.ocr_low_conf_threshold
            )

        raw_text = ocr_data["full_text"]
        cleaned_text = raw_text
        corrections: list[dict] = []
        if settings.ocr_postprocess:
            cleaned_text, corrections = ocr_postprocess.normalize_text(raw_text, language)

        ocr_result = await db.execute(
            select(OcrResult).where(OcrResult.page_id == page.id)
        )
        existing = ocr_result.scalar_one_or_none()

        if existing:
            existing.raw_text = raw_text
            existing.bounding_boxes = {"words": words}
            existing.confidence = ocr_data["avg_confidence"]
            existing.language_detected = language
            existing.cleaned_text = cleaned_text
            existing.corrections = {"rules": corrections}
        else:
            new_result = OcrResult(
                page_id=page.id,
                raw_text=raw_text,
                bounding_boxes={"words": words},
                confidence=ocr_data["avg_confidence"],
                language_detected=language,
                cleaned_text=cleaned_text,
                corrections={"rules": corrections},
            )
            db.add(new_result)

        await db.commit()
        return {
            "page_id": page_id_str,
            "page_number": page.page_number,
            "success": True,
        }


def _process_page_threadsafe(page_id_str: str, book_id_str: str, language: str) -> dict:
    """Thread-safe wrapper: creates a fresh event loop for each call."""
    return run_async_threadsafe(_process_page_async(page_id_str, book_id_str, language))


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
def _update_job_progress(
    job_id_str: str, completed: int, total: int, book_id_str: str | None = None
) -> None:
    """Update job progress percentage in the database atomically.

    Takes a row-level lock so concurrent progress updates serialise and
    never regress the value. Publishes a ``job.progress`` SSE event so
    connected clients see live updates without polling.
    """

    async def _do():
        book_id: uuid.UUID | None = None
        if book_id_str:
            try:
                book_id = uuid.UUID(book_id_str)
            except (TypeError, ValueError):
                book_id = None

        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            new_progress = round((completed / total) * 100, 1) if total else 0.0
            # Lock the row so concurrent progress updates serialise and we
            # never regress the value.
            job_result = await db.execute(
                select(Job).where(Job.id == job_id).with_for_update()
            )
            job = job_result.scalar_one_or_none()
            if not job:
                return
            if new_progress > (job.progress or 0.0):
                job.progress = new_progress
                await db.commit()
                progress_pct = new_progress
            else:
                progress_pct = job.progress or 0.0
            if book_id is None and job.book_id is not None:
                book_id = job.book_id
            jtype = job.job_type

        if book_id is not None:
            publish_sync(
                book_id,
                {
                    "id": event_id("job-progress"),
                    "type": "job.progress",
                    "book_id": str(book_id),
                    "job_id": job_id_str,
                    "job_type": jtype,
                    "progress": progress_pct,
                },
            )

    try:
        run_async_threadsafe(_do())
    except Exception:
        # Progress is best-effort; logging only.
        logger.debug("Progress update failed for job %s", job_id_str, exc_info=True)


def _publish_book_status(book_id: uuid.UUID, status: str, job_id: uuid.UUID | None = None) -> None:
    publish_sync(
        book_id,
        {
            "id": event_id("book-status"),
            "type": "book.status_changed",
            "book_id": str(book_id),
            "status": status,
            "job_id": str(job_id) if job_id else None,
        },
    )


def _publish_job_terminal(
    book_id: uuid.UUID, job_id: uuid.UUID, status: str, error_log: str | None = None
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


def _has_active_job_for_book(book_id: uuid.UUID) -> bool:
    """Return True if the book already has a queued/running OCR or PREPROCESSING job."""

    async def _check():
        async with async_session_factory() as db:
            result = await db.execute(
                select(Job.id)
                .where(
                    Job.book_id == book_id,
                    Job.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)),
                    Job.job_type.in_(
                        (JobType.OCR, JobType.PREPROCESSING)
                    ),
                )
                .limit(1)
            )
            return result.scalar_one_or_none() is not None

    try:
        return bool(run_async_threadsafe(_check()))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Preprocessing phase task
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="preprocess_pages_for_book",
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Preprocessing Phase", group="CeleryTask")
def preprocess_pages_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Preprocess all pages that need it, then chain into OCR.

    On failure, the preprocessing job is marked FAILED and OCR is **not**
    dispatched — downstream code must retry the job explicitly.
    """
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)

    book_uuid = uuid.UUID(book_id_str)
    if _has_active_job_for_book(book_uuid):
        logger.info(
            "Skipping preprocessing for book %s — another active job exists",
            book_id_str,
        )
        return

    async def _run():
        async with async_session_factory() as db:
            job_uuid = uuid.UUID(job_id_str)
            job_result = await db.execute(
                select(Job).where(Job.id == job_uuid).with_for_update()
            )
            job = job_result.scalar_one_or_none()
            if job:
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(timezone.utc)
                if self.request.id and not job.celery_task_id:
                    job.celery_task_id = self.request.id
                await db.commit()

            pages_result = await db.execute(
                select(Page).where(Page.book_id == book_uuid).order_by(Page.page_number)
            )
            pages = pages_result.scalars().all()

            preprocessed = 0
            for page in pages:
                config = page.preprocessing_config
                if config and not page.processed_image_path:
                    image_rel = page.image_path
                    if not image_rel:
                        continue
                    image_path = Path(settings.storage_path) / image_rel
                    if not image_path.exists():
                        continue
                    output_path = storage.processed_image_path(book_id_str, page.page_number)
                    preprocessing.run_pipeline(image_path, config, output_path)
                    page.processed_image_path = storage.relative(output_path)
                    preprocessed += 1

            if preprocessed > 0:
                await db.commit()
            return preprocessed

    try:
        count = run_async(_run())
        logger.info("Preprocessed %d pages for book %s, chaining to OCR", count, book_id_str)
    except (ConnectionError, TimeoutError, OSError, sa_exc.OperationalError) as exc:
        # Transient: let Celery retry.
        logger.warning("Transient preprocessing error for book %s: %s", book_id_str, exc)
        raise self.retry(exc=exc)
    except Exception as e:
        logger.error("Preprocessing failed for book %s: %s", book_id_str, e)
        _mark_job_failed(
            job_id_str,
            book_uuid,
            f"Preprocessing failed: {e}",
        )
        return

    run_ocr_for_book.delay(job_id_str, book_id_str, language)


# ---------------------------------------------------------------------------
# Book-level OCR: processes pages sequentially with per-page progress updates
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="run_ocr_for_book",
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(ConnectionError, TimeoutError, OSError, sa_exc.OperationalError),
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Book Orchestration", group="CeleryTask")
def run_ocr_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Run OCR sequentially for every page of a book, updating progress after each page."""
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)
    newrelic.agent.add_custom_attribute("language", language)

    async def _setup():
        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            book_id = uuid.UUID(book_id_str)

            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                raise ValueError(f"Job {job_id_str} not found")

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.celery_task_id = self.request.id
            await db.commit()

            pages_result = await db.execute(
                select(Page).where(Page.book_id == book_id).order_by(Page.page_number)
            )
            pages = pages_result.scalars().all()

            if not pages:
                job.status = JobStatus.FAILED
                job.error_log = "No pages found for book"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return None

            return [str(p.id) for p in pages]

    try:
        page_ids = run_async(_setup())
        if page_ids is None:
            return

        total_pages = len(page_ids)
        errors: list[str] = []
        completed = 0
        avg_conf_sum = 0.0
        avg_conf_count = 0
        started = datetime.now(timezone.utc)

        for page_id in page_ids:
            try:
                _process_page_threadsafe(page_id, book_id_str, language)
                ocr_row_result = run_async_threadsafe(
                    _capture_page_confidence(page_id)
                )
                if ocr_row_result is not None:
                    avg_conf_sum += ocr_row_result
                    avg_conf_count += 1
            except Exception as e:
                logger.error("OCR failed for page %s: %s", page_id, e)
                errors.append(f"Page {page_id}: {e}")

            completed += 1
            _update_job_progress(job_id_str, completed, total_pages, book_id_str)

        avg_confidence = (
            round(avg_conf_sum / avg_conf_count, 2) if avg_conf_count else None
        )
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        from app.services.metrics import record_ocr_completion

        record_ocr_completion(
            book_id_str,
            avg_confidence or 0.0,
            completed - len(errors),
            duration,
        )

        _finalize_job(job_id_str, book_id_str, total_pages, errors)

    except (ConnectionError, TimeoutError, OSError, sa_exc.OperationalError) as exc:
        logger.warning("Transient OCR error for job %s, will retry: %s", job_id_str, exc)
        raise
    except Exception as e:
        logger.error("OCR book job %s setup failed: %s", job_id_str, e)
        _mark_job_failed(job_id_str, uuid.UUID(book_id_str), str(e))
        raise


async def _capture_page_confidence(page_id_str: str) -> float | None:
    """Return the most-recent OcrResult confidence for a page, or None."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(OcrResult).where(OcrResult.page_id == uuid.UUID(page_id_str))
        )
        row = result.scalar_one_or_none()
        return row.confidence if row and row.confidence is not None else None


def _finalize_job(job_id_str: str, book_id_str: str, total_pages: int, errors: list[str]) -> None:
    """Finalize the job after the sequential OCR loop completes.

    Sets job status, progress, completion timestamp, and updates the book's
    OCR status based on how many pages failed. Emits SSE events for the
    terminal job status and the book status transition.

    When ANY page fails the book is kept in PAGES_SELECTED so the user
    knows the OCR was partial and can re-run after fixing pages.
    """

    async def _do():
        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            book_id = uuid.UUID(book_id_str)

            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                return

            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()

            if errors and len(errors) == total_pages:
                job.status = JobStatus.FAILED
                job.error_log = "All pages failed:\n" + "\n".join(errors)
                if book:
                    book.status = BookStatus.PAGES_SELECTED
            elif errors:
                job.status = JobStatus.COMPLETED
                job.error_log = "Some pages failed:\n" + "\n".join(errors)
                if book:
                    # Partial OCR — keep the book in PAGES_SELECTED so the
                    # user must explicitly proceed.
                    book.status = BookStatus.PAGES_SELECTED
            else:
                job.status = JobStatus.COMPLETED
                if book:
                    book.status = BookStatus.OCR_COMPLETE

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            terminal_status = job.status
            error_log = job.error_log
            new_book_status = book.status if book else None

        _publish_job_terminal(book_id, job_id, terminal_status, error_log)
        if new_book_status is not None:
            _publish_book_status(book_id, new_book_status, job_id)

    try:
        run_async_threadsafe(_do())
    except Exception as e:
        logger.error("OCR book finalization failed for %s: %s", job_id_str, e)
        _mark_job_failed(job_id_str, uuid.UUID(book_id_str), str(e))


def _mark_job_failed(job_id_str: str, book_id: uuid.UUID, error: str):
    """Mark a job as failed in the database and publish a terminal SSE event."""

    async def _do():
        async with async_session_factory() as db:
            job_result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id_str))
            )
            job = job_result.scalar_one_or_none()
            if not job:
                return
            job.status = JobStatus.FAILED
            job.error_log = error
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

        _publish_job_terminal(book_id, uuid.UUID(job_id_str), JobStatus.FAILED, error)

    try:
        run_async(_do())
    except Exception as e:
        logger.error("Failed to mark job %s as FAILED: %s", job_id_str, e)
