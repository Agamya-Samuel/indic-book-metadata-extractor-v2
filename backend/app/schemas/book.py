from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field

from app.schemas.common import Page


class BookUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    title: str | None
    language: str
    total_pages: int | None
    status: str
    created_at: datetime.datetime | None
    owner_id: uuid.UUID | None = None
    owner_display_name: str | None = None

    model_config = {"from_attributes": True}


class BookDetail(BookUploadResponse):
    updated_at: datetime.datetime | None = None
    needs_review: bool = False
    low_confidence_count: int = 0
    owner_email: str | None = None


class PageSelectionRequest(BaseModel):
    selected_pages: list[int] = Field(..., min_length=1)


class PageSelectionResponse(BaseModel):
    book_id: uuid.UUID
    selected_count: int
    status: str
    job_id: uuid.UUID | None = None


class PageResponse(BaseModel):
    id: uuid.UUID
    page_number: int
    image_path: str | None
    preprocessing_config: dict | None
    has_processed_image: bool = False
    ocr_error: str | None = None
    image_url: str | None = None
    ocr_text: str | None = None
    ocr_confidence: float | None = None

    model_config = {"from_attributes": True}


class OcrPageStatus(BaseModel):
    page_number: int
    page_id: uuid.UUID
    has_ocr: bool
    confidence: float | None


class OcrStatusResponse(BaseModel):
    total_pages: int
    ocr_complete_count: int
    ocr_pending_count: int
    avg_confidence: float | None
    pages: list[OcrPageStatus]


class BookSearchResult(BaseModel):
    id: uuid.UUID
    title: str | None
    filename: str
    language: str
    status: str
    total_pages: int | None
    created_at: datetime.datetime | None
    metadata_fields: dict | None = None
    thumbnail_url: str | None = None
    owner_id: uuid.UUID | None = None
    owner_display_name: str | None = None
    owner_email: str | None = None


class BookListResponse(Page[BookSearchResult]):
    pass


class BookDetailResponse(BaseModel):
    book: BookDetail
    metadata: dict | None = None
    metadata_updated_at: datetime.datetime | None = None
    owner_display_name: str | None = None


class FilterOptionsResponse(BaseModel):
    languages: list[str]
    statuses: list[str]
    genres: list[str]
    publishers: list[str]
