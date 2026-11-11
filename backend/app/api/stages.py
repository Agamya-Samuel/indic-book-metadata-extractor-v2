from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_book_or_404
from app.core.database import get_db
from app.models.book import Book
from app.models.stage import BookStageStatus, get_current_stages
from app.schemas.stage import StageStatusResponse

router = APIRouter()


@router.get("/{book_id}/stages", response_model=list[StageStatusResponse])
async def list_stages(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> list[StageStatusResponse]:
    result = await db.execute(
        select(BookStageStatus)
        .where(BookStageStatus.book_id == book.id)
        .order_by(BookStageStatus.stage_name, BookStageStatus.attempt)
    )
    rows = result.scalars().all()
    return [StageStatusResponse.model_validate(r) for r in rows]


@router.get("/{book_id}/stages/current", response_model=list[StageStatusResponse])
async def list_current_stages(
    book: Book = Depends(get_owned_book_or_404),
) -> list[StageStatusResponse]:
    rows = await get_current_stages(book.id)
    return [StageStatusResponse.model_validate(r) for r in rows]
