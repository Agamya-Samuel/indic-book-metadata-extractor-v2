from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.books import _get_book
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.schemas.metadata import (
    ExtractionRequest,
    ExtractionResponse,
    ModelInfo,
)
from app.services.llm_service import llm_service

router = APIRouter()


@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    models = await llm_service.list_available_models()
    return [ModelInfo(**m) for m in models]


@router.post(
    "/{book_id}/run-extraction",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_extraction(
    book_id: UUID,
    body: ExtractionRequest,
    db: AsyncSession = Depends(get_db),
) -> ExtractionResponse:
    book = await _get_book(book_id, db)

    if book.status not in (BookStatus.OCR_COMPLETE,):
        raise HTTPException(
            status_code=400,
            detail=f"Book status must be 'ocr_complete', got '{book.status}'",
        )

    pages_result = await db.execute(
        select(Page).where(Page.book_id == book_id)
    )
    pages = pages_result.scalars().all()
    if not pages:
        raise HTTPException(status_code=400, detail="No pages selected for this book")

    page_ids = [p.id for p in pages]
    ocr_results = await db.execute(
        select(OcrResult).where(OcrResult.page_id.in_(page_ids))
    )
    ocr_list = ocr_results.scalars().all()
    has_text = any(
        (o.corrected_text or o.raw_text or "").strip() for o in ocr_list
    )
    if not has_text:
        raise HTTPException(
            status_code=400,
            detail="No OCR text available for extraction. Run OCR first.",
        )

    running_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.job_type == JobType.LLM,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    if running_jobs.scalars().first():
        raise HTTPException(
            status_code=409,
            detail="An LLM extraction job is already running or queued for this book",
        )

    from app.schemas.metadata import BATCH_FIELD_ORDER

    job = Job(
        book_id=book_id,
        job_type=JobType.LLM,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.tasks.llm_tasks import run_llm_extraction

    run_llm_extraction.delay(
        str(job.id),
        str(book_id),
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        system_prompt_override=body.custom_system_prompt,
        extraction_prompt_override=body.custom_extraction_prompt,
    )

    return ExtractionResponse(
        job_id=job.id,
        book_id=book_id,
        status=job.status,
        total_batches=len(BATCH_FIELD_ORDER),
    )


@router.post(
    "/{book_id}/retry-extraction",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def retry_extraction(
    book_id: UUID,
    body: ExtractionRequest,
    db: AsyncSession = Depends(get_db),
) -> ExtractionResponse:
    book = await _get_book(book_id, db)

    if book.status not in (BookStatus.OCR_COMPLETE, BookStatus.COMPLETE):
        raise HTTPException(
            status_code=400,
            detail=f"Book status must be 'ocr_complete' or 'complete', got '{book.status}'",
        )

    book.status = BookStatus.OCR_COMPLETE

    return await run_extraction(book_id, body, db)
