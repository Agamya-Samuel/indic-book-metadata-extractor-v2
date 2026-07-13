"""Bulk operations: export/import metadata CSV, Wikibase QuickStatements export."""

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book
from app.models.metadata import BookMetadata
from app.schemas.bulk import (
    BulkImportResult,
    BulkStatsResponse,
)
from app.schemas.metadata import FIELD_WIKIDATA, FullMetadata

logger = logging.getLogger(__name__)

router = APIRouter()

# Ordered list of metadata columns for CSV export (book_id first, then all fields)
METADATA_COLUMNS = ["book_id", "title", "language", "filename"] + [
    f for f in FullMetadata.model_fields if f != "custom_fields"
]


def _load_property_mapping() -> dict[str, str]:
    """Load Wikibase property mapping (Wikidata P-ID → local P-ID).

    Falls back to hardcoded FIELD_WIKIDATA values if mapping file not found.
    """
    mapping_path = Path(settings.property_mapping_path)
    if mapping_path.exists():
        try:
            with open(mapping_path) as f:
                mapping = json.load(f)
            logger.info("Loaded property mapping from %s (%d entries)", mapping_path, len(mapping))
            return mapping
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load property mapping from %s: %s", mapping_path, e)

    logger.info("No property mapping file found, using hardcoded Wikidata P-IDs")
    return {}


PROPERTY_MAPPING: dict[str, str] = {}


@router.get("/stats", response_model=BulkStatsResponse)
async def get_bulk_stats(
    db: AsyncSession = Depends(get_db),
) -> BulkStatsResponse:
    """Get summary statistics for the library."""
    total = await db.scalar(select(func.count(Book.id)))

    with_meta = await db.scalar(
        select(func.count(BookMetadata.id))
    )

    lang_result = await db.execute(
        select(Book.language, func.count(Book.id)).group_by(Book.language)
    )
    languages = {row[0]: row[1] for row in lang_result.all()}

    status_result = await db.execute(
        select(Book.status, func.count(Book.id)).group_by(Book.status)
    )
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
    format: str = Query(default="csv"),
    db: AsyncSession = Depends(get_db),
):
    """Export all book metadata as CSV.

    Returns a CSV file with one row per book. The first column is `book_id`
    (UUID) which is used for matching during re-import.
    """
    # Build query: join Book + BookMetadata
    query = (
        select(Book, BookMetadata)
        .outerjoin(BookMetadata, Book.id == BookMetadata.book_id)
    )

    if language:
        query = query.where(Book.language == language)
    if status:
        query = query.where(Book.status == status)

    query = query.order_by(Book.created_at.desc())

    result = await db.execute(query)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="No books found matching filters")

    # Build CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(METADATA_COLUMNS)

    for book, metadata in rows:
        fields = metadata.fields if metadata and metadata.fields else {}
        row = [
            str(book.id),
            book.title or "",
            book.language or "",
            book.filename or "",
        ]
        for col in METADATA_COLUMNS[4:]:  # skip book_id, title, language, filename
            row.append(fields.get(col, "") or "")
        writer.writerow(row)

    output.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"metadata_export_{timestamp}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=BulkImportResult)
async def bulk_import(
    file: UploadFile = File(...),
    mode: str = Query(default="merge"),
    db: AsyncSession = Depends(get_db),
):
    """Import cleaned metadata from a CSV file.

    The CSV must have a `book_id` column. Each row's metadata fields are
    merged (mode=merge) or replaced (mode=overwrite) into the book's record.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    if "book_id" not in (reader.fieldnames or []):
        raise HTTPException(
            status_code=400, detail="CSV must contain a 'book_id' column"
        )

    total_rows = 0
    books_updated = 0
    books_not_found = 0
    fields_changed = 0
    errors: list[str] = []

    # Metadata field names (everything except book_id and book-level fields)
    book_level_cols = {"book_id", "title", "language", "filename"}
    meta_field_names = [
        c for c in (reader.fieldnames or []) if c not in book_level_cols
    ]

    for row_num, row in enumerate(reader, start=2):
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

        # Collect new metadata values from CSV
        new_fields = {}
        for col in meta_field_names:
            value = row.get(col, "").strip()
            if value:
                new_fields[col] = value

        if not new_fields:
            continue

        # Get or create metadata record
        meta_result = await db.execute(
            select(BookMetadata).where(BookMetadata.book_id == book_id)
        )
        metadata = meta_result.scalar_one_or_none()

        if metadata is None:
            metadata = BookMetadata(book_id=book_id, fields=new_fields)
            db.add(metadata)
            fields_changed += len(new_fields)
        elif mode == "overwrite":
            metadata.fields = new_fields
            flag_modified(metadata, "fields")
            fields_changed += len(new_fields)
        else:  # merge
            existing = metadata.fields or {}
            for k, v in new_fields.items():
                if existing.get(k) != v:
                    existing[k] = v
                    fields_changed += 1
            metadata.fields = existing
            flag_modified(metadata, "fields")

        books_updated += 1

    await db.commit()

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
):
    """Generate QuickStatements TSV for Wikibase upload.

    Each book becomes a new item. Properties are mapped using FIELD_WIKIDATA,
    resolved to local Wikibase P-IDs via property-mapping.json if available.
    Returns a .tsv file compatible with QuickStatements.
    """
    prop_map = _load_property_mapping()

    query = (
        select(Book, BookMetadata)
        .outerjoin(BookMetadata, Book.id == BookMetadata.book_id)
    )

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
            local_prop = prop_map.get(wikidata_prop, wikidata_prop)
            escaped = _escape_qs(value)
            lines.append(f'LAST\t{local_prop}\t"{escaped}"')

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

    return StreamingResponse(
        iter([tsv_content]),
        media_type="text/tab-separated-values",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _escape_qs(value: str) -> str:
    """Escape a value for QuickStatements (double quotes and backslashes)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
