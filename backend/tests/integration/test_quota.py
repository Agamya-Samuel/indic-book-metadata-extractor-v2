"""Per-user quotas stop one account flooding the queue or the library."""

from __future__ import annotations

import io
import uuid

from app.core.config import settings
from app.models.job import Job, JobStatus, JobType


class TestBookQuota:
    async def test_upload_rejected_past_the_book_limit(self, client, make_book, sample_pdf, monkeypatch):
        monkeypatch.setattr(settings, "max_books_per_user", 1)
        await make_book()

        response = await client.post(
            "/api/books/upload",
            files={
                "file": (
                    "second.pdf",
                    io.BytesIO(sample_pdf.read_bytes()),
                    "application/pdf",
                )
            },
            data={"language": "tel"},
        )
        assert response.status_code == 429
        assert "limit" in response.json()["detail"].lower()


class TestJobQuota:
    async def test_new_job_rejected_past_the_active_job_limit(
        self, client, make_book, db_session, regular_user, monkeypatch
    ):
        monkeypatch.setattr(settings, "max_active_jobs_per_user", 1)
        book = await make_book()
        db_session.add(
            Job(
                id=uuid.uuid4(),
                book_id=uuid.UUID(book["id"]),
                requested_by_id=regular_user.id,
                job_type=JobType.PREPROCESSING,
                status=JobStatus.QUEUED,
                progress=0,
            )
        )
        await db_session.commit()

        response = await client.post(
            f"/api/books/{book['id']}/pages",
            json={"selected_pages": [1]},
        )
        assert response.status_code == 429
        assert "active job" in response.json()["detail"].lower()
