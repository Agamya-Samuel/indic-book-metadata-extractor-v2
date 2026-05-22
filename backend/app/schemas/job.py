from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: uuid.UUID
    book_id: uuid.UUID | None
    job_type: str
    status: str
    progress: float
    created_at: datetime.datetime | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    error_log: str | None

    model_config = {"from_attributes": True}
