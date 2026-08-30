import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import newrelic.agent
from sqlalchemy import exc as sa_exc, select
from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services import ocr_service, preprocessing, storage
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

        ocr_result = await db.execute(
            select(OcrResult).where(OcrResult.page_id == page.id)
        )
        existing = ocr_result.scalar_one_or_none()

        if existing:
            existing.raw_text = ocr_data["full_text"]
            existing.bounding_boxes = {"words": ocr_data["words"]}
            existing.confidence = ocr_data["avg_confidence"]
            existing.language_detected = language
        else:
            new_result = OcrResult(
                page_id=page.id,
                raw_text=ocr_data["full_text"],
                bounding_boxes={"words": ocr_data["words"]},
                confidence=ocr_data["avg_confidence"],
                language_detected=language,
            )
            db.add(new_result)

        await db.commit()
        return {
            "page_id": page_id_str,
            "page_number": page.page_number,
            "success": True,
        }


def _process_page(page_id_str: str, book_id_str: str, language: str) -> dict:
    """Synchronous wrapper for single-page task (uses the persistent worker loop)."""
    return run_async(_process_page_async(page_id_str, book_id_str, language))


def _process_page_threadsafe(page_id_str: str, book_id_str: str, language: str) -> dict:
    """Thread-safe wrapper: creates a fresh event loop for each call."""
    return run_async_threadsafe(_process_page_async(page_id_str, book_id_str, language))


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------
def _update_job_progress(
    job_id_str: str, completed: int, total: int, book_id_str: str | None = None
) -> None:
    """Update job progress percentage in the database.

    Uses a thread-safe async wrapper since this may be called from
    :class:`~concurrent.futures.ThreadPoolExecutor` threads.
    Also publishes a ``job.progress`` SSE event so connected clients see
    live updates without polling.
    """
    async def _do():
        book_id: uuid.UUID | None = None
        if book_id_str:
            try:
                book_id = uuid.UUID(book_id_str)
            except (TypeError, ValueError):
                book_id = None
        async with async_session_factory() as db:
            job_result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id_str))
            )
            job = job_result.scalar_one_or_none()
            if not job:
                return
            job.progress = round((completed / total) * 100, 1)
            if book_id is None and job.book_id is not None:
                book_id = job.book_id
            await db.commit()
            progress_pct = job.progress
            jid = job.id
            bkid = book_id
            jtype = job.job_type

        if bkid is not None:
            publish_sync(
                bkid,
                {
                    "id": event_id("job-progress"),
                    "type": "job.progress",
                    "book_id": str(bkid),
                    "job_id": str(jid),
                    "job_type": jtype,
                    "progress": progress_pct,
                },
            )

    run_async_threadsafe(_do())


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


