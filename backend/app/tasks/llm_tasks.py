import logging
import uuid
from datetime import datetime, timezone

import newrelic.agent
from sqlalchemy import exc as sa_exc, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.metadata_field_evidence import MetadataFieldEvidence
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.services.batch_routing import PageText
from app.services.llm_service import llm_service as llm_service_singleton
from app.services.prompts import render_extraction_prompt
from app.services.search_service import SearchService
from app.services.sse_service import event_id, publish_sync
from app.tasks.async_utils import run_async
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _validate_book_context(
    job_id: uuid.UUID, book_id: uuid.UUID
) -> tuple[Job, Book, str, int, list[PageText]]:
    """Load job/book, validate preconditions, and return (job, book, ocr_text, page_count, pages).

    ``pages`` is the per-page OCR text list used by the LLM service to route
    each metadata batch to the most relevant page region. The legacy
    ``ocr_text`` blob is also returned for backward compatibility and
    logging.

    Raises on unrecoverable validation failure with the job already marked failed.
    """
    async with async_session_factory() as db:
        job_result = await db.execute(select(Job).where(Job.id == job_id))
        job = job_result.scalar_one_or_none()
        if job is None:
            raise ValueError(f"Job {job_id} not found")

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
            raise ValueError(f"Book {book_id} not found")

        if book.status not in (BookStatus.OCR_COMPLETE, BookStatus.LLM_RUNNING):
            job.status = JobStatus.FAILED
            job.error_log = f"Book status is '{book.status}', expected 'ocr_complete'"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise ValueError(f"Invalid book status: {book.status}")

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
            raise ValueError(f"No pages for book {book_id}")

        page_ids = [p.id for p in pages]
        ocr_result_rows = await db.execute(
            select(OcrResult).where(OcrResult.page_id.in_(page_ids))
        )
        ocr_by_page = {r.page_id: r for r in ocr_result_rows.scalars().all()}

        text_parts = []
        page_texts: list[PageText] = []
        for page in pages:
            ocr = ocr_by_page.get(page.id)
            if ocr:
                text = ocr.corrected_text or ocr.raw_text or ""
                if text.strip():
                    text_parts.append(text.strip())
                    page_texts.append(PageText(page_number=page.page_number, text=text))

        if not text_parts:
            job.status = JobStatus.FAILED
            job.error_log = "No OCR text available for extraction"
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise ValueError("No OCR text available")

        ocr_text = "\n\n---\n\n".join(text_parts)
        language = book.language or "tel"
        page_count = len(text_parts)

        book.status = BookStatus.LLM_RUNNING
        await db.commit()

        return job, book, ocr_text, language, page_count, page_texts


