"""Media endpoints that accept a session or a resource-scoped signed token.

These live outside the books/pages routers because those carry the
approved-session dependency, which would reject the cookie-less ``<img>``
request that a signed URL exists to serve.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import can_view_full_book, get_optional_user
from app.core.config import settings
from app.core.database import get_db
from app.core.media_tokens import page_scope, thumbnail_scope, verify_media_token
from app.models.book import Book
from app.models.page import Page
from app.models.user import User
from app.services import pdf_service, storage

router = APIRouter()


async def _page_for_media(page_id: UUID, db: AsyncSession, user: User | None, token: str | None) -> Page:
    """Session auth, or a signed token scoped to this page for ``<img>`` tags."""
    if user is not None:
        page = await db.get(Page, page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="Page not found")
        book = await db.get(Book, page.book_id)
        if book is None or not can_view_full_book(book, user):
            raise HTTPException(status_code=404, detail="Page not found")
        return page

    scope, resource = page_scope(page_id)
    if not verify_media_token(token, scope, resource):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    page = await db.get(Page, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.get("/books/{book_id}/pages/{page_number}/thumbnail")
async def get_thumbnail(
    book_id: UUID,
    page_number: int,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> FileResponse:
    if user is not None:
        book = await db.get(Book, book_id)
        if book is None or not can_view_full_book(book, user):
            raise HTTPException(status_code=404, detail="Book not found")
    else:
        scope, resource = thumbnail_scope(book_id)
        if not verify_media_token(token, scope, resource):
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        book = await db.get(Book, book_id)
        if book is None:
            raise HTTPException(status_code=404, detail="Book not found")

    if page_number < 1 or (book.total_pages and page_number > book.total_pages):
        raise HTTPException(status_code=404, detail="Page number out of range")

    thumb_path = storage.thumbnail_path(str(book.id), page_number)
    if not thumb_path.exists():
        pdf_path = storage.original_pdf_path(str(book.id))
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Original PDF not found")
        try:
            await asyncio.to_thread(pdf_service.render_thumbnail, pdf_path, page_number, thumb_path)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to render thumbnail")

    return FileResponse(thumb_path, media_type="image/jpeg")


@router.get("/pages/{page_id}/preprocessing/preview")
async def get_preprocessing_preview(
    page_id: UUID,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> FileResponse:
    page = await _page_for_media(page_id, db, user, token)
    preview_path = storage.preview_image_path(str(page.book_id), str(page.id))
    if not preview_path.exists():
        raise HTTPException(status_code=404, detail="No preview available")
    return FileResponse(preview_path, media_type="image/png")


@router.get("/pages/{page_id}/image")
async def get_page_image(
    page_id: UUID,
    token: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> FileResponse:
    page = await _page_for_media(page_id, db, user, token)
    if page.processed_image_path:
        processed = Path(settings.storage_path) / page.processed_image_path
        if processed.exists():
            return FileResponse(processed, media_type="image/png")

    if page.image_path:
        original = Path(settings.storage_path) / page.image_path
        if original.exists():
            return FileResponse(original, media_type="image/png")

    raise HTTPException(status_code=404, detail="Page image not found")
