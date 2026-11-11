from enum import StrEnum

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BookStatus(StrEnum):
    UPLOADED = "uploaded"
    PAGES_SELECTED = "pages_selected"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETE = "ocr_complete"
    LLM_RUNNING = "llm_running"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETE = "complete"


# Books in these states form the public catalog. Owners and admins always see
# their own/in-progress books in addition to these.
PUBLIC_BOOK_STATUSES = frozenset({BookStatus.COMPLETE, BookStatus.AWAITING_REVIEW})


class Book(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "books"

    title: Mapped[str | None] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="tel")
    status: Mapped[str] = mapped_column(String(30), default=BookStatus.UPLOADED)
    total_pages: Mapped[int | None] = mapped_column(Integer)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    owner = relationship("User", back_populates="books")
    pages = relationship("Page", back_populates="book", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="book", cascade="all, delete-orphan")
    metadata_record = relationship(
        "BookMetadata", back_populates="book", uselist=False, cascade="all, delete-orphan"
    )
    metadata_evidence = relationship(
        "MetadataFieldEvidence",
        back_populates="book",
        cascade="all, delete-orphan",
    )