async def _persist_extraction_results(
    metadata, batch_results, book_id, job_id, ocr_text, language, page_count,
    evidence=None,
):
    """Persist extracted metadata, LLM run records, and per-field evidence."""
    evidence = evidence or {}
    async with async_session_factory() as db:
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
            new_metadata = BookMetadata(book_id=book_id, fields=fields_data)
            db.add(new_metadata)

        await db.flush()

        # Per-field evidence: one row per populated field.
        if evidence:
            existing_evidence_result = await db.execute(
                select(MetadataFieldEvidence).where(
                    MetadataFieldEvidence.book_id == book_id
                )
            )
            existing_evidence = {
                e.field_name: e
                for e in existing_evidence_result.scalars().all()
            }
            for field_name, ef in evidence.items():
                if ef.value is None:
                    continue
                ef_row = existing_evidence.get(field_name)
                if ef_row is None:
                    db.add(
                        MetadataFieldEvidence(
                            book_id=book_id,
                            field_name=field_name,
                            value=ef.value,
                            confidence=ef.confidence,
                            extraction_method=ef.method,
                            source_page_number=ef.source_page_number,
                            source_text_snippet=ef.source_text_snippet,
                        )
                    )
                else:
                    ef_row.value = ef.value
                    ef_row.confidence = ef.confidence
                    ef_row.extraction_method = ef.method
                    ef_row.source_page_number = ef.source_page_number
                    ef_row.source_text_snippet = ef.source_text_snippet

        for br in batch_results:
            llm_run = LlmRun(
                job_id=job_id,
                model=br.get("model", "airavata"),
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

        job_result = await db.execute(select(Job).where(Job.id == job_id))
        job = job_result.scalar_one_or_none()
        book_result = await db.execute(select(Book).where(Book.id == book_id))
        book = book_result.scalar_one_or_none()

        error_batches = [
            br["batch_name"]
            for br in batch_results
            if br.get("usage", {}).get("status") not in ("success", "fallback", "empty_response")
        ]
        empty_batches = [
            br["batch_name"]
            for br in batch_results
            if br.get("usage", {}).get("status") == "empty_response"
        ]

        if error_batches and len(error_batches) == len(batch_results):
            job.status = JobStatus.FAILED
            job.error_log = f"All batches failed: {', '.join(error_batches)}"
            if book:
                book.status = BookStatus.OCR_COMPLETE
        elif error_batches:
            job.status = JobStatus.COMPLETED
            job.error_log = f"Partial failures: {', '.join(error_batches)}"
            if book:
                book.status = BookStatus.AWAITING_REVIEW
        elif empty_batches:
            # Job technically completed but every "empty" batch produced no
            # values — likely a context-length truncation problem. Surface
            # this prominently in error_log so users aren't confused by a
            # fully green job with zero extracted fields.
            job.status = JobStatus.COMPLETED
            job.error_log = (
                f"LLM returned no values for {len(empty_batches)} "
                f"batch(es): {', '.join(empty_batches)}. "
                "Likely context-length truncation; check num_ctx and per-batch OCR cap."
            )
            if book:
                book.status = BookStatus.AWAITING_REVIEW
        else:
            job.status = JobStatus.COMPLETED
            if book:
                book.status = BookStatus.AWAITING_REVIEW

        job.progress = 100.0
        job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        terminal_status = job.status
        error_log = job.error_log
        new_book_status = book.status if book else None
        job_uuid = job.id
        book_uuid = book.id

        publish_sync(
            book_uuid,
            {
                "id": event_id(f"job-{terminal_status}"),
                "type": "job.terminal",
                "book_id": str(book_uuid),
                "job_id": str(job_uuid),
                "status": terminal_status,
                "error_log": error_log,
            },
        )
        if new_book_status is not None:
            publish_sync(
                book_uuid,
                {
                    "id": event_id("book-status"),
                    "type": "book.status_changed",
                    "book_id": str(book_uuid),
                    "status": new_book_status,
                    "job_id": str(job_uuid),
                },
            )
            if new_book_status == BookStatus.AWAITING_REVIEW:
                low_conf_count = await SearchService.count_low_confidence_fields(
                    db, book_uuid, settings.low_confidence_threshold
                )
                publish_sync(
                    book_uuid,
                    {
                        "id": event_id("book-awaiting-review"),
                        "type": "book.awaiting_review",
                        "book_id": str(book_uuid),
                        "low_confidence_count": low_conf_count,
                    },
                )


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
    max_tokens: int = 512,
    system_prompt_override: str | None = None,
    extraction_prompt_override: str | None = None,
):
    newrelic.agent.add_custom_attribute("book_id", book_id_str)
    newrelic.agent.add_custom_attribute("job_id", job_id_str)
    newrelic.agent.add_custom_attribute("model", model)

    async def _process():
        job_id = uuid.UUID(job_id_str)
        book_id = uuid.UUID(book_id_str)

        job, book, ocr_text, language, page_count, page_texts = await _validate_book_context(
            job_id, book_id
        )

        llm = llm_service_singleton

        async def on_progress(current: int, total: int, batch_name: str):
            async with async_session_factory() as progress_db:
                result = await progress_db.execute(
                    select(Job).where(Job.id == job_id)
                )
                progress_job = result.scalar_one_or_none()
                if progress_job:
                    progress_job.progress = round((current / total) * 100, 1)
                    await progress_db.commit()
                    progress_pct = progress_job.progress
                else:
                    progress_pct = round((current / total) * 100, 1)
            publish_sync(
                book_id,
                {
                    "id": event_id("job-progress"),
                    "type": "job.progress",
                    "book_id": str(book_id),
                    "job_id": str(job_id),
                    "job_type": JobType.LLM,
                    "progress": progress_pct,
                    "batch": batch_name,
                },
            )

        metadata, batch_results, evidence = await llm.run_hybrid_full_extraction(
            ocr_text=ocr_text,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            language=language,
            page_count=page_count,
            system_prompt_override=system_prompt_override,
            extraction_prompt_override=extraction_prompt_override,
            progress_callback=on_progress,
            pages=page_texts,
        )

        await _persist_extraction_results(
            metadata, batch_results, book_id, job_id, ocr_text, language, page_count,
            evidence=evidence,
        )

    try:
        return run_async(_process())
    except (ConnectionError, TimeoutError, OSError, sa_exc.OperationalError) as exc:
        logger.warning("Transient error for LLM job %s, retrying: %s", job_id_str, exc)
        raise self.retry(exc=exc)
    except Exception as e:
        logger.error("LLM extraction job %s failed: %s", job_id_str, e)
        error_message = str(e)

        async def _mark_failed():
            async with async_session_factory() as db:
                job_result = await db.execute(
                    select(Job).where(Job.id == uuid.UUID(job_id_str))
                )
                job = job_result.scalar_one_or_none()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_log = error_message
                    job.completed_at = datetime.now(timezone.utc)

                book_result = await db.execute(
                    select(Book).where(
                        Book.jobs.any(Job.id == uuid.UUID(job_id_str))
                    )
                )
                book = book_result.scalar_one_or_none()
                book_status_after: str | None = None
                if book and book.status == BookStatus.LLM_RUNNING:
                    book.status = BookStatus.OCR_COMPLETE
                    book_status_after = BookStatus.OCR_COMPLETE

                await db.commit()
                book_uuid = book.id if book else None

            if book_uuid is not None:
                publish_sync(
                    book_uuid,
                    {
                        "id": event_id("job-failed"),
                        "type": "job.terminal",
                        "book_id": str(book_uuid),
                        "job_id": job_id_str,
                        "status": JobStatus.FAILED,
                        "error_log": error_message,
                    },
                )
                if book_status_after is not None:
                    publish_sync(
                        book_uuid,
                        {
                            "id": event_id("book-status"),
                            "type": "book.status_changed",
                            "book_id": str(book_uuid),
                            "status": book_status_after,
                            "job_id": job_id_str,
                        },
                    )

        run_async(_mark_failed())
        raise
