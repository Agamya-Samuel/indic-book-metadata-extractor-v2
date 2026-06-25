import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import newrelic.agent
from celery import chord, group
from sqlalchemy import exc as sa_exc, select
from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services import ocr_service, preprocessing, storage
from app.tasks.async_utils import run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

#: Pages per batch to reduce task-queue overhead for large books.
OCR_BATCH_SIZE: int = 5


def _process_page(page_id_str: str, book_id_str: str, language: str) -> dict:
    """Process a single page: run OCR and persist results. No retry."""
    async def _run():
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

            # Run preprocessing if configured but not yet applied
            config = page.preprocessing_config
            if config and not page.processed_image_path:
                output_path = storage.processed_image_path(
                    book_id_str, page.page_number
                )
                preprocessing.run_pipeline(image_path, config, output_path)
                page.processed_image_path = storage.relative(output_path)
                await db.flush()
                image_path = output_path

            ocr_data = ocr_service.run_ocr(image_path, language)

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

    return run_async(_run())


# ---------------------------------------------------------------------------
# Single-page OCR task (reusable building block)
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
# Batched-page OCR task (reduces task-queue overhead)
# ---------------------------------------------------------------------------
@celery_app.task(
    bind=True,
    name="run_ocr_for_page_batch",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
@newrelic.agent.background_task(name="OCR: Page Batch", group="CeleryTask")
def run_ocr_for_page_batch(self, page_id_strs: list, book_id_str: str, language: str):
    """Run OCR on a batch of up to :data:`OCR_BATCH_SIZE` pages in one task.
    Individual page failures are captured and returned without failing the batch.
    """
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("page_count", len(page_id_strs))
    newrelic.agent.add_custom_attribute("language", language)

    results = []
    for page_id_str in page_id_strs:
        try:
            results.append(_process_page(page_id_str, book_id_str, language))
        except Exception as e:
            results.append({
                "page_id": page_id_str,
                "success": False,
                "error": str(e),
            })
    return results


# ---------------------------------------------------------------------------
# Book-level OCR: orchestrates parallel page tasks via chord
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="run_ocr_for_book")
@newrelic.agent.background_task(name="OCR: Book Orchestration", group="CeleryTask")
def run_ocr_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Kick off parallel OCR for all pages of a book using Celery chord."""

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

        batches = [page_ids[i : i + OCR_BATCH_SIZE] for i in range(0, len(page_ids), OCR_BATCH_SIZE)]
        page_tasks = group(
            run_ocr_for_page_batch.s(batch, book_id_str, language) for batch in batches
        )
        callback = _ocr_book_complete.s(job_id_str, book_id_str, len(page_ids), len(batches))

        chord(page_tasks, callback).apply_async()

    except Exception as e:
        logger.error("OCR book job %s setup failed: %s", job_id_str, e)
        _mark_job_failed(job_id_str, str(e))
        raise


@celery_app.task(name="_ocr_book_complete")
def _ocr_book_complete(results, job_id_str: str, book_id_str: str, total_pages: int, batch_count: int):
    """Callback invoked after all page OCR batches complete."""

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


def _mark_job_failed(job_id_str: str, error: str):
    """Mark a job as failed in the database."""

    async def _do():
        async with async_session_factory() as db:
            job_result = await db.execute(
                select(Job).where(Job.id == uuid.UUID(job_id_str))
            )
            job = job_result.scalar_one_or_none()
            if job:
                job.status = JobStatus.FAILED
                job.error_log = error
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

    run_async(_do())
