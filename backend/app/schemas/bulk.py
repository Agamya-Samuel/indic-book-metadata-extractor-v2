from __future__ import annotations

from pydantic import BaseModel, Field


class BulkExportRequest(BaseModel):
    language: str | None = Field(
        default=None, description="Filter by language (e.g. 'tel', 'hin')"
    )
    status: str | None = Field(
        default=None, description="Filter by book status (e.g. 'complete')"
    )
    format: str = Field(
        default="csv",
        description="Export format: 'csv' for download, 'openrefine' to create an OpenRefine project",
    )


class BulkImportRequest(BaseModel):
    mode: str = Field(
        default="merge",
        description="Import mode: 'merge' updates only provided fields, 'overwrite' replaces all fields",
    )


class BulkImportResult(BaseModel):
    total_rows: int
    books_updated: int
    books_not_found: int
    fields_changed: int
    errors: list[str] = Field(default_factory=list)


class BulkStatsResponse(BaseModel):
    total_books: int
    books_with_metadata: int
    languages: dict[str, int]
    statuses: dict[str, int]


class WikibaseExportRequest(BaseModel):
    language: str | None = Field(
        default=None, description="Filter by language"
    )
