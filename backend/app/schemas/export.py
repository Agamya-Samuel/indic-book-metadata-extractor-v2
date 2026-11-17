from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ExportFormat = Literal["csv", "xlsx", "json", "jsonl", "wikibase", "openrefine"]

MAX_BOOK_IDS = 1000


class ExportRequest(BaseModel):
    format: ExportFormat = "csv"
    include_details: bool = False
    book_ids: list[UUID] | None = Field(
        default=None,
        description="Explicit books to export. Omit to use the filters.",
    )
    language: str | None = None
    status: str | None = None
    owner_id: UUID | None = Field(
        default=None,
        description="Administrators only; ignored for regular users.",
    )

    @field_validator("book_ids")
    @classmethod
    def _validate_book_ids(cls, book_ids: list[UUID] | None) -> list[UUID] | None:
        if book_ids is None:
            return None
        if not book_ids:
            raise ValueError("book_ids cannot be empty")
        if len(book_ids) > MAX_BOOK_IDS:
            raise ValueError(f"At most {MAX_BOOK_IDS} books can be exported at once")
        return book_ids