# ---------------------------------------------------------------------------
# Preprocessing phase task
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="preprocess_pages_for_book",
    max_retries=1,
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Preprocessing Phase", group="CeleryTask")
def preprocess_pages_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Preprocess all pages that need it, then chain into OCR."""
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)

    async def _run():
        async with async_session_factory() as db:
            book_id = uuid.UUID(book_id_str)
            pages_result = await db.execute(
                select(Page).where(Page.book_id == book_id).order_by(Page.page_number)
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
    except Exception as e:
        logger.error("Preprocessing failed for book %s: %s", book_id_str, e)

    run_ocr_for_book.delay(job_id_str, book_id_str, language)


# ---------------------------------------------------------------------------
# Single-page OCR task
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="run_ocr_for_page",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Single Page", group="CeleryTask")
def run_ocr_for_page(self, page_id_str: str, book_id_str: str, language: str):
    """Run OCR on a single page. Retries up to 3 times on transient errors."""
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("page_id", page_id_str)
    newrelic.agent.add_custom_attribute("language", language)

    try:
        return _process_page(page_id_str, book_id_str, language)
    except (ConnectionError, TimeoutError, OSError, sa_exc.OperationalError) as exc:
        logger.warning("Transient error for page %s, retrying: %s", page_id_str, exc)
        raise self.retry(exc=exc)
    except Exception as e:
        logger.error("OCR failed for page %s: %s", page_id_str, e)
        return {
            "page_id": page_id_str,
            "success": False,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Batched-page OCR task with thread-based parallelism
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="run_ocr_for_page_batch",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Page Batch", group="CeleryTask")
def run_ocr_for_page_batch(
    self,
    page_id_strs: list,
    book_id_str: str,
    language: str,
    job_id_str: str | None = None,
    total_pages: int | None = None,
):
    """Run OCR on a batch of pages using thread-based parallelism.

    Uses :class:`~concurrent.futures.ThreadPoolExecutor` to process multiple
    pages concurrently within a single Celery worker process.  Since
    ``pytesseract`` spawns a subprocess for each call (releasing the GIL),
    threads achieve true CPU-level parallelism.

    Individual page failures are captured and returned without failing the batch.
    """
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("page_count", len(page_id_strs))
    newrelic.agent.add_custom_attribute("language", language)

    num_workers = min(settings.ocr_thread_workers, len(page_id_strs))
    results = [None] * len(page_id_strs)

    progress_counter = 0
    progress_lock = threading.Lock()

    def _process_idx(idx: int) -> tuple[int, dict]:
        page_id = page_id_strs[idx]
        try:
            return idx, _process_page_threadsafe(page_id, book_id_str, language)
        except Exception as e:
            return idx, {"page_id": page_id, "success": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(_process_idx, i): i
            for i in range(len(page_id_strs))
        }
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

            if job_id_str and total_pages:
                with progress_lock:
                    progress_counter += 1
                    current = progress_counter
                try:
                    _update_job_progress(job_id_str, current, total_pages, book_id_str)
                except Exception:
                    logger.debug("Progress update failed for page %d", idx)

    return results


# ---------------------------------------------------------------------------
# Book-level OCR: processes pages sequentially with per-page progress updates
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="run_ocr_for_book")
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

        for page_id in page_ids:
            try:
                _process_page_threadsafe(page_id, book_id_str, language)
            except Exception as e:
                logger.error("OCR failed for page %s: %s", page_id, e)
                errors.append(f"Page {page_id}: {e}")

            completed += 1
            try:
                _update_job_progress(job_id_str, completed, total_pages, book_id_str)
            except Exception:
                logger.debug("Progress update failed for page %s", page_id)

        _finalize_job(job_id_str, book_id_str, total_pages, errors)

    except Exception as e:
        logger.error("OCR book job %s setup failed: %s", job_id_str, e)
        _mark_job_failed(job_id_str, str(e))
        raise


@celery_app.task(name="_ocr_book_complete")
def _ocr_book_complete(results, job_id_str: str, book_id_str: str, total_pages: int, batch_count: int):
    """Legacy chord callback. No longer invoked (orchestrator now finalizes inline),
    but kept for backward compatibility with any in-flight chord dispatches."""

    async def _finalize():
        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            book_id = uuid.UUID(book_id_str)

            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                return

            errors = []
            for batch_result in results:
                if isinstance(batch_result, list):
                    for r in batch_result:
                        if isinstance(r, dict) and r.get("success"):
                            continue
                        error_msg = r.get("error", "unknown") if isinstance(r, dict) else str(r)
                        errors.append(f"Page: {error_msg}")
                elif isinstance(batch_result, dict) and batch_result.get("success"):
                    continue
                else:
                    error_msg = batch_result.get("error", "unknown") if isinstance(batch_result, dict) else str(batch_result)
                    errors.append(f"Page: {error_msg}")

            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()

            if errors and len(errors) == total_pages:
                job.status = JobStatus.FAILED
                job.error_log = "All pages failed:\n" + "\n".join(errors)
            elif errors:
                job.status = JobStatus.COMPLETED
                job.error_log = "Some pages failed:\n" + "\n".join(errors)
                if book:
                    book.status = BookStatus.OCR_COMPLETE
            else:
                job.status = JobStatus.COMPLETED
                if book:
                    book.status = BookStatus.OCR_COMPLETE

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    try:
        run_async(_finalize())
    except Exception as e:
        logger.error("OCR book completion callback failed for %s: %s", job_id_str, e)
        _mark_job_failed(job_id_str, str(e))


def _finalize_job(job_id_str: str, book_id_str: str, total_pages: int, errors: list[str]) -> None:
    """Finalize the job after the sequential OCR loop completes.

    Sets job status, progress, completion timestamp, and updates the book's
    OCR status based on how many pages failed. Emits SSE events for the
    terminal job status and the book status transition.
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

            if errors and len(errors) >= total_pages:
                job.status = JobStatus.FAILED
                job.error_log = "All pages failed:\n" + "\n".join(errors)
            elif errors:
                job.status = JobStatus.COMPLETED
                job.error_log = "Some pages failed:\n" + "\n".join(errors)
                if book:
                    book.status = BookStatus.OCR_COMPLETE
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
        _mark_job_failed(job_id_str, str(e))


def _mark_job_failed(job_id_str: str, error: str):
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
            book_id = job.book_id
            await db.commit()

        if book_id is not None:
            _publish_job_terminal(book_id, uuid.UUID(job_id_str), JobStatus.FAILED, error)

    run_async(_do())
