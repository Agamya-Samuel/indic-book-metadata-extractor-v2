"""Bulk operations: metadata export/import and Wikibase QuickStatements."""

import csv
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.api.deps import get_audit_context, require_admin
from app.models.book import Book
from app.models.metadata import BookMetadata
from app.schemas.bulk import (
    BulkImportResult,
    BulkStatsResponse,
)
from app.schemas.export import ExportFormat
from app.schemas.metadata import FIELD_WIKIDATA
from app.services import audit_service, export_service
from app.services.audit_service import AuditAction, AuditContext, AuditResult

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=BulkStatsResponse)
async def get_bulk_stats(
    db: AsyncSession = Depends(get_db),
) -> BulkStatsResponse:
    """Get summary statistics for the library."""
    total = await db.scalar(select(func.count(Book.id)))

    with_meta = await db.scalar(select(func.count(BookMetadata.id)))

    lang_result = await db.execute(select(Book.language, func.count(Book.id)).group_by(Book.language))
    languages = {row[0]: row[1] for row in lang_result.all()}

    status_result = await db.execute(select(Book.status, func.count(Book.id)).group_by(Book.status))
    statuses = {row[0]: row[1] for row in status_result.all()}

    return BulkStatsResponse(
        total_books=total or 0,
        books_with_metadata=with_meta or 0,
        languages=languages,
        statuses=statuses,
    )


