"""Unit tests for the StageManager state machine.

These cover the transitions, the derived Book.status cache, sequential
validation, and the legacy-book path. There was no coverage here before,
which is how a broken state machine shipped to production.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.book import Book, BookStatus
from app.models.stage import StageStatus
from app.services.stage_manager import StageManager, StageTransitionError

UPLOAD = "upload"
PAGE_SELECTION = "page_selection"
OCR = "ocr"
LLM = "llm_extraction"
HUMAN_REVIEW = "human_review"
COMPLETION = "completion"

FULL_ORDER = [UPLOAD, PAGE_SELECTION, OCR, LLM, HUMAN_REVIEW, COMPLETION]


async def _make_book(db_session, status: BookStatus = BookStatus.UPLOADED) -> uuid.UUID:
    book = Book(
        id=uuid.uuid4(),
        title="Test",
        filename="test.pdf",
        language="tel",
        total_pages=3,
        status=status,
    )
    db_session.add(book)
    await db_session.commit()
    return book.id


async def _advance(db_session, book_id, stage: str) -> None:
    await StageManager.initiate_stage(db_session, book_id, stage)
    await StageManager.start_stage(db_session, book_id, stage)
    await StageManager.complete_stage(db_session, book_id, stage)
    await db_session.commit()


async def _status(db_session, book_id) -> str:
    book = await db_session.get(Book, book_id)
    await db_session.refresh(book)
    return str(book.status)


class TestHappyPath:
    async def test_progression_updates_derived_book_status(self, db_session):
        book_id = await _make_book(db_session)

        await _advance(db_session, book_id, UPLOAD)
        assert await _status(db_session, book_id) == BookStatus.UPLOADED

        await _advance(db_session, book_id, PAGE_SELECTION)
        assert await _status(db_session, book_id) == BookStatus.PAGES_SELECTED

        await StageManager.initiate_stage(db_session, book_id, OCR)
        await StageManager.start_stage(db_session, book_id, OCR)
        await db_session.commit()
        assert await _status(db_session, book_id) == BookStatus.OCR_RUNNING

        await StageManager.complete_stage(db_session, book_id, OCR)
        await db_session.commit()
        assert await _status(db_session, book_id) == BookStatus.OCR_COMPLETE

        await StageManager.initiate_stage(db_session, book_id, LLM)
        await StageManager.start_stage(db_session, book_id, LLM)
        await db_session.commit()
        assert await _status(db_session, book_id) == BookStatus.LLM_RUNNING

        await StageManager.complete_stage(db_session, book_id, LLM)
        await db_session.commit()
        assert await _status(db_session, book_id) == BookStatus.AWAITING_REVIEW

        await _advance(db_session, book_id, HUMAN_REVIEW)
        await _advance(db_session, book_id, COMPLETION)
        assert await _status(db_session, book_id) == BookStatus.COMPLETE

    async def test_each_stage_records_attempt_one(self, db_session):
        book_id = await _make_book(db_session)
        await _advance(db_session, book_id, UPLOAD)
        row = await StageManager.get_stage(db_session, book_id, UPLOAD)
        assert row is not None
        assert row.attempt == 1
        assert row.status == StageStatus.COMPLETED
        assert row.started_at is not None
        assert row.completed_at is not None


class TestTransitionGuards:
    async def test_complete_rejected_from_initiated(self, db_session):
        book_id = await _make_book(db_session)
        await StageManager.initiate_stage(db_session, book_id, UPLOAD)
        with pytest.raises(StageTransitionError):
            await StageManager.complete_stage(db_session, book_id, UPLOAD)

    async def test_start_rejected_when_already_processing(self, db_session):
        book_id = await _make_book(db_session)
        await StageManager.initiate_stage(db_session, book_id, UPLOAD)
        await StageManager.start_stage(db_session, book_id, UPLOAD)
        with pytest.raises(StageTransitionError):
            await StageManager.start_stage(db_session, book_id, UPLOAD)

    async def test_complete_rejected_for_unknown_stage(self, db_session):
        book_id = await _make_book(db_session)
        with pytest.raises(StageTransitionError):
            await StageManager.complete_stage(db_session, book_id, UPLOAD)

    async def test_cancel_allowed_from_initiated(self, db_session):
        book_id = await _make_book(db_session)
        await StageManager.initiate_stage(db_session, book_id, UPLOAD)
        row = await StageManager.cancel_stage(db_session, book_id, UPLOAD, "superseded")
        assert row.status == StageStatus.CANCELLED


class TestSequentialValidation:
    async def test_skipping_a_stage_is_rejected(self, db_session):
        book_id = await _make_book(db_session)
        await _advance(db_session, book_id, UPLOAD)
        with pytest.raises(StageTransitionError):
            await StageManager.initiate_stage(db_session, book_id, OCR)

    async def test_legacy_book_without_stage_rows_is_allowed(self, db_session):
        # Books that predate stage tracking have no rows; they must not be
        # locked out of the pipeline.
        book_id = await _make_book(db_session, status=BookStatus.OCR_COMPLETE)
        row = await StageManager.initiate_stage(db_session, book_id, LLM)
        assert row.stage_name == LLM

    async def test_retry_increments_attempt(self, db_session):
        book_id = await _make_book(db_session)
        await _advance(db_session, book_id, UPLOAD)
        await _advance(db_session, book_id, UPLOAD)
        row = await StageManager.get_stage(db_session, book_id, UPLOAD)
        assert row.attempt == 2
