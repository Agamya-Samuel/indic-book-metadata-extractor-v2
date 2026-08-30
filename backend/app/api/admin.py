"""Admin HTTP endpoints: library stats, book CRUD, cross-book job control."""
from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.book import BookListResponse, BookSearchResult
from app.services import admin_service
from app.services.search_service import SearchService

router = APIRouter()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.get_admin_stats(db)


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------

@router.get("/books", response_model=BookListResponse)
async def admin_list_books(
    query: str | None = Query(default=None, alias="query"),
    language: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    has_metadata: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    items_raw, total = await SearchService.list_books(
        db, language=language, status=status_, page=page, page_size=page_size,
    )

    if query and query.strip():
        # When a search term is provided, switch to similarity search.
        items_raw, total = await SearchService.search_books(
            db, q=query.strip(), language=language, status=status_,
            page=page, page_size=page_size,
        )

    items = []
    for item in items_raw:
        if has_metadata is True and not item.get("metadata_fields"):
            continue
        if has_metadata is False and item.get("metadata_fields"):
            continue
        thumb = f"/api/books/{item['id']}/pages/1/thumbnail"
        items.append(BookSearchResult(
            id=item["id"],
            title=item["title"],
            filename=item["filename"],
            language=item["language"],
            status=item["status"],
            total_pages=item["total_pages"],
            created_at=item["created_at"],
            metadata_fields=item["metadata_fields"],
            thumbnail_url=thumb,
        ))

    total = len(items) if has_metadata is not None else total
    return BookListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_book(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await admin_service.delete_book(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")


@router.post("/books/{book_id}/reset")
async def admin_reset_book(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        book = await admin_service.reset_book(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": str(book.id), "status": book.status}


@router.post("/books/{book_id}/rerun-ocr", status_code=status.HTTP_201_CREATED)
async def admin_rerun_ocr(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        job = await admin_service.rerun_ocr(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book_id),
        "status": job.status,
    }


@router.post("/books/{book_id}/rerun-extraction", status_code=status.HTTP_201_CREATED)
async def admin_rerun_extraction(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        job = await admin_service.rerun_extraction(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book_id),
        "status": job.status,
    }


# ---------------------------------------------------------------------------
# Jobs (cross-book)
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def admin_list_jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None, alias="job_type"),
    book_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items, total = await admin_service.list_admin_jobs(
        db, status=status, job_type=job_type, book_id=book_id,
        page=page, page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.post("/jobs/{job_id}/cancel")
async def admin_cancel_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        job = await admin_service.cancel_job(db, job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"id": str(job.id), "status": job.status}