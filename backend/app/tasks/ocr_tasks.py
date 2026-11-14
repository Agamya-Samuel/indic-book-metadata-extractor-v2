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
from app.services import notification_service, ocr_service, ocr_postprocess, preprocessing, storage
from app.services.sse_service import event_id, publish_sync
from app.services.stage_manager import StageManager, StageTransitionError
from app.tasks.cancellation import (
    is_cancelled_async,
    is_superseded_async,
    should_stop,
)
from app.tasks.async_utils import run_async, run_async_threadsafe
from app.tasks.pipeline_lock import refresh as refresh_pipeline_lock
from app.tasks.pipeline_lock import single_book_task
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def ocr_outcome(total_pages: int, errors: list[str]) -> tuple[str, str | None]:
    """Terminal job status and error log for an OCR run with page failures.

    A partial failure still counts as completed: the pages that succeeded are
    usable, and blocking the book at ``pages_selected`` stranded the text the
    user could already review. Only a run where every page failed is a failure.
    """
    if not errors:
        return JobStatus.COMPLETED, None
    joined = "\n".join(errors)
    if total_pages and len(errors) >= total_pages:
        return JobStatus.FAILED, ("All pages failed:\n" + joined)[:2000]
    return JobStatus.COMPLETED, ("Some pages failed:\n" + joined)[:2000]


def _record_page_error(page_id_str: str, message: str) -> None:
    async def _do():
        async with async_session_factory() as db:
            page = await db.get(Page, uuid.UUID(page_id_str))
            if page is None:
                return
            page.ocr_error = message[:2000]
            await db.commit()

    try:
        run_async_threadsafe(_do())
    except Exception:  # noqa: BLE001
        logger.debug("Could not record OCR error for page %s", page_id_str, exc_info=True)


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

        page.ocr_error = None
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
            job.last_progress_at = datetime.now(timezone.utc)
            if new_progress > (job.progress or 0.0):
                job.progress = new_progress
                progress_pct = new_progress
            else:
                progress_pct = job.progress or 0.0
            await db.commit()
            if book_id is None and job.book_id is not None:
                book_id = job.book_id
            jtype = job.job_type

        refresh_pipeline_lock(job_id_str)
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


