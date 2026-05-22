import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OcrResult(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ocr_results"

    page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pages.id", ondelete="CASCADE"), unique=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    bounding_boxes: Mapped[dict | None] = mapped_column(JSONB)
    corrected_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    language_detected: Mapped[str | None] = mapped_column(String(10))

    page = relationship("Page", back_populates="ocr_result")