@router.post("/export")
async def bulk_export(
    language: str | None = Query(default=None),
    status: str | None = Query(default=None),
    format: ExportFormat = Query(default="csv"),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
) -> Response:
    """Export every eligible book's metadata as a download (admin scope)."""
    try:
        rows = await export_service.collect_rows(db, language=language, status=status)
    except export_service.ExportTooLarge as exc:
        raise HTTPException(status_code=413, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=404, detail="No books found matching filters")

    body, media_type, extension = export_service.render(rows, format)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    scope = "all-books" if len(rows) > 1 else f"book-{str(rows[0].book_id)[:8]}"
    filename = f"metadata_export_{scope}_{timestamp}.{extension}"

    await audit_service.record_isolated(
        db,
        action=AuditAction.EXPORT_METADATA,
        ctx=ctx,
        description=f"Bulk exported metadata for {len(rows)} book(s)",
        resource_type="book",
        details={
            "format": format,
            "row_count": len(rows),
            "language": language,
            "status": status,
        },
    )
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/import", response_model=BulkImportResult)
async def bulk_import(
    file: UploadFile = File(...),
    mode: str = Query(default="merge"),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
):
    """Import cleaned metadata from a CSV file.

    The CSV must have a `book_id` column. Each row's metadata fields are
    merged (mode=merge) or replaced (mode=overwrite) into the book's record.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    max_import_bytes = 10 * 1024 * 1024
    max_import_rows = 5000
    content = await file.read(max_import_bytes + 1)
    if len(content) > max_import_bytes:
        raise HTTPException(status_code=413, detail="CSV import is limited to 10 MB")
    try:
        text = content.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")
    reader = csv.DictReader(io.StringIO(text))

    if "book_id" not in (reader.fieldnames or []):
        raise HTTPException(status_code=400, detail="CSV must contain a 'book_id' column")

    total_rows = 0
    books_updated = 0
    books_not_found = 0
    fields_changed = 0
    errors: list[str] = []

    # Metadata field names (everything except book-level and provenance columns).
    # Current exports prefix book columns (book_title, ...), so `title` and
    # `language` in those files are metadata fields. Legacy exports used bare
    # `title`/`language`, which must keep their old book-level meaning.
    fieldnames = set(reader.fieldnames or [])
    book_level_cols = {
        "book_id",
        "status",
        "total_pages",
        "uploaded_at",
        "reviewed_at",
        "filename",
    }
    if "book_title" in fieldnames:
        book_level_cols |= {"book_title", "book_language", "source_filename"}
    else:
        book_level_cols |= {"title", "language"}
    meta_field_names = [c for c in (reader.fieldnames or []) if c not in book_level_cols]

    for row_num, row in enumerate(reader, start=2):
        if total_rows >= max_import_rows:
            errors.append(f"Import stopped at {max_import_rows} rows; split the file")
            break
        total_rows += 1
        book_id_str = row.get("book_id", "").strip()

        if not book_id_str:
            errors.append(f"Row {row_num}: empty book_id")
            continue

        try:
            book_id = uuid.UUID(book_id_str)
        except ValueError:
            errors.append(f"Row {row_num}: invalid book_id '{book_id_str}'")
            continue

        # Fetch book
        book_result = await db.execute(select(Book).where(Book.id == book_id))
        book = book_result.scalar_one_or_none()

        if book is None:
            books_not_found += 1
            continue

        # `book_title` (or the legacy `title`) is a book-level column, so a
        # re-import must restore it on the book rather than drop it from the
        # metadata fields. The book language is not changed on import: it drives
        # OCR routing and requires a re-run.
        changed = False
        if "book_title" in fieldnames:
            title_value = (row.get("book_title") or "").strip()
        else:
            title_value = (row.get("title") or "").strip()
        if title_value and book.title != title_value:
            book.title = title_value
            changed = True

        # Collect new metadata values from CSV.
        new_fields = {}
        new_custom: dict[str, str] = {}
        for col in meta_field_names:
            value = (row.get(col) or "").strip()
            if not value:
                continue
            if col.startswith("custom:"):
                name = col[len("custom:") :].strip()
                if name:
                    new_custom[name] = value
            else:
                new_fields[col] = value

        if not new_fields and not new_custom and not changed:
            continue

        if new_fields or new_custom:
            # Get or create metadata record
            meta_result = await db.execute(select(BookMetadata).where(BookMetadata.book_id == book_id))
            metadata = meta_result.scalar_one_or_none()

            if metadata is None:
                fields = dict(new_fields)
                if new_custom:
                    fields["custom_fields"] = new_custom
                metadata = BookMetadata(book_id=book_id, fields=fields)
                db.add(metadata)
                fields_changed += len(new_fields) + len(new_custom)
            elif mode == "overwrite":
                fields = dict(new_fields)
                if new_custom:
                    fields["custom_fields"] = new_custom
                metadata.fields = fields
                flag_modified(metadata, "fields")
                fields_changed += len(new_fields) + len(new_custom)
            else:  # merge
                existing = dict(metadata.fields or {})
                for k, v in new_fields.items():
                    if existing.get(k) != v:
                        existing[k] = v
                        fields_changed += 1
                if new_custom:
                    existing_custom = existing.get("custom_fields")
                    merged_custom = dict(existing_custom) if isinstance(existing_custom, dict) else {}
                    for k, v in new_custom.items():
                        if merged_custom.get(k) != v:
                            merged_custom[k] = v
                            fields_changed += 1
                    existing["custom_fields"] = merged_custom
                metadata.fields = existing
                flag_modified(metadata, "fields")
            changed = True

        if changed:
            books_updated += 1

    await db.commit()

    await audit_service.record_isolated(
        db,
        action=AuditAction.BULK_IMPORT,
        ctx=ctx,
        description=f"Imported metadata from {file.filename} ({mode} mode)",
        resource_type="bulk_import",
        details={
            "filename": file.filename,
            "mode": mode,
            "total_rows": total_rows,
            "books_updated": books_updated,
            "books_not_found": books_not_found,
            "fields_changed": fields_changed,
            "error_count": len(errors),
        },
        result=AuditResult.SUCCESS if not errors else AuditResult.FAILURE,
        error_message="; ".join(errors[:5]) if errors else None,
    )
    return BulkImportResult(
        total_rows=total_rows,
        books_updated=books_updated,
        books_not_found=books_not_found,
        fields_changed=fields_changed,
        errors=errors[:50],  # cap error list
    )


@router.post("/export-wikibase")
async def bulk_export_wikibase(
    language: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
):
    """Generate QuickStatements TSV for Wikibase upload.

    Each book becomes a new item. Properties are mapped using FIELD_WIKIDATA,
    resolved to local Wikibase P-IDs via property-mapping.json if available.
    Returns a .tsv file compatible with QuickStatements.
    """
    prop_map = export_service.load_property_mapping()

    query = select(Book, BookMetadata).outerjoin(BookMetadata, Book.id == BookMetadata.book_id)

    if language:
        query = query.where(Book.language == language)

    query = query.order_by(Book.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No books found")

    lines: list[str] = []

    # Resolve P31 and Q571 from mapping, fall back to Wikidata IDs
    p31_id = prop_map.get("P31", "P31")
    q571_id = prop_map.get("Q571", "Q571")
    p407_id = prop_map.get("P407", "P407")

    for book, metadata in rows:
        fields = metadata.fields if metadata and metadata.fields else {}

        lines.append("CREATE")

        title = fields.get("title") or book.title or "Untitled"
        lines.append(f'LAST\tLen\t"{_escape_qs(title)}"')

        for field_name, wikidata_prop in FIELD_WIKIDATA.items():
            if wikidata_prop is None:
                continue

            value = fields.get(field_name)
            if not value:
                continue

            # Resolve local property ID from mapping
            wikidata_prop = export_service.wikibase_property_id(field_name, value, wikidata_prop)
            local_prop = prop_map.get(wikidata_prop, wikidata_prop)
            rendered = export_service.wikibase_tsv_value(field_name, value, book.language or "")
            if rendered is None:
                continue
            lines.append(f"LAST\t{local_prop}\t{rendered}")

        # instance of = book
        lines.append(f"LAST\t{p31_id}\t{q571_id}")

        # Add source language if available
        lang = fields.get("language") or book.language
        if lang:
            lang_map = {"tel": "Q809", "hin": "Q1568"}
            lang_qid = lang_map.get(lang)
            if lang_qid:
                local_lang_qid = prop_map.get(lang_qid, lang_qid)
                lines.append(f"LAST\t{p407_id}\t{local_lang_qid}")

    tsv_content = "\n".join(lines) + "\n"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"wikibase_quickstatements_{timestamp}.tsv"

    await audit_service.record_isolated(
        db,
        action=AuditAction.EXPORT_WIKIBASE,
        ctx=ctx,
        description=f"Generated QuickStatements TSV for {len(rows)} book(s)",
        resource_type="wikibase",
        details={"book_count": len(rows), "language": language},
    )
    return StreamingResponse(
        iter([tsv_content]),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _escape_qs(value: str) -> str:
    """Escape a value for QuickStatements (double quotes and backslashes)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
