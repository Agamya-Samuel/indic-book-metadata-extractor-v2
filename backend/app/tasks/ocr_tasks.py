import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from celery import chord, group
from sqlalchemy import select

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
def run_ocr_for_page(self, page_id_str: str, book_id_str: str, language: str):
    """Run OCR on a single page. Retries up to 3 times on transient errors."""

    async def _process():
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

    try:
        return run_async(_process())
    except (ConnectionError, TimeoutError, OSError) as exc:
        # Transient errors — retry
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
# Book-level OCR: orchestrates parallel page tasks via chord
# ---------------------------------------------------------------------------
@celery_app.task(bind=True, name="run_ocr_for_book")
def run_ocr_for_book(self, job_id_str: str, book_id_str: str, language: str):
    """Kick off parallel OCR for all pages of a book using Celery chord."""

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

        # Build a chord: parallel OCR for all pages -> completion callback
        page_tasks = group(
            run_ocr_for_page.s(pid, book_id_str, language) for pid in page_ids
        )
        callback = _ocr_book_complete.s(job_id_str, book_id_str, len(page_ids))

        chord(page_tasks, callback).apply_async()

    except Exception as e:
        logger.error("OCR book job %s setup failed: %s", job_id_str, e)
        _mark_job_failed(job_id_str, str(e))
        raise


@celery_app.task(name="_ocr_book_complete")
def _ocr_book_complete(results, job_id_str: str, book_id_str: str, total_pages: int):
    """Callback invoked after all page OCR tasks complete."""

    async def _finalize():
        async with async_session_factory() as db:
            job_id = uuid.UUID(job_id_str)
            book_id = uuid.UUID(book_id_str)

            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one_or_none()
            if job is None:
                return

            errors = []
            for r in results:
                if isinstance(r, dict) and r.get("success"):
                    continue
                # Treat anything that isn't a success dict as a failure
                # (includes exceptions from exhausted retries)
                error_msg = (
                    r.get("error", "unknown") if isinstance(r, dict) else str(r)
                )
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
