"""Unit tests for the pipeline orchestrator (process_book_pipeline).

These tests exercise the orchestrator's idempotency and event publishing
without touching the real database, Redis, or Celery workers. Stage helpers
are monkeypatched with synchronous fakes; the actual Celery dispatch is
stubbed out via ``mock_celery``.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.models.book import Book, BookStatus
from app.services.sse_service import channel_for


@pytest.fixture
def test_session_factory(monkeypatch):
    """Point the production ``async_session_factory`` at the test SQLite
    engine so the orchestrator's DB helpers work in tests. Patch both the
    canonical name on the database module and the references imported by
    the tasks modules (which capture the value at import time)."""
    from app.core import database
    from app.tasks import pipeline_tasks
    from tests.conftest import TestSessionFactory

    monkeypatch.setattr(database, "async_session_factory", TestSessionFactory)
    monkeypatch.setattr(pipeline_tasks, "async_session_factory", TestSessionFactory)
    yield TestSessionFactory


async def _seed_book(db_session, status: BookStatus, total_pages: int = 2) -> Book:
    book = Book(
        id=uuid.uuid4(),
        title="t",
        filename="t.pdf",
        language="tel",
        total_pages=total_pages,
        status=status,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    return book


async def test_orchestrator_dispatches_subtasks_on_fresh_upload(
    db_session, mock_celery, test_session_factory
):
    book = await _seed_book(db_session, BookStatus.UPLOADED, total_pages=3)
    book_id = book.id

    async def _advance(target: BookStatus):
        from sqlalchemy import select

        from app.models.book import Book as BookModel

        async with test_session_factory() as db:
            result = await db.execute(select(BookModel).where(BookModel.id == book_id))
            b = result.scalar_one()
            b.status = target
            await db.commit()
        return None

    async def _pages_stage(_bid):
        await _advance(BookStatus.PAGES_SELECTED)

    async def _ocr_stage(_bid, _lang):
        await _advance(BookStatus.OCR_COMPLETE)

    async def _llm_stage(_bid):
        await _advance(BookStatus.AWAITING_REVIEW)

    with (
        patch("app.tasks.pipeline_tasks._stage_pages_selected_async", side_effect=_pages_stage),
        patch("app.tasks.pipeline_tasks._stage_ocr_async", side_effect=_ocr_stage),
        patch("app.tasks.pipeline_tasks._stage_llm_async", side_effect=_llm_stage),
        patch("app.tasks.pipeline_tasks.publish_sync") as mock_publish,
    ):
        from app.tasks import pipeline_tasks

        await pipeline_tasks._process_book_pipeline_async(str(book_id), "tel")

        published_types = {c.args[1].get("type") for c in mock_publish.call_args_list}
        assert "pipeline.started" in published_types
        assert "pipeline.completed" in published_types


async def test_orchestrator_resumes_from_ocr_complete(
    db_session, mock_celery, test_session_factory
):
    book = await _seed_book(db_session, BookStatus.OCR_COMPLETE, total_pages=3)
    book_id = book.id

    async def _advance_to_awaiting():
        from sqlalchemy import select

        from app.models.book import Book as BookModel

        async with test_session_factory() as db:
            result = await db.execute(select(BookModel).where(BookModel.id == book_id))
            b = result.scalar_one()
            b.status = BookStatus.AWAITING_REVIEW
            await db.commit()

    async def _llm_stage(_bid):
        await _advance_to_awaiting()

    with (
        patch("app.tasks.pipeline_tasks._stage_pages_selected_async") as mock_stage_pages,
        patch("app.tasks.pipeline_tasks._stage_ocr_async") as mock_stage_ocr,
        patch("app.tasks.pipeline_tasks._stage_llm_async", side_effect=_llm_stage),
        patch("app.tasks.pipeline_tasks.publish_sync"),
    ):
        from app.tasks import pipeline_tasks

        await pipeline_tasks._process_book_pipeline_async(str(book_id), "tel")

        mock_stage_pages.assert_not_called()
        mock_stage_ocr.assert_not_called()


async def test_orchestrator_skips_llm_when_already_complete(
    db_session, mock_celery, test_session_factory
):
    book = await _seed_book(db_session, BookStatus.AWAITING_REVIEW, total_pages=3)
    book_id = book.id

    with (
        patch("app.tasks.pipeline_tasks._stage_pages_selected_async") as mock_stage_pages,
        patch("app.tasks.pipeline_tasks._stage_ocr_async") as mock_stage_ocr,
        patch("app.tasks.pipeline_tasks._stage_llm_async") as mock_stage_llm,
        patch("app.tasks.pipeline_tasks.publish_sync") as mock_publish,
    ):
        from app.tasks import pipeline_tasks

        await pipeline_tasks._process_book_pipeline_async(str(book_id), "tel")

        mock_stage_pages.assert_not_called()
        mock_stage_ocr.assert_not_called()
        mock_stage_llm.assert_not_called()
        # The orchestrator should still emit pipeline.completed because the
        # book is already past every stage.
        published_types = {c.args[1].get("type") for c in mock_publish.call_args_list}
        assert "pipeline.completed" in published_types


def test_sse_channel_format_roundtrip():
    book_id = uuid.uuid4()
    channel = channel_for(book_id)
    from app.services.sse_service import book_id_from_channel

    assert book_id_from_channel(channel) == str(book_id)
    assert book_id_from_channel("not-a-book-channel") is None


def test_sse_publish_sync_writes_to_expected_channel(monkeypatch):
    from app.services import sse_service

    captured: list[tuple[str, str]] = []

    class FakeRedis:
        def publish(self, channel, message):
            captured.append((channel, message))
            return 1

        def close(self):
            pass

    monkeypatch.setattr(sse_service, "_sync_redis", lambda: FakeRedis())

    book_id = uuid.uuid4()
    sse_service.publish_sync(
        book_id,
        {"type": "job.progress", "progress": 42.5},
    )

    assert len(captured) == 1
    channel, message = captured[0]
    assert channel == f"book:{book_id}:events"
    assert '"progress": 42.5' in message
    assert '"type": "job.progress"' in message
