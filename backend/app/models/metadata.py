import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BookMetadata(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "metadata"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), unique=True
    )
    fields: Mapped[dict | None] = mapped_column(JSONB)

    book = relationship("Book", back_populates="metadata_record")
