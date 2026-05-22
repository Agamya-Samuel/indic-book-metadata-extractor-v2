from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.books import _get_book
from app.core.database import get_db
from app.models.job import Job, JobType
from app.models.llm_run import LlmRun
from app.models.metadata import BookMetadata
from app.schemas.metadata import (
    ALL_METADATA_FIELDS,
    LlmRunResponse,
    MetadataFieldDefinition,
    MetadataResponse,
    MetadataUpdateRequest,
)

router = APIRouter()


@router.get("/{book_id}/metadata", response_model=MetadataResponse)
async def get_metadata(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    await _get_book(book_id, db)

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
    db: AsyncSession = Depends(get_db),
) -> MetadataResponse:
    await _get_book(book_id, db)

    result = await db.execute(
        select(BookMetadata).where(BookMetadata.book_id == book_id)
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
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[MetadataFieldDefinition]:
    await _get_book(book_id, db)
    return ALL_METADATA_FIELDS


@router.get("/{book_id}/llm-runs", response_model=list[LlmRunResponse])
async def get_llm_runs(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[LlmRunResponse]:
    await _get_book(book_id, db)

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
