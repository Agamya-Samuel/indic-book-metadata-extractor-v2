from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import PaginationParams, get_owned_book_or_404, get_pagination
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.metadata_field_evidence import MetadataFieldEvidence
from app.models.stage import StageStatus
from app.schemas.common import Page
from app.schemas.metadata import (
    ALL_METADATA_FIELDS,
    FieldEvidenceResponse,
    LlmRunResponse,
    MetadataFieldDefinition,
    MetadataResponse,
    MetadataUpdateRequest,
)
from app.services.stage_manager import StageManager

router = APIRouter()


@router.get("/{book_id}/metadata", response_model=MetadataResponse)
async def get_metadata(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    book_id = book.id

    result = await db.execute(select(BookMetadata).where(BookMetadata.book_id == book_id))
    metadata = result.scalar_one_or_none()

    if metadata is None:
        return MetadataResponse(book_id=book_id, fields={})

    return MetadataResponse(
        book_id=book_id,
        fields=metadata.fields or {},
        updated_at=metadata.updated_at,
    )


@router.put("/{book_id}/metadata", response_model=MetadataResponse)
async def update_metadata(
    book_id: UUID,
    body: MetadataUpdateRequest,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    result = await db.execute(select(BookMetadata).where(BookMetadata.book_id == book_id).with_for_update())
    metadata = result.scalar_one_or_none()

    if metadata is None:
        metadata = BookMetadata(book_id=book_id, fields=body.fields)
        db.add(metadata)
    else:
        existing = metadata.fields or {}
        existing.update(body.fields)
        metadata.fields = existing
        flag_modified(metadata, "fields")

    # Saving no longer completes the workflow. Keep the book in
    # `awaiting_review` and mark `human_review` as in progress; the explicit
    # "Mark review complete" action finishes it.
    if book.status == BookStatus.AWAITING_REVIEW:
        human = await StageManager.get_stage(db, book_id, "human_review")
        if human is None:
            await StageManager.initiate_stage(db, book_id, "human_review")
            await StageManager.start_stage(db, book_id, "human_review")
        elif human.status == StageStatus.INITIATED:
            await StageManager.start_stage(db, book_id, "human_review")

    await db.commit()
    await db.refresh(metadata)

    return MetadataResponse(
        book_id=book_id,
        fields=metadata.fields or {},
        updated_at=metadata.updated_at,
    )


@router.post("/{book_id}/review/complete", response_model=MetadataResponse)
async def complete_review(
    book_id: UUID,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    """Explicitly finish the human review and complete the workflow.

    Requires metadata to exist and no queued/running jobs. Idempotent: calling
    it on an already-complete book is a no-op.
    """
    result = await db.execute(select(BookMetadata).where(BookMetadata.book_id == book_id))
    metadata = result.scalar_one_or_none()
    if metadata is None or not (metadata.fields or {}):
        raise HTTPException(
            status_code=400,
            detail="Cannot complete review: no metadata has been saved yet.",
        )

    running = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    if running.scalars().first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot complete review while jobs are still running.",
        )

    if book.status != BookStatus.COMPLETE:
        human = await StageManager.get_stage(db, book_id, "human_review")
        if human is None:
            human = await StageManager.initiate_stage(db, book_id, "human_review")
        if human.status in (
            StageStatus.INITIATED,
            StageStatus.FAILED,
            StageStatus.CANCELLED,
        ):
            human = await StageManager.start_stage(db, book_id, "human_review")
        if human.status != StageStatus.COMPLETED:
            await StageManager.complete_stage(db, book_id, "human_review")

        completion = await StageManager.get_stage(db, book_id, "completion")
        if completion is None:
            completion = await StageManager.initiate_stage(db, book_id, "completion")
        if completion.status in (
            StageStatus.INITIATED,
            StageStatus.FAILED,
            StageStatus.CANCELLED,
        ):
            completion = await StageManager.start_stage(db, book_id, "completion")
        if completion.status != StageStatus.COMPLETED:
            await StageManager.complete_stage(db, book_id, "completion")

        await db.commit()
        await db.refresh(metadata)

    return MetadataResponse(
        book_id=book_id,
        fields=metadata.fields or {},
        updated_at=metadata.updated_at,
    )


@router.get(
    "/{book_id}/metadata/fields",
    response_model=Page[MetadataFieldDefinition],
)
async def get_field_definitions(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
) -> Page[MetadataFieldDefinition]:
    items = ALL_METADATA_FIELDS[pagination.offset : pagination.offset + pagination.page_size]
    return Page[MetadataFieldDefinition].create(
        items=items,
        total=len(ALL_METADATA_FIELDS),
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/{book_id}/metadata/evidence",
    response_model=Page[FieldEvidenceResponse],
)
async def get_metadata_evidence(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> Page[FieldEvidenceResponse]:
    """Return per-field provenance (confidence, source page, method)."""
    total = int(
        await db.scalar(select(func.count(MetadataFieldEvidence.id)).where(MetadataFieldEvidence.book_id == book.id))
        or 0
    )
    result = await db.execute(
        select(MetadataFieldEvidence)
        .where(MetadataFieldEvidence.book_id == book.id)
        .order_by(MetadataFieldEvidence.field_name)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    rows = result.scalars().all()
    return Page[FieldEvidenceResponse].create(
        items=[FieldEvidenceResponse.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{book_id}/llm-runs", response_model=Page[LlmRunResponse])
async def get_llm_runs(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> Page[LlmRunResponse]:
    book_id = book.id

    job_ids_result = await db.execute(select(Job.id).where(Job.book_id == book_id, Job.job_type == JobType.LLM))
    job_ids = [row[0] for row in job_ids_result.all()]

    if not job_ids:
        return Page[LlmRunResponse].create(
            items=[],
            total=0,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    total = int(await db.scalar(select(func.count(LlmRun.id)).where(LlmRun.job_id.in_(job_ids))) or 0)
    runs_result = await db.execute(
        select(LlmRun)
        .where(LlmRun.job_id.in_(job_ids))
        .order_by(LlmRun.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    runs = runs_result.scalars().all()
    return Page[LlmRunResponse].create(
        items=[LlmRunResponse.model_validate(r) for r in runs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
