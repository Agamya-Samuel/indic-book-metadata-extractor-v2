import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin
from datetime import datetime
from sqlalchemy import DateTime, func


class LlmRun(UUIDMixin, Base):
    __tablename__ = "llm_runs"

    job_id: Mapped[uuid.UUID | None] = mapped_column(
        # SET NULL keeps LlmRun audit rows after the parent Job is
        # deleted (e.g. on book purge). Downstream consumers see
        # job_id=None for these orphan runs.
        ForeignKey("jobs.id", ondelete="SET NULL")
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_template: Mapped[str | None] = mapped_column(Text)
    batch_config: Mapped[dict | None] = mapped_column(JSONB)
    raw_response: Mapped[str | None] = mapped_column(Text)
    parsed_fields: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job = relationship("Job", back_populates="llm_runs")
