import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services import ocr_service, preprocessing, storage
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_page_image_path(page: Page) -> str | None:
    if page.processed_image_path:
        path = str(page.image_path) if not page.processed_image_path else page.processed_image_path
        return page.processed_image_path
    return page.image_path


@celery_app.task(bind=True, name="run_ocr_for_page")
def run_ocr_for_page(self, page_id_str: str, book_id_str: str, language: str):
    async def _process():
        async with async_session_factory() as db:
            result = await db.execute(select(Page).where(Page.id == uuid.UUID(page_id_str)))
            page = result.scalar_one_or_none()
            if page is None:
                raise ValueError(f"Page {page_id_str} not found")

            image_rel = page.processed_image_path or page.image_path
            if not image_rel:
                raise ValueError(f"Page {page_id_str} has no image")

            from pathlib import Path

            image_path = Path(settings.storage_path) / image_rel
            if not image_path.exists():
                raise ValueError(f"Image file not found: {image_path}")

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
            return ocr_data

    try:
        return _run_async(_process())
    except Exception as e:
        logger.error("OCR failed for page %s: %s", page_id_str, e)
        raise


@celery_app.task(bind=True, name="run_ocr_for_book")
def run_ocr_for_book(self, job_id_str: str, book_id_str: str, language: str):
    async def _process():
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
                return

            total = len(pages)
            errors = []

            for i, page in enumerate(pages):
                try:
                    image_rel = page.processed_image_path or page.image_path
                    if not image_rel:
                        errors.append(f"Page {page.page_number}: no image")
                        continue

                    from pathlib import Path

                    image_path = Path(settings.storage_path) / image_rel
                    if not image_path.exists():
                        errors.append(f"Page {page.page_number}: image file missing")
                        continue

                    config = page.preprocessing_config
                    if config and not page.processed_image_path:
                        output_path = storage.processed_image_path(
                            str(book_id), page.page_number
                        )
                        preprocessing.run_pipeline(image_path, config, output_path)
                        page.processed_image_path = storage.relative(output_path)
                        await db.flush()
                        image_path = output_path

                    ocr_data = ocr_service.run_ocr(image_path, language)

                    existing_result = await db.execute(
                        select(OcrResult).where(OcrResult.page_id == page.id)
                    )
                    existing = existing_result.scalar_one_or_none()

                    if existing:
                        existing.raw_text = ocr_data["full_text"]
                        existing.bounding_boxes = {"words": ocr_data["words"]}
                        existing.confidence = ocr_data["avg_confidence"]
                        existing.language_detected = language
                    else:
                        new_ocr = OcrResult(
                            page_id=page.id,
                            raw_text=ocr_data["full_text"],
                            bounding_boxes={"words": ocr_data["words"]},
                            confidence=ocr_data["avg_confidence"],
                            language_detected=language,
                        )
                        db.add(new_ocr)

                    await db.flush()

                except Exception as e:
                    errors.append(f"Page {page.page_number}: {e}")
                    logger.error("OCR failed for page %s: %s", page.id, e)

                progress = round(((i + 1) / total) * 100, 1)
                job.progress = progress
                await db.commit()
                job_result = await db.execute(select(Job).where(Job.id == job_id))
                job = job_result.scalar_one()

            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()

            if errors and len(errors) == total:
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
        return _run_async(_process())
    except Exception as e:
        logger.error("OCR book job %s failed: %s", job_id_str, e)

        async def _mark_failed():
            async with async_session_factory() as db:
                job_result = await db.execute(
                    select(Job).where(Job.id == uuid.UUID(job_id_str))
                )
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_log = str(e)
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()

        _run_async(_mark_failed())
        raise
