import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OcrResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ocr_results"

    page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), unique=True)
    raw_text: Mapped[str | None] = mapped_column(Text)
    bounding_boxes: Mapped[dict | None] = mapped_column(JSONB)
    corrected_text: Mapped[str | None] = mapped_column(Text)
    cleaned_text: Mapped[str | None] = mapped_column(Text)
    corrections: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    language_detected: Mapped[str | None] = mapped_column(String(10))
    # Which path produced the text, for audit/review. ``ocr_route`` is set only
    # when page-level script routing changed the engine/model.
    ocr_engine: Mapped[str | None] = mapped_column(String(20))
    ocr_route: Mapped[str | None] = mapped_column(String(50))
    ocr_coverage: Mapped[float | None] = mapped_column(Float)
    ocr_script: Mapped[dict | None] = mapped_column(JSONB)

    page = relationship("Page", back_populates="ocr_result")
