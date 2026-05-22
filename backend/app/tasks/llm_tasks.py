import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services.llm_service import LlmService
from app.services.prompts import render_system_prompt, render_extraction_prompt
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="run_llm_extraction")
def run_llm_extraction(
    self,
    job_id_str: str,
    book_id_str: str,
    model: str = "airavata",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    system_prompt_override: str | None = None,
    extraction_prompt_override: str | None = None,
):
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

            book_result = await db.execute(select(Book).where(Book.id == book_id))
            book = book_result.scalar_one_or_none()
            if book is None:
                job.status = JobStatus.FAILED
                job.error_log = "Book not found"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            if book.status not in (BookStatus.OCR_COMPLETE, BookStatus.LLM_RUNNING):
                job.status = JobStatus.FAILED
                job.error_log = f"Book status is '{book.status}', expected 'ocr_complete'"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            pages_result = await db.execute(
                select(Page)
                .where(Page.book_id == book_id)
                .order_by(Page.page_number)
            )
            pages = pages_result.scalars().all()

            if not pages:
                job.status = JobStatus.FAILED
                job.error_log = "No pages found for book"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            page_ids = [p.id for p in pages]
            ocr_result_rows = await db.execute(
                select(OcrResult).where(OcrResult.page_id.in_(page_ids))
            )
            ocr_by_page = {r.page_id: r for r in ocr_result_rows.scalars().all()}

            text_parts = []
            for page in pages:
                ocr = ocr_by_page.get(page.id)
                if ocr:
                    text = ocr.corrected_text or ocr.raw_text or ""
                    if text.strip():
                        text_parts.append(text.strip())

            if not text_parts:
                job.status = JobStatus.FAILED
                job.error_log = "No OCR text available for extraction"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            ocr_text = "\n\n---\n\n".join(text_parts)
            language = book.language or "tel"
            page_count = len(text_parts)

            book.status = BookStatus.LLM_RUNNING
            await db.commit()

            llm = LlmService()

            def on_progress(current: int, total: int, batch_name: str):
                _run_async(_update_job_progress(job_id, current, total))

            metadata, batch_results = await llm.run_full_extraction(
                ocr_text=ocr_text,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                language=language,
                page_count=page_count,
                system_prompt_override=system_prompt_override,
                extraction_prompt_override=extraction_prompt_override,
                progress_callback=on_progress,
            )

            await llm.close()

            metadata_result = await db.execute(
                select(BookMetadata).where(BookMetadata.book_id == book_id)
            )
            existing_metadata = metadata_result.scalar_one_or_none()

            fields_data = metadata.model_dump()

            if existing_metadata:
                existing_fields = existing_metadata.fields or {}
                existing_fields.update(
                    {k: v for k, v in fields_data.items() if v is not None}
                )
                existing_metadata.fields = existing_fields
            else:
                new_metadata = BookMetadata(
                    book_id=book_id,
                    fields=fields_data,
                )
                db.add(new_metadata)

            await db.flush()

            for br in batch_results:
                llm_run = LlmRun(
                    job_id=job_id,
                    model=model,
                    prompt_template=render_extraction_prompt(
                        batch_name=br["batch_name"],
                        ocr_text=ocr_text[:2000],
                        language=language,
                        page_count=page_count,
                    ),
                    batch_config={"batch_name": br["batch_name"]},
                    raw_response=br.get("raw_response"),
                    parsed_fields=br.get("parsed_fields"),
                )
                db.add(llm_run)

            await db.flush()

            error_batches = [
                br["batch_name"]
                for br in batch_results
                if br.get("usage", {}).get("status") != "success"
            ]

            if error_batches and len(error_batches) == len(batch_results):
                job.status = JobStatus.FAILED
                job.error_log = f"All batches failed: {', '.join(error_batches)}"
                book.status = BookStatus.OCR_COMPLETE
            elif error_batches:
                job.status = JobStatus.COMPLETED
                job.error_log = f"Partial failures: {', '.join(error_batches)}"
                book.status = BookStatus.COMPLETE
            else:
                job.status = JobStatus.COMPLETED
                book.status = BookStatus.COMPLETE

            job.progress = 100.0
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

    try:
        return _run_async(_process())
    except Exception as e:
        logger.error("LLM extraction job %s failed: %s", job_id_str, e)

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

                book_result = await db.execute(
                    select(Book).where(
                        Book.jobs.any(Job.id == uuid.UUID(job_id_str))
                    )
                )
                book = book_result.scalar_one_or_none()
                if book and book.status == BookStatus.LLM_RUNNING:
                    book.status = BookStatus.OCR_COMPLETE

                await db.commit()

        _run_async(_mark_failed())
        raise


async def _update_job_progress(job_id: uuid.UUID, current: int, total: int):
    async with async_session_factory() as db:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job:
            job.progress = round((current / total) * 100, 1)
            await db.commit()
