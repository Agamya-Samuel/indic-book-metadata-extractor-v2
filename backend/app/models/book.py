from enum import StrEnum

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BookStatus(StrEnum):
    UPLOADED = "uploaded"
    PAGES_SELECTED = "pages_selected"
    OCR_RUNNING = "ocr_running"
    OCR_COMPLETE = "ocr_complete"
    LLM_RUNNING = "llm_running"
    COMPLETE = "complete"


class Book(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "books"

    title: Mapped[str | None] = mapped_column(String(500))
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="tel")
    status: Mapped[str] = mapped_column(String(30), default=BookStatus.UPLOADED)
    total_pages: Mapped[int | None] = mapped_column(Integer)

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
