import uuid

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class MetadataFieldEvidence(UUIDMixin, TimestampMixin, Base):
    """One row per extracted metadata field, with provenance.

    The legacy ``BookMetadata.fields`` JSONB blob is kept for fast read;
    this table mirrors each populated field with a confidence score, the
    page the value was sourced from, a text snippet from the OCR output,
    and the extraction method that produced it (regex / dictionary / NER
    / LLM / human). This makes the extraction pipeline debuggable and
    provides the per-field accuracy signal needed to demo production
    quality to the OKI team.
    """

    __tablename__ = "metadata_field_evidence"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), nullable=True
    )
    source_page_number: Mapped[int | None] = mapped_column()
    source_text_snippet: Mapped[str | None] = mapped_column(Text)
    source_bbox: Mapped[dict | None] = mapped_column(JSONB)
    extraction_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="llm"
    )

    __table_args__ = (
        Index(
            "ix_metadata_field_evidence_book_field",
            "book_id",
            "field_name",
            unique=True,
        ),
    )

    book = relationship("Book", back_populates="metadata_evidence")
    source_page = relationship("Page", foreign_keys=[source_page_id])
