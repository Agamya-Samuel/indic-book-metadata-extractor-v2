import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_view_full_book, get_optional_current_user, get_visible_book_or_404
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.user import User
from app.schemas.book import (
    BookDetailResponse,
    BookDetailPage,
    BookDetail,
    BookListResponse,
    BookSearchResult,
    FilterOptionsResponse,
)
from app.schemas.job import JobResponse
from app.schemas.metadata import LlmRunResponse
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/books", response_model=BookListResponse)
async def list_library_books(
    query: str | None = Query(default=None, alias="query"),
    language: str | None = Query(default=None),
    status: str | None = Query(default=None),
    genre: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    if query and query.strip():
        items_raw, total = await SearchService.search_books(
            db,
            q=query.strip(),
            language=language,
            status=status,
            genre=genre,
            publisher=publisher,
            page=page,
            page_size=page_size,
            public_only=True,
        )
    else:
        items_raw, total = await SearchService.list_books(
            db,
            language=language,
            status=status,
            page=page,
            page_size=page_size,
            public_only=True,
        )

    items = []
    for item in items_raw:
        thumb = f"/api/books/{item['id']}/pages/1/thumbnail"
        items.append(
            BookSearchResult(
                id=item["id"],
                title=item["title"],
                filename=item["filename"],
                language=item["language"],
                status=item["status"],
                total_pages=item["total_pages"],
                created_at=item["created_at"],
                metadata_fields=item["metadata_fields"],
                thumbnail_url=thumb,
                owner_id=item.get("owner_id"),
                owner_display_name=item.get("owner_display_name"),
            )
        )

    return BookListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/search", response_model=list[BookSearchResult])
async def search_library(
    q: str = Query(..., min_length=1),
    language: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[BookSearchResult]:
    items_raw, _ = await SearchService.search_books(
        db,
        q=q,
        language=language,
        page=1,
        page_size=limit,
        public_only=True,
    )

    results = []
    for item in items_raw:
        thumb = f"/api/books/{item['id']}/pages/1/thumbnail"
        results.append(
            BookSearchResult(
                id=item["id"],
                title=item["title"],
                filename=item["filename"],
                language=item["language"],
                status=item["status"],
                total_pages=item["total_pages"],
                created_at=item["created_at"],
                metadata_fields=item["metadata_fields"],
                thumbnail_url=thumb,
                owner_id=item.get("owner_id"),
                owner_display_name=item.get("owner_display_name"),
            )
        )
    return results


@router.get("/filters", response_model=FilterOptionsResponse)
async def get_filter_options(
    db: AsyncSession = Depends(get_db),
) -> FilterOptionsResponse:
    return await SearchService.get_filter_options(db, public_only=True)


@router.get("/books/{book_id}/detail", response_model=BookDetailResponse)
async def get_book_detail(
    book: Book = Depends(get_visible_book_or_404),
    user: User | None = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookDetailResponse:
    detail = await SearchService.get_book_detail(db, book.id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Book not found")

    raw_book = detail["book"]
    metadata = detail["metadata"]
    can_view_full = can_view_full_book(raw_book, user)

    if can_view_full:
        pages = detail["pages"]
        jobs = detail["jobs"]
        llm_runs = detail["llm_runs"]
        low_conf_count = await SearchService.count_low_confidence_fields(
            db, book.id, settings.low_confidence_threshold
        )
        page_responses = [
            BookDetailPage(
                id=p["id"],
                page_number=p["page_number"],
                image_url=p["image_url"],
                ocr_text=p["ocr_text"],
                ocr_confidence=p["ocr_confidence"],
            )
            for p in pages
        ]
        llm_run_responses = [
            LlmRunResponse.model_validate(r).model_dump() for r in llm_runs
        ]
        job_responses = [JobResponse.model_validate(j).model_dump() for j in jobs]
    else:
        page_responses = []
        llm_run_responses = []
        job_responses = []
        low_conf_count = 0

    book_detail = BookDetail.model_validate(
        {
            **BookDetail.model_validate(raw_book).model_dump(),
            "needs_review": (
                can_view_full
                and raw_book.status == BookStatus.AWAITING_REVIEW
                and low_conf_count > 0
            ),
            "low_confidence_count": low_conf_count,
            "owner_display_name": detail.get("owner_display_name"),
            "owner_email": detail.get("owner_email") if can_view_full else None,
        }
    )

    return BookDetailResponse(
        book=book_detail,
        metadata=metadata.fields if metadata else None,
        metadata_updated_at=metadata.updated_at if metadata else None,
        pages=page_responses,
        llm_runs=llm_run_responses,
        jobs=job_responses,
        can_view_full=can_view_full,
        owner_display_name=detail.get("owner_display_name"),
    )
