import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class Page(UUIDMixin, Base):
    __tablename__ = "pages"

    book_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500))
    processed_image_path: Mapped[str | None] = mapped_column(String(500))
    preprocessing_config: Mapped[dict | None] = mapped_column(JSONB)
    # Set when OCR failed for this page; cleared on the next successful run.
    ocr_error: Mapped[str | None] = mapped_column(Text)

    book = relationship("Book", back_populates="pages")
    ocr_result = relationship(
        "OcrResult", back_populates="page", uselist=False, cascade="all, delete-orphan"
    )