def _has_active_job_for_book(
    book_id: uuid.UUID, exclude_job_id: uuid.UUID | None = None
) -> bool:
    """Return True if the book already has a queued/running OCR or PREPROCESSING job.

    ``exclude_job_id`` skips the job that dispatched this task — the API creates
    the OCR job as QUEUED before dispatching preprocessing, so without the
    exclusion the caller would always match itself and skip the whole run.
    """

    async def _check():
        async with async_session_factory() as db:
            query = select(Job.id).where(
                Job.book_id == book_id,
                Job.status.in_((JobStatus.QUEUED, JobStatus.RUNNING)),
                Job.job_type.in_((JobType.OCR, JobType.PREPROCESSING)),
            )
            if exclude_job_id is not None:
                query = query.where(Job.id != exclude_job_id)
            result = await db.execute(query.limit(1))
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
@single_book_task
def preprocess_pages_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Preprocess all pages that need it, then chain into OCR.

    On failure, the preprocessing job is marked FAILED and OCR is **not**
    dispatched — downstream code must retry the job explicitly.
    """
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)

    book_uuid = uuid.UUID(book_id_str)
    if _has_active_job_for_book(book_uuid, uuid.UUID(job_id_str)):
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
            if job is None or job.status == JobStatus.CANCELLED:
                return None
            if await is_superseded_async(db, job):
                logger.info("Preprocessing job %s was superseded", job_id_str)
                return None
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.last_progress_at = job.started_at
            if self.request.id and not job.celery_task_id:
                job.celery_task_id = self.request.id
            await db.commit()

            pages_result = await db.execute(
                select(Page).where(Page.book_id == book_uuid).order_by(Page.page_number)
            )
            pages = pages_result.scalars().all()

            preprocessed = 0
            for page in pages:
                if await is_cancelled_async(db, job_uuid):
                    logger.info("Preprocessing job %s cancelled", job_id_str)
                    return None
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
        if count is None:
            logger.info(
                "Preprocessing for book %s stopped (cancelled, superseded, or job gone)",
                book_id_str,
            )
            return
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

    if should_stop(uuid.UUID(job_id_str)):
        logger.info("OCR for book %s not dispatched: job cancelled or superseded", book_id_str)
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
@single_book_task
def run_ocr_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Run OCR sequentially for every page of a book, updating progress after each page."""
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)
    newrelic.agent.add_custom_attribute("language", language)

    job_uuid = uuid.UUID(job_id_str)

    async def _setup():
        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            book_id = uuid.UUID(book_id_str)

            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                logger.info("OCR job %s no longer exists", job_id_str)
                return None
            if job.status == JobStatus.CANCELLED:
                logger.info("OCR job %s was cancelled before it started", job_id_str)
                return None
            if await is_superseded_async(db, job):
                logger.info("OCR job %s was superseded before it started", job_id_str)
                return None

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            job.last_progress_at = job.started_at
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
            if should_stop(job_uuid):
                logger.info("OCR job %s cancelled or superseded; stopping", job_id_str)
                return
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
                _record_page_error(page_id, f"{type(e).__name__}: {e}")

            completed += 1
            _update_job_progress(job_id_str, completed, total_pages, book_id_str)

        if should_stop(job_uuid):
            logger.info("OCR job %s cancelled or superseded before finalising", job_id_str)
            return

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
                return None
            if job.status == JobStatus.CANCELLED:
                logger.info("OCR job %s was cancelled; not finalising", job_id_str)
                return None
            if await is_superseded_async(db, job):
                logger.info("OCR job %s was superseded; not finalising", job_id_str)
                return None

            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()

            # Stage transitions run on THIS session, never a second one: the
            # other session's SELECT ... FOR UPDATE on the book row would block
            # against any flushed write of ours that references it.
            try:
                status, outcome_log = ocr_outcome(total_pages, errors)
                job.status = status
                job.error_log = outcome_log
                if book:
                    if status == JobStatus.FAILED:
                        await StageManager.fail_stage(
                            db, book_id, "ocr", outcome_log or ""
                        )
                    else:
                        # Partial runs advance: the failed pages stay flagged via
                        # pages.ocr_error, but the book reaches ocr_complete so
                        # the text that did succeed can be reviewed.
                        await StageManager.complete_stage(db, book_id, "ocr")
            except StageTransitionError:
                logger.warning(
                    "OCR stage for book %s changed while job %s was finalising; "
                    "keeping the job result without touching the stage",
                    book_id_str,
                    job_id_str,
                    exc_info=True,
                )

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            terminal_status = job.status
            error_log = job.error_log
            new_book_status = book.status if book else None
            notification_id = await notification_service.notify_job_terminal(
                db, job=job, book=book, status=terminal_status
            )
            await notification_service.notify_and_deliver(db, [notification_id])

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

    async def _do() -> bool:
        async with async_session_factory() as db:
            job_result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id_str))
            )
            job = job_result.scalar_one_or_none()
            if not job:
                return False
            if job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                logger.info(
                    "Job %s is already %s; refusing to overwrite it with a failure",
                    job_id_str,
                    job.status,
                )
                return False
            if await is_superseded_async(db, job):
                logger.info("Job %s was superseded; not marking it failed", job_id_str)
                return False
            job.status = JobStatus.FAILED
            job.error_log = error
            job.completed_at = datetime.now(timezone.utc)

            # Never leave the book wedged in OCR_RUNNING. Both run-ocr and
            # run-extraction refuse to start from a running status, so a failed
            # run would be a dead end that no UI action could clear. Release it
            # the same way _finalize_job does for partial runs.
            book = await db.get(Book, book_id)
            released = book is not None and book.status == BookStatus.OCR_RUNNING
            if released:
                book.status = BookStatus.PAGES_SELECTED

            await db.commit()
            notification_id = await notification_service.notify_job_terminal(
                db, job=job, book=book, status=JobStatus.FAILED
            )
            await notification_service.notify_and_deliver(db, [notification_id])
            return released

    try:
        released = run_async(_do())
        _publish_job_terminal(book_id, uuid.UUID(job_id_str), JobStatus.FAILED, error)
        if released:
            _publish_book_status(book_id, BookStatus.PAGES_SELECTED, uuid.UUID(job_id_str))
    except Exception as e:
        logger.error("Failed to mark job %s as FAILED: %s", job_id_str, e)
