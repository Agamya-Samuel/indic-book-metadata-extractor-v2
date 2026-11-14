from __future__ import annotations

import uuid


from app.models.book import Book, BookStatus
from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page


async def _create_book_with_ocr(client, make_book, db_session):
    book = await make_book()
    book_id = uuid.UUID(book["id"])

    # Page rendering is asynchronous in production; seed the page rows and OCR
    # results directly so extraction tests stay deterministic.
    pages = [
        Page(
            book_id=book_id,
            page_number=page_number,
            image_path=f"pages/{book_id}/{page_number}.png",
            preprocessing_config={},
        )
        for page_number in (1, 2)
    ]
    db_session.add_all(pages)

    # Drive the stages the way the pipeline does, so book.status is derived
    # from stage state rather than assigned directly.
    from app.services.stage_manager import StageManager

    await db_session.flush()

    await StageManager.initiate_stage(db_session, book_id, "page_selection")
    await StageManager.start_stage(db_session, book_id, "page_selection")
    await StageManager.complete_stage(db_session, book_id, "page_selection")

    for page in pages:
        ocr = OcrResult(
            page_id=page.id,
            raw_text="Sample OCR text for extraction",
            confidence=85.0,
            language_detected="tel",
        )
        db_session.add(ocr)

    await StageManager.initiate_stage(db_session, book_id, "ocr")
    await StageManager.start_stage(db_session, book_id, "ocr")
    await StageManager.complete_stage(db_session, book_id, "ocr")
    await db_session.commit()

    return book


class TestListModels:
    async def test_list_models(self, client):
        # Regression: /books/models must not be shadowed by /books/{book_id}
        # (which would 422 on UUID validation).
        response = await client.get("/api/books/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["items"], list)
        assert data["total"] == len(data["items"])


class TestRunExtraction:
    async def test_run_extraction_dispatch(self, client, make_book, db_session, mock_celery):
        book = await _create_book_with_ocr(client, make_book, db_session)

        response = await client.post(
            f"/api/books/{book['id']}/run-extraction",
            json={"model": "qwen2.5", "temperature": 0.3, "max_tokens": 2048},
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
            json={"model": "qwen2.5"},
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
            json={"model": "qwen2.5"},
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
            json={"model": "qwen2.5"},
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
            json={"model": "qwen2.5"},
        )
        assert response.status_code == 201


async def _drive_to_awaiting_review(db_session, book_id: uuid.UUID) -> None:
    from app.services.stage_manager import StageManager

    await StageManager.initiate_stage(db_session, book_id, "llm_extraction")
    await StageManager.start_stage(db_session, book_id, "llm_extraction")
    await StageManager.complete_stage(db_session, book_id, "llm_extraction")
    await db_session.commit()


class TestRerunFromAwaitingReview:
    async def test_run_extraction_accepted_from_awaiting_review(
        self, client, make_book, db_session, mock_celery
    ):
        book = await _create_book_with_ocr(client, make_book, db_session)
        book_id = uuid.UUID(book["id"])
        await _drive_to_awaiting_review(db_session, book_id)

        detail = await client.get(f"/api/books/{book['id']}")
        assert detail.json()["status"] == "awaiting_review"

        response = await client.post(
            f"/api/books/{book['id']}/run-extraction",
            json={"model": "qwen2.5"},
        )
        assert response.status_code == 201

    async def test_rerun_extraction_accepted_from_awaiting_review(
        self, client, make_book, db_session, mock_celery
    ):
        book = await _create_book_with_ocr(client, make_book, db_session)
        book_id = uuid.UUID(book["id"])
        await _drive_to_awaiting_review(db_session, book_id)

        response = await client.post(
            f"/api/books/{book['id']}/rerun-extraction"
        )
        assert response.status_code == 201

    async def test_rerun_releases_downstream_stages(
        self, client, make_book, db_session, mock_celery
    ):
        from sqlalchemy import select

        from app.models.stage import BookStageStatus, StageStatus

        book = await _create_book_with_ocr(client, make_book, db_session)
        book_id = uuid.UUID(book["id"])
        await _drive_to_awaiting_review(db_session, book_id)

        response = await client.post(
            f"/api/books/{book['id']}/rerun-extraction"
        )
        assert response.status_code == 201

        rows = (
            await db_session.execute(
                select(BookStageStatus).where(
                    BookStageStatus.book_id == book_id,
                    BookStageStatus.stage_name == "llm_extraction",
                )
            )
        ).scalars().all()
        attempts = sorted(row.attempt for row in rows)
        assert len(attempts) == 2, "a re-run must open a new attempt"
        latest = max(rows, key=lambda row: row.attempt)
        assert latest.status == StageStatus.PROCESSING
        assert any(row.status == StageStatus.CANCELLED for row in rows)
