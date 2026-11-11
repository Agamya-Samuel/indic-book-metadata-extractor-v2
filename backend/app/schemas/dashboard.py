"""Schemas for the per-user dashboard and job queue views."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel


class DashboardJobRow(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None = None
    book_title: str | None = None
    book_filename: str | None = None
    job_type: str
    status: str
    progress: float
    queue_ahead: int | None = None
    created_at: datetime.datetime | None = None
    started_at: datetime.datetime | None = None
    completed_at: datetime.datetime | None = None
    error_log: str | None = None


class DashboardJobsResponse(BaseModel):
    items: list[DashboardJobRow]
    total: int
    page: int
    page_size: int
    total_pages: int


class DashboardSummary(BaseModel):
    books: dict
    jobs: dict
    queue: dict
