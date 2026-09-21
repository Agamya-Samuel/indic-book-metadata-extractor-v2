from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class BookStage(StrEnum):
    UPLOAD = "upload"
    PAGE_SELECTION = "page_selection"
    OCR = "ocr"
    LLM_EXTRACTION = "llm_extraction"
    HUMAN_REVIEW = "human_review"
    COMPLETION = "completion"


class StageStatus(StrEnum):
    INITIATED = "initiated"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatusResponse(BaseModel):
    id: UUID
    book_id: UUID
    stage_name: str
    attempt: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_log: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
