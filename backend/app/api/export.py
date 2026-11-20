"""Metadata export endpoints: one book or a caller-scoped selection."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_context, get_owned_book_or_404, require_approved_user
from app.core.database import get_db
from app.models.book import Book
from app.models.user import User, UserRole
from app.schemas.export import ExportFormat, ExportRequest
from app.services import audit_service, export_service
from app.services.audit_service import AuditAction, AuditContext

router = APIRouter(dependencies=[Depends(require_approved_user)])


def _scope_label(rows: list[export_service.ExportRow]) -> str:
    if len(rows) == 1:
        return f"book-{str(rows[0].book_id)[:8]}"
    return f"{len(rows)}-books"


def _file_response(
    rows: list[export_service.ExportRow],
    fmt: ExportFormat,
    include_details: bool,
) -> Response:
    body, media_type, extension = export_service.render(rows, fmt, include_details)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    filename = f"indic-books_{_scope_label(rows)}_{stamp}.{extension}"
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/books/{book_id}/export")
async def export_book(
    book: Book = Depends(get_owned_book_or_404),
    format: ExportFormat = Query(default="csv"),
    include_details: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
) -> Response:
    """Export one book's reviewed metadata as a download."""
    rows = await export_service.collect_rows(db, book_ids=[book.id])
    if not rows:
        raise HTTPException(status_code=404, detail="This book has no reviewed metadata to export")
    await audit_service.record_isolated(
        db,
        action=AuditAction.EXPORT_METADATA,
        ctx=ctx,
        description=f"Exported metadata for book {book.title or book.filename}",
        resource_type="book",
        resource_id=book.id,
        resource_label=book.title or book.filename,
        subject_user_id=book.owner_id,
        details={"format": format, "include_details": include_details, "row_count": len(rows)},
    )
    return _file_response(rows, format, include_details)


@router.post("/export")
async def export_metadata(
    body: ExportRequest,
    user: User = Depends(require_approved_user),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
) -> Response:
    """Export selected books or a filtered slice of the caller's library."""
    owner_id = body.owner_id
    if user.role != UserRole.ADMIN:
        if body.owner_id is not None and body.owner_id != user.id:
            # Do not confirm that another user's books exist.
            raise HTTPException(status_code=404, detail="Book not found")
        owner_id = user.id

    if body.book_ids:
        result = await db.execute(select(Book).where(Book.id.in_(set(body.book_ids))))
        visible = {book.id: book for book in result.scalars().all()}
        for book_id in set(body.book_ids):
            book = visible.get(book_id)
            if book is None or (user.role != UserRole.ADMIN and book.owner_id != user.id):
                raise HTTPException(status_code=404, detail="Book not found")

    try:
        rows = await export_service.collect_rows(
            db,
            book_ids=body.book_ids,
            owner_id=owner_id,
            language=body.language,
            status=body.status,
        )
    except export_service.ExportTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No books with reviewed metadata matched the export",
        )

    await audit_service.record_isolated(
        db,
        action=AuditAction.EXPORT_METADATA,
        ctx=ctx,
        description=f"Exported metadata for {len(rows)} book(s)",
        resource_type="book",
        details={
            "format": body.format,
            "include_details": body.include_details,
            "row_count": len(rows),
            "book_ids": body.book_ids,
            "language": body.language,
            "status": body.status,
            "owner_id": str(owner_id) if owner_id else None,
        },
    )
    return _file_response(rows, body.format, body.include_details)
