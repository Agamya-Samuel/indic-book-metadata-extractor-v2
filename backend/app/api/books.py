from pathlib import Path
from uuid import UUID

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.base import uuid
from app.models.book import Book, BookStatus
from app.models.page import Page
from app.schemas.book import (
    BookDetail,
    BookUploadResponse,
    PageResponse,
    PageSelectionRequest,
    PageSelectionResponse,
)
from app.services import pdf_service, storage

router = APIRouter()


async def _get_book(book_id: UUID, db: AsyncSession) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@router.post("/upload", response_model=BookUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_book(
    file: UploadFile,
    title: str | None = None,
    language: str = "tel",
    db: AsyncSession = Depends(get_db),
) -> BookUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    if language not in ("tel", "hin"):
        raise HTTPException(status_code=422, detail="language must be 'tel' or 'hin'")

    book_id = uuid.uuid4()
    pdf_path = storage.original_pdf_path(str(book_id))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pdf_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            f.write(chunk)

    try:
        page_count = pdf_service.get_page_count(pdf_path)
    except Exception:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF")

    book = Book(
        id=book_id,
        title=title,
        filename=file.filename,
        language=language,
        total_pages=page_count,
        status=BookStatus.UPLOADED,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return BookUploadResponse.model_validate(book)


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(book_id: UUID, db: AsyncSession = Depends(get_db)) -> BookDetail:
    book = await _get_book(book_id, db)
    return BookDetail.model_validate(book)


@router.get("/{book_id}/pages/{page_number}/thumbnail")
async def get_thumbnail(
    book_id: UUID,
    page_number: int,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    book = await _get_book(book_id, db)
    if page_number < 1 or (book.total_pages and page_number > book.total_pages):
        raise HTTPException(status_code=404, detail="Page number out of range")

    thumb_path = storage.thumbnail_path(str(book_id), page_number)
    if not thumb_path.exists():
        pdf_path = storage.original_pdf_path(str(book_id))
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Original PDF not found")
        try:
            pdf_service.render_thumbnail(pdf_path, page_number, thumb_path)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to render thumbnail")

    return FileResponse(thumb_path, media_type="image/jpeg")


@router.post("/{book_id}/pages", response_model=PageSelectionResponse)
async def select_pages(
    book_id: UUID,
    body: PageSelectionRequest,
    db: AsyncSession = Depends(get_db),
) -> PageSelectionResponse:
    book = await _get_book(book_id, db)
    if not book.total_pages:
        raise HTTPException(status_code=400, detail="Book has no pages")

    unique_pages = sorted(set(body.selected_pages))
    for pn in unique_pages:
        if pn < 1 or pn > book.total_pages:
            raise HTTPException(
                status_code=422,
                detail=f"Page {pn} out of range (1-{book.total_pages})",
            )

    result = await db.execute(select(Page).where(Page.book_id == book_id))
    existing = result.scalars().all()
    for p in existing:
        if p.image_path:
            fp = Path(settings.storage_path) / p.image_path
            fp.unlink(missing_ok=True)
        await db.delete(p)
    await db.flush()

    pdf_path = storage.original_pdf_path(str(book_id))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Original PDF not found")

    for pn in unique_pages:
        out = storage.full_page_path(str(book_id), pn)
        pdf_service.render_full_page(pdf_path, pn, out)
        page = Page(
            book_id=book_id,
            page_number=pn,
            image_path=storage.relative(out),
        )
        db.add(page)

    book.status = BookStatus.PAGES_SELECTED
    await db.commit()

    return PageSelectionResponse(
        book_id=book_id,
        selected_count=len(unique_pages),
        status=book.status,
    )


@router.get("/{book_id}/pages", response_model=list[PageResponse])
async def list_pages(book_id: UUID, db: AsyncSession = Depends(get_db)) -> list[PageResponse]:
    await _get_book(book_id, db)
    result = await db.execute(
        select(Page).where(Page.book_id == book_id).order_by(Page.page_number)
    )
    pages = result.scalars().all()
    return [PageResponse.model_validate(p) for p in pages]
