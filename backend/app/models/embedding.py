import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from datetime import datetime
from sqlalchemy import DateTime, func

from pgvector.sqlalchemy import Vector


class Embedding(UUIDMixin, Base):
    __tablename__ = "embeddings"

    book_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE")
    )
    embedding = mapped_column(Vector(768))
    source_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    book = relationship("Book")
