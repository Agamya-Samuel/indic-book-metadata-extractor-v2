from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import PaginationParams, get_owned_book_or_404, get_pagination
from app.core.database import get_db
from app.models.book import Book
from app.models.stage import BookStageStatus, get_current_stages
from app.schemas.common import Page
from app.schemas.stage import StageStatusResponse

router = APIRouter()


@router.get("/{book_id}/stages", response_model=Page[StageStatusResponse])
async def list_stages(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> Page[StageStatusResponse]:
    total = int(
        await db.scalar(
            select(func.count(BookStageStatus.id)).where(
                BookStageStatus.book_id == book.id
            )
        )
        or 0
    )
    result = await db.execute(
        select(BookStageStatus)
        .where(BookStageStatus.book_id == book.id)
        .order_by(BookStageStatus.stage_name, BookStageStatus.attempt)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    rows = result.scalars().all()
    return Page[StageStatusResponse].create(
        items=[StageStatusResponse.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{book_id}/stages/current", response_model=Page[StageStatusResponse])
async def list_current_stages(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
) -> Page[StageStatusResponse]:
    rows = await get_current_stages(book.id)
    items = rows[pagination.offset : pagination.offset + pagination.page_size]
    return Page[StageStatusResponse].create(
        items=[StageStatusResponse.model_validate(r) for r in items],
        total=len(rows),
        page=pagination.page,
        page_size=pagination.page_size,
    )
