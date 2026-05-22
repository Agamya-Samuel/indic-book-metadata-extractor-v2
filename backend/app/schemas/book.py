from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, Field


class BookUploadResponse(BaseModel):
    id: uuid.UUID
    filename: str
    title: str | None
    language: str
    total_pages: int | None
    status: str
    created_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class BookDetail(BookUploadResponse):
    updated_at: datetime.datetime | None = None


class PageSelectionRequest(BaseModel):
    selected_pages: list[int] = Field(..., min_length=1)


class PageSelectionResponse(BaseModel):
    book_id: uuid.UUID
    selected_count: int
    status: str


class PageResponse(BaseModel):
    id: uuid.UUID
    page_number: int
    image_path: str | None
    preprocessing_config: dict | None

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
