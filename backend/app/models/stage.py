from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import async_session_factory
from app.models.base import Base, UUIDMixin


class BookStage(str, Enum):
    UPLOAD = "upload"
    PAGE_SELECTION = "page_selection"
    OCR = "ocr"
    LLM_EXTRACTION = "llm_extraction"
    HUMAN_REVIEW = "human_review"
    COMPLETION = "completion"


class StageStatus(str, Enum):
    INITIATED = "initiated"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


STAGE_ORDER = [
    BookStage.UPLOAD,
    BookStage.PAGE_SELECTION,
    BookStage.OCR,
    BookStage.LLM_EXTRACTION,
    BookStage.HUMAN_REVIEW,
    BookStage.COMPLETION,
]


class BookStageStatus(UUIDMixin, Base):
    __tablename__ = "book_stage_status"

    book_id: Mapped[UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    stage_name: Mapped[str] = mapped_column(String(30), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StageStatus.INITIATED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('initiated','processing','completed','failed','cancelled')", name="ck_stage_status"),
        CheckConstraint(f"stage_name IN ({','.join(repr(s.value) for s in BookStage)})", name="ck_stage_name"),
    )


async def get_current_stages(book_id: UUID) -> list[BookStageStatus]:
    """Return the latest attempt row for each stage for a book."""
    latest = (
        select(BookStageStatus.stage_name, func.max(BookStageStatus.attempt).label("max_attempt"))
        .where(BookStageStatus.book_id == book_id)
        .group_by(BookStageStatus.stage_name)
        .subquery()
    )
    async with async_session_factory() as db:
        result = await db.execute(
            select(BookStageStatus)
            .join(latest, (BookStageStatus.stage_name == latest.c.stage_name) & (BookStageStatus.attempt == latest.c.max_attempt))
            .where(BookStageStatus.book_id == book_id)
            .order_by(BookStageStatus.stage_name)
        )
        return list(result.scalars().all())


async def get_stage(book_id: UUID, stage_name: str, attempt: int | None = None) -> BookStageStatus | None:
    async with async_session_factory() as db:
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
