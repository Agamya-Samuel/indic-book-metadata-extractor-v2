from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_owned_book_or_404
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.models.metadata_field_evidence import MetadataFieldEvidence
from app.models.stage import StageStatus
from app.schemas.metadata import (
    ALL_METADATA_FIELDS,
    LlmRunResponse,
    MetadataFieldDefinition,
    MetadataResponse,
    MetadataUpdateRequest,
)
from app.services.stage_manager import StageManager
from pydantic import BaseModel


class FieldEvidenceResponse(BaseModel):
    field_name: str
    value: str | None
    confidence: float | None
    extraction_method: str
    source_page_number: int | None
    source_text_snippet: str | None

    model_config = {"from_attributes": True}

router = APIRouter()


@router.get("/{book_id}/metadata", response_model=MetadataResponse)
async def get_metadata(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    book_id = book.id

    result = await db.execute(
        select(BookMetadata).where(BookMetadata.book_id == book_id)
    )
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
    result = await db.execute(
        select(BookMetadata)
        .where(BookMetadata.book_id == book_id)
        .with_for_update()
    )
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
    result = await db.execute(
        select(BookMetadata).where(BookMetadata.book_id == book_id)
    )
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
    response_model=list[MetadataFieldDefinition],
)
async def get_field_definitions(
    book: Book = Depends(get_owned_book_or_404),
) -> list[MetadataFieldDefinition]:
    return ALL_METADATA_FIELDS


@router.get(
    "/{book_id}/metadata/evidence",
    response_model=list[FieldEvidenceResponse],
)
async def get_metadata_evidence(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> list[FieldEvidenceResponse]:
    """Return per-field provenance (confidence, source page, method)."""
    result = await db.execute(
        select(MetadataFieldEvidence)
        .where(MetadataFieldEvidence.book_id == book.id)
        .order_by(MetadataFieldEvidence.field_name)
    )
    rows = result.scalars().all()
    return [FieldEvidenceResponse.model_validate(r) for r in rows]


@router.get("/{book_id}/llm-runs", response_model=list[LlmRunResponse])
async def get_llm_runs(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> list[LlmRunResponse]:
    book_id = book.id

    jobs_result = await db.execute(
        select(Job.id).where(Job.book_id == book_id, Job.job_type == JobType.LLM)
    )
    job_ids = [row[0] for row in jobs_result.all()]

    if not job_ids:
        return []

    runs_result = await db.execute(
        select(LlmRun)
        .where(LlmRun.job_id.in_(job_ids))
        .order_by(LlmRun.created_at.desc())
    )
    runs = runs_result.scalars().all()
    return [LlmRunResponse.model_validate(r) for r in runs]
