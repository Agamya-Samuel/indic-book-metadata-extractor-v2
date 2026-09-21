import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.models.base import uuid
from app.models.book import Book, BookStatus
from app.models.stage import (
    BookStage,
    BookStageStatus,
    StageStatus,
    STAGE_ORDER,
    get_stage,
)

logger = logging.getLogger(__name__)

BOOK_STATUS_MAP = {
    (BookStage.UPLOAD, StageStatus.INITIATED): BookStatus.UPLOADED,
    (BookStage.UPLOAD, StageStatus.PROCESSING): BookStatus.UPLOADED,
    (BookStage.PAGE_SELECTION, StageStatus.INITIATED): BookStatus.PAGES_SELECTED,
    (BookStage.PAGE_SELECTION, StageStatus.PROCESSING): BookStatus.PAGES_SELECTED,
    (BookStage.OCR, StageStatus.INITIATED): BookStatus.OCR_RUNNING,
    (BookStage.OCR, StageStatus.PROCESSING): BookStatus.OCR_RUNNING,
    (BookStage.OCR, StageStatus.COMPLETED): BookStatus.OCR_COMPLETE,
    (BookStage.LLM_EXTRACTION, StageStatus.INITIATED): BookStatus.LLM_RUNNING,
    (BookStage.LLM_EXTRACTION, StageStatus.PROCESSING): BookStatus.LLM_RUNNING,
    (BookStage.LLM_EXTRACTION, StageStatus.COMPLETED): BookStatus.AWAITING_REVIEW,
    (BookStage.HUMAN_REVIEW, StageStatus.INITIATED): BookStatus.AWAITING_REVIEW,
    (BookStage.HUMAN_REVIEW, StageStatus.PROCESSING): BookStatus.AWAITING_REVIEW,
    (BookStage.COMPLETION, StageStatus.COMPLETED): BookStatus.COMPLETE,
}

TERMINAL_STATUSES = {StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED}


class StageTransitionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class StageManager:
    @staticmethod
    async def _lock_book(db, book_id: UUID) -> Book | None:
        result = await db.execute(
            select(Book).where(Book.id == book_id).with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _lock_stage(db, book_id: UUID, stage_name: str, attempt: int) -> BookStageStatus | None:
        result = await db.execute(
            select(BookStageStatus)
            .where(
                BookStageStatus.book_id == book_id,
                BookStageStatus.stage_name == stage_name,
                BookStageStatus.attempt == attempt,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_current_stages(db, book_id: UUID) -> list[BookStageStatus]:
        latest = (
            select(BookStageStatus.stage_name, func.max(BookStageStatus.attempt).label("max_attempt"))
            .where(BookStageStatus.book_id == book_id)
            .group_by(BookStageStatus.stage_name)
            .subquery()
        )
        result = await db.execute(
            select(BookStageStatus)
            .join(latest, (BookStageStatus.stage_name == latest.c.stage_name) & (BookStageStatus.attempt == latest.c.max_attempt))
            .where(BookStageStatus.book_id == book_id)
            .order_by(BookStageStatus.stage_name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_stage(db, book_id: UUID, stage_name: str, attempt: int | None = None) -> BookStageStatus | None:
        q = select(BookStageStatus).where(
            BookStageStatus.book_id == book_id,
            BookStageStatus.stage_name == stage_name,
        )
        if attempt is not None:
            q = q.where(BookStageStatus.attempt == attempt)
        else:
            max_attempt_sub = (
                select(func.max(BookStageStatus.attempt))
                .where(BookStageStatus.book_id == book_id, BookStageStatus.stage_name == stage_name)
                .scalar_subquery()
            )
            q = q.where(BookStageStatus.attempt == max_attempt_sub)
        result = await db.execute(q)
        return result.scalar_one_or_none()

    @staticmethod
    async def _derive_book_status(db, book_id: UUID) -> BookStatus | None:
        stages = await StageManager.get_current_stages(db, book_id)
        if not stages:
            return BookStatus.UPLOADED

        stage_map = {s.stage_name: s for s in stages}
        has_failed_or_cancelled = any(s.status in (StageStatus.FAILED, StageStatus.CANCELLED) for s in stages)

        if has_failed_or_cancelled:
            for stage in STAGE_ORDER:
                s = stage_map.get(stage)
                if s and s.status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.CANCELLED):
                    derived = BOOK_STATUS_MAP.get((stage, s.status))
                    if derived:
                        return derived
            return BookStatus.UPLOADED

        for stage in STAGE_ORDER:
            s = stage_map.get(stage)
            if s:
                derived = BOOK_STATUS_MAP.get((stage, s.status))
                if derived:
                    return derived
        return BookStatus.UPLOADED

    @staticmethod
    async def _update_book_status(db, book_id: UUID) -> None:
        book = await StageManager._lock_book(db, book_id)
        if book is None:
            raise StageTransitionError(f"Book {book_id} not found")
        derived = await StageManager._derive_book_status(db, book_id)
        if derived != book.status:
            book.status = derived
            await db.flush()

    @staticmethod
    async def _validate_sequential(db, book_id: UUID, stage_name: str) -> None:
        stage_idx = STAGE_ORDER.index(stage_name)
        if stage_idx == 0:
            return
        prior_stage = STAGE_ORDER[stage_idx - 1]
        prior = await get_stage(db, book_id, prior_stage)
        if prior is None or prior.status not in TERMINAL_STATUSES:
            raise StageTransitionError(
                f"Cannot initiate '{stage_name}': prior stage '{prior_stage}' is not completed (status={prior.status if prior else 'missing'})"
            )

    @staticmethod
    async def initiate_stage(db, book_id: UUID, stage_name: str) -> BookStageStatus:
        await StageManager._validate_sequential(db, book_id, stage_name)

        max_attempt = 1
        existing = await get_stage(db, book_id, stage_name)
        if existing is not None:
            max_attempt = existing.attempt + 1

        row = BookStageStatus(
            book_id=book_id,
            stage_name=stage_name,
            attempt=max_attempt,
            status=StageStatus.INITIATED,
        )
        db.add(row)
        await db.flush()
        await StageManager._update_book_status(db, book_id)
        return row

    @staticmethod
    async def start_stage(db, book_id: UUID, stage_name: str, attempt: int | None = None) -> BookStageStatus:
        row = await get_stage(db, book_id, stage_name, attempt)
        if row is None:
            raise StageTransitionError(f"Stage '{stage_name}' not found for book {book_id}")
        row = await StageManager._lock_stage(db, book_id, stage_name, row.attempt)
        if row.status not in (StageStatus.INITIATED, StageStatus.FAILED, StageStatus.CANCELLED):
            raise StageTransitionError(f"Cannot start '{stage_name}' from status '{row.status}'")
        row.status = StageStatus.PROCESSING
        row.started_at = datetime.now(timezone.utc)
        await db.flush()
        await StageManager._update_book_status(db, book_id)
        return row

    @staticmethod
    async def complete_stage(db, book_id: UUID, stage_name: str, attempt: int | None = None) -> BookStageStatus:
        row = await get_stage(db, book_id, stage_name, attempt)
        if row is None:
            raise StageTransitionError(f"Stage '{stage_name}' not found for book {book_id}")
        row = await StageManager._lock_stage(db, book_id, stage_name, row.attempt)
        if row.status != StageStatus.PROCESSING:
            raise StageTransitionError(f"Cannot complete '{stage_name}' from status '{row.status}'")
        row.status = StageStatus.COMPLETED
        row.completed_at = datetime.now(timezone.utc)
        await db.flush()
        await StageManager._update_book_status(db, book_id)
        return row

    @staticmethod
    async def fail_stage(db, book_id: UUID, stage_name: str, error_log: str = "", attempt: int | None = None) -> BookStageStatus:
        row = await get_stage(db, book_id, stage_name, attempt)
        if row is None:
            raise StageTransitionError(f"Stage '{stage_name}' not found for book {book_id}")
        row = await StageManager._lock_stage(db, book_id, stage_name, row.attempt)
        if row.status not in (StageStatus.PROCESSING, StageStatus.INITIATED):
            raise StageTransitionError(f"Cannot fail '{stage_name}' from status '{row.status}'")
        row.status = StageStatus.FAILED
        row.completed_at = datetime.now(timezone.utc)
        row.error_log = error_log[:2000] if error_log else None
        await db.flush()
        await StageManager._update_book_status(db, book_id)
        return row

    @staticmethod
    async def cancel_stage(db, book_id: UUID, stage_name: str, error_log: str = "", attempt: int | None = None) -> BookStageStatus:
        row = await get_stage(db, book_id, stage_name, attempt)
        if row is None:
            raise StageTransitionError(f"Stage '{stage_name}' not found for book {book_id}")
        row = await StageManager._lock_stage(db, book_id, stage_name, row.attempt)
        if row.status not in (StageStatus.PROCESSING, StageStatus.INITIATED):
            raise StageTransitionError(f"Cannot cancel '{stage_name}' from status '{row.status}'")
        row.status = StageStatus.CANCELLED
        row.completed_at = datetime.now(timezone.utc)
        row.error_log = error_log[:2000] if error_log else None
        await db.flush()
        await StageManager._update_book_status(db, book_id)
        return row

    @staticmethod
    async def reset_book(db, book_id: UUID) -> None:
        await StageManager._lock_book(db, book_id)
        existing = await db.execute(
            select(BookStageStatus).where(BookStageStatus.book_id == book_id)
        )
        for row in existing.scalars().all():
            await db.delete(row)
        await db.flush()
        await StageManager._update_book_status(db, book_id)
