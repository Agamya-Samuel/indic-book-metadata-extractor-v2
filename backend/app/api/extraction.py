from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    PaginationParams,
    get_current_user,
    get_owned_book_or_404,
    get_pagination,
)
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.models.user import User
from app.schemas.common import Page as PageEnvelope
from app.schemas.metadata import (
    BATCH_FIELD_ORDER,
    ExtractionRequest,
    ExtractionResponse,
    ModelInfo,
)
from app.services.llm_service import llm_service
from app.services.stage_manager import StageManager, StageStatus

router = APIRouter()


@router.get("/models", response_model=PageEnvelope[ModelInfo])
async def list_models(
    pagination: PaginationParams = Depends(get_pagination),
    _user: User = Depends(get_current_user),
) -> PageEnvelope[ModelInfo]:
    models = [ModelInfo(**m) for m in await llm_service.list_available_models()]
    items = models[pagination.offset : pagination.offset + pagination.page_size]
    return PageEnvelope[ModelInfo].create(
        items=items,
        total=len(models),
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post(
    "/{book_id}/run-extraction",
    response_model=ExtractionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_extraction(
    book_id: UUID,
    body: ExtractionRequest,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExtractionResponse:
    # Check for an active run before the status gate: after the first request
    # the book is llm_running, and a duplicate must see 409 (with the job id),
    # not an "invalid status" 400.
    running_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.job_type == JobType.LLM,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    running_job = running_jobs.scalars().first()
    if running_job:
        raise HTTPException(
            status_code=409,
            detail="An LLM extraction job is already running or queued for this book",
            headers={"X-Existing-Job-Id": str(running_job.id)},
        )

    if book.status not in (
        BookStatus.OCR_COMPLETE,
        BookStatus.AWAITING_REVIEW,
        BookStatus.COMPLETE,
    ):
        raise HTTPException(
            status_code=400,
            detail=(f"Book status must be 'ocr_complete', 'awaiting_review' or 'complete', got '{book.status}'"),
        )

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id))
    pages = pages_result.scalars().all()
    if not pages:
        raise HTTPException(status_code=400, detail="No pages selected for this book")

    page_ids = [p.id for p in pages]
    ocr_results = await db.execute(select(OcrResult).where(OcrResult.page_id.in_(page_ids)))
    ocr_list = ocr_results.scalars().all()
    has_text = any((o.corrected_text or o.raw_text or "").strip() for o in ocr_list)
    if not has_text:
        raise HTTPException(
            status_code=400,
            detail="No OCR text available for extraction. Run OCR first.",
        )

    if book.status in (BookStatus.AWAITING_REVIEW, BookStatus.COMPLETE):
        # Re-running extraction supersedes the human review, so release the
        # downstream stages and let the new run own the state again.
        await StageManager.reset_from_stage(db, book_id, "llm_extraction", "Superseded by a new extraction run")
        book.status = BookStatus.OCR_COMPLETE
        await db.flush()

    job = Job(
        book_id=book.id,
        requested_by_id=user.id,
        job_type=JobType.LLM,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await StageManager.initiate_stage(db, book_id, "llm_extraction")
    await StageManager.start_stage(db, book_id, "llm_extraction")
    await db.commit()

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
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExtractionResponse:
    if book.status not in (
        BookStatus.OCR_COMPLETE,
        BookStatus.AWAITING_REVIEW,
        BookStatus.COMPLETE,
    ):
        raise HTTPException(
            status_code=400,
            detail=(f"Book status must be 'ocr_complete', 'awaiting_review' or 'complete', got '{book.status}'"),
        )

    existing = await StageManager.get_stage(db, book_id, "llm_extraction")
    if existing and existing.status in (StageStatus.INITIATED, StageStatus.PROCESSING):
        await StageManager.cancel_stage(db, book_id, "llm_extraction", "Superseded by retry")
        await db.commit()

    return await run_extraction(book_id, body, book=book, db=db, user=user)
