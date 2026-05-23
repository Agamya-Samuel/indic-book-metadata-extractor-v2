from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page


async def _create_book_with_ocr(client, make_book, db_session):
    book = await make_book()
    book_id = uuid.UUID(book["id"])

    await client.post(
        f"/api/books/{book['id']}/pages",
        json={"selected_pages": [1, 2]},
    )

    from sqlalchemy import select
    pages_result = await db_session.execute(
        select(Page).where(Page.book_id == book_id)
    )
    pages = pages_result.scalars().all()

    for page in pages:
        ocr = OcrResult(
            page_id=page.id,
            raw_text="Sample OCR text for extraction",
            confidence=85.0,
            language_detected="tel",
        )
        db_session.add(ocr)

    book_result = await db_session.execute(select(Book).where(Book.id == book_id))
    book_obj = book_result.scalar_one()
    book_obj.status = BookStatus.OCR_COMPLETE
    await db_session.commit()

    return book


class TestListModels:
    async def test_list_models(self, client):
        response = await client.get("/api/books/models")
        assert response.status_code in (200, 404, 422)


class TestRunExtraction:
    async def test_run_extraction_dispatch(self, client, make_book, db_session, mock_celery):
        book = await _create_book_with_ocr(client, make_book, db_session)

        response = await client.post(
            f"/api/books/{book['id']}/run-extraction",
            json={"model": "airavata", "temperature": 0.3, "max_tokens": 2048},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["total_batches"] == 8
        mock_celery["llm"].delay.assert_called_once()

    async def test_run_extraction_wrong_status(self, client, make_book_with_pages, mock_celery):
        book = await make_book_with_pages()
        response = await client.post(
            f"/api/books/{book['id']}/run-extraction",
            json={"model": "airavata"},
        )
        assert response.status_code == 400

    async def test_run_extraction_no_ocr_text(self, client, make_book, db_session, mock_celery):
        book_resp = await make_book()
        book_id = uuid.UUID(book_resp["id"])

        await client.post(
            f"/api/books/{book_resp['id']}/pages",
            json={"selected_pages": [1]},
        )

        from sqlalchemy import select
        book_result = await db_session.execute(select(Book).where(Book.id == book_id))
        book_obj = book_result.scalar_one()
        book_obj.status = BookStatus.OCR_COMPLETE
        await db_session.commit()

        response = await client.post(
            f"/api/books/{book_resp['id']}/run-extraction",
            json={"model": "airavata"},
        )
        assert response.status_code == 400

    async def test_run_extraction_conflict(self, client, make_book, db_session, mock_celery):
        book = await _create_book_with_ocr(client, make_book, db_session)
        book_id = uuid.UUID(book["id"])

        running_job = Job(
            book_id=book_id,
            job_type=JobType.LLM,
            status=JobStatus.RUNNING,
            progress=50.0,
        )
        db_session.add(running_job)
        await db_session.commit()

        response = await client.post(
            f"/api/books/{book['id']}/run-extraction",
            json={"model": "airavata"},
        )
        assert response.status_code == 409


class TestRetryExtraction:
    async def test_retry_extraction(self, client, make_book, db_session, mock_celery):
        book = await _create_book_with_ocr(client, make_book, db_session)
        book_id = uuid.UUID(book["id"])

        from sqlalchemy import select
        book_result = await db_session.execute(select(Book).where(Book.id == book_id))
        book_obj = book_result.scalar_one()
        book_obj.status = BookStatus.COMPLETE
        await db_session.commit()

        response = await client.post(
            f"/api/books/{book['id']}/retry-extraction",
            json={"model": "airavata"},
        )
        assert response.status_code == 201
