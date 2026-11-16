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
    last_progress_at: datetime.datetime | None = None
    error_log: str | None = None
    celery_task_id: str | None = None
    # Seconds from start (or queue entry) to completion (or now).
    duration_seconds: int | None = None
    # Queue position within the job's family: 0 running, N queued ahead,
    # None when the job is terminal.
    queue_ahead: int | None = None
    stage_name: str | None = None
    stage_status: str | None = None


class AdminJobsResponse(Page[AdminJobRow]):
    pass


class UserJobCounts(BaseModel):
    user_id: uuid.UUID | None = None
    display_name: str | None = None
    email: str | None = None
    total: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


class JobSummaryResponse(BaseModel):
    total: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    by_type: dict[str, int] = {}
    by_user: list[UserJobCounts] = []


class BulkCancelRequest(BaseModel):
    job_ids: list[uuid.UUID]


class BulkCancelItem(BaseModel):
    id: uuid.UUID
    status: str | None = None
    ok: bool
    error: str | None = None


class BulkCancelResponse(BaseModel):
    results: list[BulkCancelItem]
