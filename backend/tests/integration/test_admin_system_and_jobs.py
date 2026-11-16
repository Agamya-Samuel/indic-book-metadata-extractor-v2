"""Admin system + global queue-management endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.services import system_metrics_service as svc


async def _seed_job(
    db_session,
    owner,
    *,
    status: str = JobStatus.QUEUED,
    job_type: str = JobType.OCR,
) -> tuple[Book, Job]:
    book = Book(
        id=uuid.uuid4(),
        title="Queue Book",
        filename="queue.pdf",
        language="tel",
        total_pages=2,
        owner_id=owner.id,
        status=BookStatus.PAGES_SELECTED,
    )
    db_session.add(book)
    await db_session.commit()

    job = Job(
        id=uuid.uuid4(),
        book_id=book.id,
        requested_by_id=owner.id,
        job_type=job_type,
        status=status,
        progress=0.0,
    )
    db_session.add(job)
    await db_session.commit()
    return book, job


@pytest.fixture(autouse=True)
def _reset_metrics_cache():
    svc.reset_cache()
    yield
    svc.reset_cache()


class TestAdminSystemEndpoint:
    async def test_requires_admin(self, client):
        response = await client.get("/api/admin/system")
        assert response.status_code == 403

    async def test_returns_server_service_and_queue_metrics(self, admin_client, db_session):
        celery = AsyncMock(return_value={"name": "Celery workers", "status": "ok", "detail": "1 worker"})
        ollama = AsyncMock(return_value={"name": "LLM (Ollama)", "status": "ok"})
        with patch.object(svc, "_check_celery", celery), patch.object(svc, "_check_ollama", ollama):
            response = await admin_client.get("/api/admin/system")

        assert response.status_code == 200
        data = response.json()
        assert set(data) >= {"generated_at", "overall_status", "server", "services", "queues"}
        names = {service["name"] for service in data["services"]}
        assert {"PostgreSQL", "Redis", "Celery workers"} <= names
        assert "queues" in data["queues"]
        assert "by_status" in data["queues"]


class TestAdminJobSummaryEndpoint:
    async def test_requires_admin(self, client):
        response = await client.get("/api/admin/jobs/summary")
        assert response.status_code == 403

    async def test_returns_per_user_breakdown(self, admin_client, db_session, admin_user):
        await _seed_job(db_session, admin_user, status=JobStatus.QUEUED)
        await _seed_job(db_session, admin_user, status=JobStatus.RUNNING)
        await _seed_job(db_session, admin_user, status=JobStatus.COMPLETED, job_type=JobType.LLM)

        response = await admin_client.get("/api/admin/jobs/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["queued"] == 1
        assert data["running"] == 1
        assert data["completed"] == 1
        assert data["by_type"].get("ocr") == 2
        assert data["by_user"][0]["total"] == 3


class TestAdminJobsListEnrichment:
    async def test_returns_queue_duration_and_stage_fields(self, admin_client, db_session, admin_user):
        await _seed_job(db_session, admin_user, status=JobStatus.QUEUED)

        response = await admin_client.get("/api/admin/jobs?sort=created_at&order=desc")

        assert response.status_code == 200
        item = response.json()["items"][0]
        for field in ("queue_ahead", "duration_seconds", "stage_name", "stage_status", "celery_task_id"):
            assert field in item


class TestAdminBulkCancel:
    async def test_mixed_batch_reports_each_outcome(self, admin_client, db_session, admin_user):
        _, queued = await _seed_job(db_session, admin_user, status=JobStatus.QUEUED)
        _, completed = await _seed_job(db_session, admin_user, status=JobStatus.COMPLETED)

        response = await admin_client.post(
            "/api/admin/jobs/cancel",
            json={"job_ids": [str(queued.id), str(completed.id), str(uuid.uuid4())]},
        )

        assert response.status_code == 200
        results = {row["id"]: row for row in response.json()["results"]}
        assert results[str(queued.id)]["ok"] is True
        assert results[str(queued.id)]["status"] == JobStatus.CANCELLED
        assert results[str(completed.id)]["ok"] is False
        assert "already" in results[str(completed.id)]["error"]

    async def test_single_cancel_terminal_is_409(self, admin_client, db_session, admin_user):
        _, completed = await _seed_job(db_session, admin_user, status=JobStatus.COMPLETED)

        response = await admin_client.post(f"/api/admin/jobs/{completed.id}/cancel")

        assert response.status_code == 409


class TestAdminRetry:
    async def test_retries_failed_job(self, admin_client, db_session, admin_user):
        book, failed = await _seed_job(db_session, admin_user, status=JobStatus.FAILED)
        replacement = Job(
            id=uuid.uuid4(),
            book_id=book.id,
            job_type=JobType.OCR,
            status=JobStatus.QUEUED,
            progress=0.0,
        )

        with patch("app.services.admin_service.rerun_ocr", AsyncMock(return_value=replacement)):
            response = await admin_client.post(f"/api/admin/jobs/{failed.id}/retry")

        assert response.status_code == 201
        data = response.json()
        assert data["job_id"] == str(replacement.id)
        assert data["status"] == JobStatus.QUEUED

    async def test_refuses_terminal_success(self, admin_client, db_session, admin_user):
        _, completed = await _seed_job(db_session, admin_user, status=JobStatus.COMPLETED)

        response = await admin_client.post(f"/api/admin/jobs/{completed.id}/retry")

        assert response.status_code == 400
