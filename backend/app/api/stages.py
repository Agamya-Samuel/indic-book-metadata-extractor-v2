from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_book_or_404
from app.core.database import get_db
from app.models.book import Book
from app.models.stage import BookStageStatus, get_current_stages, get_stage
from app.schemas.stage import StageStatusResponse

router = APIRouter()


@router.get("/{book_id}/stages", response_model=list[StageStatusResponse])
async def list_stages(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[StageStatusResponse]:
    await get_book_or_404(book_id, db)
    result = await db.execute(
        select(BookStageStatus)
        .where(BookStageStatus.book_id == book_id)
        .order_by(BookStageStatus.stage_name, BookStageStatus.attempt)
    )
    rows = result.scalars().all()
    return [StageStatusResponse.model_validate(r) for r in rows]


@router.get("/{book_id}/stages/current", response_model=list[StageStatusResponse])
async def list_current_stages(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[StageStatusResponse]:
    await get_book_or_404(book_id, db)
    rows = await get_current_stages(book_id)
    return [StageStatusResponse.model_validate(r) for r in rows]
