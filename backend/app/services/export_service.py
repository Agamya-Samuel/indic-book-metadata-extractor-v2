"""Metadata export serializers.

One implementation feeds the single-book, dashboard, and admin export
surfaces. Every format reads the reviewed ``BookMetadata.fields`` record,
never the raw LLM output.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import Book
from app.models.metadata import BookMetadata
from app.schemas.metadata import (
    ALL_METADATA_FIELDS,
    FIELD_DISPLAY_NAMES,
    FIELD_WIKIDATA,
)

logger = logging.getLogger(__name__)

ExportFormat = Literal["csv", "xlsx", "json", "jsonl", "wikibase", "openrefine"]

MAX_EXPORT_ROWS = 5000
MAX_EXPORT_BOOK_IDS = 1000

CANONICAL_FIELDS: list[str] = [f.field_name for f in ALL_METADATA_FIELDS]

DETAIL_COLUMNS = [
    "book_title",
    "book_language",
    "source_filename",
    "status",
    "total_pages",
    "uploaded_at",
    "reviewed_at",
]

DETAIL_DISPLAY_NAMES = {
    "book_id": "Book ID",
    "book_title": "Book title",
    "book_language": "Book language",
    "source_filename": "Source filename",
    "status": "Status",
    "total_pages": "Total pages",
    "uploaded_at": "Uploaded at",
    "reviewed_at": "Reviewed at",
}

MEDIA_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "openrefine": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "wikibase": "application/json",
}

EXTENSIONS: dict[str, str] = {
    "csv": "csv",
    "openrefine": "csv",
    "xlsx": "xlsx",
    "json": "json",
    "jsonl": "jsonl",
    "wikibase": "wikibase.json",
}

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

LANGUAGE_QIDS = {
    "tel": "Q809",
    "hin": "Q1568",
    "eng": "Q1860",
}

LANGUAGE_TAGS = {
    "tel": "te",
    "hin": "hi",
    "eng": "en",
}

WIKIBASE_TIME_FIELDS = frozenset({"publication_date", "inception"})
WIKIBASE_MONOLINGUAL_FIELDS = frozenset({"title", "subtitle"})
WIKIBASE_QUANTITY_FIELDS = frozenset({"pages"})
WIKIBASE_GREGORIAN = "http://www.wikidata.org/entity/Q1985727"

_YEAR_RE = re.compile(r"^\s*(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?")
_COUNT_RE = re.compile(r"\d+")
_ISBN10_RE = re.compile(r"^\d{9}[\dXx]$")
_ISBN_SEPARATORS = re.compile(r"[\s-]")


class ExportTooLarge(Exception):
    """Raised when a request would produce more rows than the cap."""


@dataclass
class ExportRow:
    book_id: UUID
    title: str | None
    language: str
    filename: str
    status: str
    total_pages: int | None
    uploaded_at: datetime | None
    reviewed_at: datetime | None
    fields: dict[str, str]
    custom_fields: dict[str, str]


def _text(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _row_from(book: Book, metadata: BookMetadata) -> ExportRow:
    raw = metadata.fields or {}
    custom = raw.get("custom_fields")
    custom_fields = (
        {str(key): _text(value) for key, value in custom.items()}
        if isinstance(custom, dict)
        else {}
    )
    return ExportRow(
        book_id=book.id,
        title=book.title,
        language=book.language or "",
        filename=book.filename,
        status=book.status,
        total_pages=book.total_pages,
        uploaded_at=book.created_at,
        reviewed_at=metadata.updated_at,
        fields={name: _text(raw.get(name)) for name in CANONICAL_FIELDS},
        custom_fields=custom_fields,
    )


async def collect_rows(
    db: AsyncSession,
    *,
    book_ids: list[UUID] | None = None,
    owner_id: UUID | None = None,
    language: str | None = None,
    status: str | None = None,
    max_rows: int = MAX_EXPORT_ROWS,
) -> list[ExportRow]:
    """Load reviewed metadata rows, scoped by the caller before this point."""
    query = (
        select(Book, BookMetadata)
        .join(BookMetadata, BookMetadata.book_id == Book.id)
        .where(BookMetadata.fields.isnot(None))
    )
    if book_ids:
        query = query.where(Book.id.in_(book_ids))
    if owner_id is not None:
        query = query.where(Book.owner_id == owner_id)
    if language:
        query = query.where(Book.language == language)
    if status:
        query = query.where(Book.status == status)

    query = query.order_by(Book.created_at.asc(), Book.id.asc()).limit(max_rows + 1)
    result = await db.execute(query)
    pairs = result.all()

    if len(pairs) > max_rows:
        raise ExportTooLarge(f"Exports are limited to {max_rows} books")

    return [_row_from(book, metadata) for book, metadata in pairs]


def _safe_cell(value: str) -> str:
    if value and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _columns(
    rows: list[ExportRow],
    include_details: bool,
    *,
    openrefine: bool = False,
) -> tuple[list[str], list[str]]:
    columns = ["book_id"]
    if include_details:
        columns.extend(DETAIL_COLUMNS)
    elif openrefine:
        columns.extend(["book_title", "book_language", "source_filename"])
    columns.extend(CANONICAL_FIELDS)

    custom_names = sorted({name for row in rows for name in row.custom_fields})
    columns.extend(f"custom:{name}" for name in custom_names)
    return columns, custom_names


def _value(row: ExportRow, column: str) -> str:
    if column == "book_id":
        return str(row.book_id)
    if column == "book_title":
        return row.title or ""
    if column == "book_language":
        return row.language
    if column == "source_filename":
        return Path(row.filename).name
    if column == "status":
        return row.status
    if column == "total_pages":
        return "" if row.total_pages is None else str(row.total_pages)
    if column == "uploaded_at":
        return _iso(row.uploaded_at) or ""
    if column == "reviewed_at":
        return _iso(row.reviewed_at) or ""
    if column.startswith("custom:"):
        return row.custom_fields.get(column[len("custom:") :], "")
    return row.fields.get(column, "")


def _display_name(column: str) -> str:
    if column in DETAIL_DISPLAY_NAMES:
        return DETAIL_DISPLAY_NAMES[column]
    if column.startswith("custom:"):
        return f"Custom: {column[len('custom:') :]}"
    return FIELD_DISPLAY_NAMES.get(column, column)


def _render_csv(
    rows: list[ExportRow],
    include_details: bool,
    *,
    bom: bool,
    openrefine: bool,
) -> bytes:
    columns, _ = _columns(rows, include_details, openrefine=openrefine)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_safe_cell(_value(row, column)) for column in columns])
    text = output.getvalue()
    return text.encode("utf-8-sig") if bom else text.encode("utf-8")


def _render_xlsx(rows: list[ExportRow], include_details: bool) -> bytes:
    columns, _ = _columns(rows, include_details)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Metadata"

    sheet.append([_display_name(column) for column in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E8EDF3")

    for row in rows:
        sheet.append([_safe_cell(_value(row, column)) for column in columns])

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{sheet.max_row}"
    for index, column in enumerate(columns, start=1):
        width = max(12, min(len(_display_name(column)) + 2, 40))
        sheet.column_dimensions[get_column_letter(index)].width = width

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _row_payload(row: ExportRow, include_details: bool) -> dict:
    payload: dict = {"book_id": str(row.book_id)}
    if include_details:
        payload["book"] = {
            "title": row.title,
            "language": row.language,
            "source_filename": Path(row.filename).name,
            "status": row.status,
            "total_pages": row.total_pages,
            "uploaded_at": _iso(row.uploaded_at),
            "reviewed_at": _iso(row.reviewed_at),
        }
    payload["metadata"] = dict(row.fields)
    if row.custom_fields:
        payload["custom_fields"] = dict(row.custom_fields)
    return payload


def _render_json(rows: list[ExportRow], include_details: bool) -> bytes:
    payload = [_row_payload(row, include_details) for row in rows]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def _render_jsonl(rows: list[ExportRow], include_details: bool) -> bytes:
    lines = [
        json.dumps(_row_payload(row, include_details), ensure_ascii=False, separators=(",", ":"))
        for row in rows
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def load_property_mapping() -> dict[str, str]:
    """Load the Wikibase property mapping (Wikidata P-ID → local P-ID)."""
    mapping_path = Path(settings.property_mapping_path)
    if mapping_path.exists():
        try:
            with open(mapping_path) as handle:
                mapping = json.load(handle)
            logger.info("Loaded property mapping from %s (%d entries)", mapping_path, len(mapping))
            return mapping
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load property mapping from %s: %s", mapping_path, exc)

    logger.info("No property mapping file found, using hardcoded Wikidata P-IDs")
    return {}


def _statement(prop: str, datavalue: dict) -> dict:
    return {
        "mainsnak": {
            "snaktype": "value",
            "property": prop,
            "datavalue": datavalue,
        },
        "type": "statement",
        "rank": "normal",
    }


def _string_datavalue(value: str) -> dict:
    return {"value": value, "type": "string"}


def _entity_datavalue(qid: str) -> dict:
    if not re.fullmatch(r"Q\d+", qid):
        return _string_datavalue(qid)
    return {
        "value": {
            "entity-type": "item",
            "numeric-id": int(qid[1:]),
            "id": qid,
        },
        "type": "wikibase-entityid",
    }


def _time_datavalue(value: str) -> dict | None:
    match = _YEAR_RE.match(value)
    if not match:
        return None

    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else 0
    day = int(match.group(3)) if match.group(3) else 0
    if month and not 1 <= month <= 12:
        return None
    if day and not 1 <= day <= 31:
        return None

    precision = 11 if day else 10 if month else 9
    return {
        "value": {
            "time": f"+{year:04d}-{month:02d}-{day:02d}T00:00:00Z",
            "timezone": 0,
            "before": 0,
            "after": 0,
            "precision": precision,
            "calendarmodel": WIKIBASE_GREGORIAN,
        },
        "type": "time",
    }


def _monolingual_datavalue(value: str, language: str) -> dict:
    return {"value": {"text": value, "language": language}, "type": "monolingualtext"}


def _quantity_datavalue(value: str) -> dict | None:
    match = _COUNT_RE.search(value)
    if not match:
        return None
    return {"value": {"amount": f"+{int(match.group(0))}", "unit": "1"}, "type": "quantity"}


def wikibase_property_id(field_name: str, value: str, wikidata_prop: str) -> str:
    """Return the Wikidata property for a value, accounting for ISBN length."""
    if field_name == "isbn" and _ISBN10_RE.match(_ISBN_SEPARATORS.sub("", value)):
        return "P957"
    return wikidata_prop


def wikibase_tsv_value(field_name: str, value: str, language: str) -> str | None:
    """Render a value for QuickStatements using the property's datatype."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    if field_name in WIKIBASE_TIME_FIELDS:
        time_value = _time_datavalue(value)
        if time_value is None:
            return None
        return f'{time_value["value"]["time"]}/{time_value["value"]["precision"]}'
    if field_name in WIKIBASE_MONOLINGUAL_FIELDS:
        return f'{LANGUAGE_TAGS.get(language, "en")}:"{escaped}"'
    if field_name in WIKIBASE_QUANTITY_FIELDS:
        quantity = _quantity_datavalue(value)
        if quantity is None:
            return None
        return quantity["value"]["amount"].lstrip("+")
    return f'"{escaped}"'


