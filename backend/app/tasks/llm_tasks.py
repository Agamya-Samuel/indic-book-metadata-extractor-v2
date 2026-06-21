import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import newrelic.agent
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services.llm_service import llm_service as llm_service_singleton
from app.services.metrics import record_llm_extraction
from app.services.prompts import render_extraction_prompt
from app.tasks.async_utils import run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="run_llm_extraction",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
@newrelic.agent.background_task(name="LLM: Metadata Extraction", group="CeleryTask")
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
    newrelic.agent.add_custom_parameter("book_id", book_id_str)
    newrelic.agent.add_custom_parameter("job_id", job_id_str)
    newrelic.agent.add_custom_parameter("model", model)

    _start_time = time.monotonic()
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

            llm = llm_service_singleton

            # Progress callback that updates DB inline within the same async context
            async def on_progress_async(current: int, total: int, batch_name: str):
                async with async_session_factory() as progress_db:
                    result = await progress_db.execute(
                        select(Job).where(Job.id == job_id)
                    )
                    progress_job = result.scalar_one_or_none()
                    if progress_job:
                        progress_job.progress = round((current / total) * 100, 1)
                        await progress_db.commit()

            pending_futures: list = []

            def on_progress(current: int, total: int, batch_name: str):
                # Schedule the async update within the running loop.
                fut = asyncio.ensure_future(on_progress_async(current, total, batch_name))
                pending_futures.append(fut)

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

            # Await any pending progress updates before closing the loop
            if pending_futures:
                await asyncio.gather(*pending_futures, return_exceptions=True)

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
        return run_async(_process())
    except (ConnectionError, TimeoutError, OSError) as exc:
        # Transient errors (Ollama down, network issues) — retry
        logger.warning("Transient error for LLM job %s, retrying: %s", job_id_str, exc)
        raise self.retry(exc=exc)
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

        run_async(_mark_failed())
        raise
