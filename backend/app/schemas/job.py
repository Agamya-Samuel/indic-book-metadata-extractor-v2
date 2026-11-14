from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel

from app.schemas.common import Page


class JobResponse(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None
    requested_by_id: uuid.UUID | None = None
    job_type: str
    status: str
    progress: float
    created_at: datetime.datetime | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    error_log: str | None

    model_config = {"from_attributes": True}


class AdminJobRow(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None = None
    requested_by_id: uuid.UUID | None = None
    book_title: str | None = None
    book_filename: str | None = None
    owner_display_name: str | None = None
    owner_email: str | None = None
    job_type: str
    status: str
    progress: float
    created_at: datetime.datetime | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    error_log: str | None = None


class AdminJobsResponse(Page[AdminJobRow]):
    pass