def _field_datavalue(field_name: str, value: str, language: str) -> dict:
    if field_name in WIKIBASE_TIME_FIELDS:
        time_value = _time_datavalue(value)
        if time_value is not None:
            return time_value
    if field_name in WIKIBASE_MONOLINGUAL_FIELDS:
        return _monolingual_datavalue(value, LANGUAGE_TAGS.get(language, "mul"))
    if field_name in WIKIBASE_QUANTITY_FIELDS:
        quantity = _quantity_datavalue(value)
        if quantity is not None:
            return quantity
    return _string_datavalue(value)


def _wikibase_item(row: ExportRow, property_mapping: dict[str, str]) -> dict:
    claims: dict[str, list[dict]] = {}

    for field_name, wikidata_prop in FIELD_WIKIDATA.items():
        if wikidata_prop is None:
            continue
        value = row.fields.get(field_name, "").strip()
        if not value:
            continue
        prop = wikibase_property_id(field_name, value, wikidata_prop)
        local_prop = property_mapping.get(prop, prop)
        claims.setdefault(local_prop, []).append(
            _statement(local_prop, _field_datavalue(field_name, value, row.language))
        )

    instance_of = property_mapping.get("P31", "P31")
    book_item = property_mapping.get("Q571", "Q571")
    claims.setdefault(instance_of, []).append(
        _statement(instance_of, _entity_datavalue(book_item))
    )

    language = row.fields.get("language") or row.language
    language_qid = LANGUAGE_QIDS.get(language)
    if language_qid:
        language_prop = property_mapping.get("P407", "P407")
        claims.setdefault(language_prop, []).append(
            _statement(language_prop, _entity_datavalue(property_mapping.get(language_qid, language_qid)))
        )

    label = row.fields.get("label") or row.title or Path(row.filename).name
    item: dict = {
        "type": "item",
        "labels": {"en": {"language": "en", "value": label}},
        "claims": claims,
    }

    description = row.fields.get("description_work") or row.fields.get("description_edition")
    if description:
        item["descriptions"] = {"en": {"language": "en", "value": description}}

    if row.custom_fields:
        item["custom_fields"] = dict(row.custom_fields)

    return item


def _render_wikibase(rows: list[ExportRow]) -> bytes:
    property_mapping = load_property_mapping()
    payload = [_wikibase_item(row, property_mapping) for row in rows]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def render(
    rows: list[ExportRow],
    fmt: ExportFormat,
    include_details: bool = False,
) -> tuple[bytes, str, str]:
    """Serialize rows and return ``(body, media_type, extension)``."""
    if fmt == "csv":
        body = _render_csv(rows, include_details, bom=True, openrefine=False)
    elif fmt == "openrefine":
        body = _render_csv(rows, include_details, bom=False, openrefine=True)
    elif fmt == "xlsx":
        body = _render_xlsx(rows, include_details)
    elif fmt == "json":
        body = _render_json(rows, include_details)
    elif fmt == "jsonl":
        body = _render_jsonl(rows, include_details)
    elif fmt == "wikibase":
        body = _render_wikibase(rows)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    return body, MEDIA_TYPES[fmt], EXTENSIONS[fmt]
