import logging

from celery import Celery
from celery.signals import task_failure, task_rejected, worker_init

from app.core.config import settings

logger = logging.getLogger(__name__)


@worker_init.connect
def _init_newrelic(**kwargs):
    """Safety-net New Relic init in case the sitecustomize hook wasn't injected."""
    if not settings.new_relic_enabled:
        return
    try:
        import os

        import newrelic.agent

        config = os.environ.get("NEW_RELIC_CONFIG_FILE", "newrelic.ini")
        newrelic.agent.initialize(config)
    except ImportError:
        pass
    except Exception as exc:
        logger.error(
            "New Relic worker init failed — Celery tasks will not be traced: %s",
            exc,
        )


@task_failure.connect
def _on_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """Map a Celery failure back to the Job row via ``jobs.celery_task_id``."""
    async def _do():
        from datetime import datetime, timezone

        from sqlalchemy import select

        from app.core.database import async_session_factory
        from app.models.book import Book, BookStatus
        from app.models.job import Job, JobStatus
        from app.services.sse_service import event_id, publish_sync

        try:
            async with async_session_factory() as db:
                job_result = await db.execute(
                    select(Job).where(Job.celery_task_id == task_id)
                )
                job = job_result.scalar_one_or_none()
                if not job or job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    return
                error = (
                    f"{type(exception).__name__}: {exception}"
                    if exception else "unknown"
                )
                job.status = JobStatus.FAILED
                job.error_log = error[:1000]
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()

                book_id = job.book_id
                if book_id:
                    book_result = await db.execute(
                        select(Book).where(Book.id == book_id)
                    )
                    book = book_result.scalar_one_or_none()
                    if book and book.status in (
                        BookStatus.OCR_RUNNING,
                        BookStatus.LLM_RUNNING,
                    ):
                        book.status = BookStatus.OCR_COMPLETE
                    await db.commit()
                    publish_sync(
                        book_id,
                        {
                            "id": event_id(f"job-{JobStatus.FAILED}"),
                            "type": "job.terminal",
                            "book_id": str(book_id),
                            "job_id": str(job.id),
                            "status": JobStatus.FAILED,
                            "error_log": error[:1000],
                        },
                    )
        except Exception as exc:
            logger.error(
                "task_failure handler could not mark job for %s: %s",
                task_id,
                exc,
            )

    try:
        from app.tasks.async_utils import run_async

        run_async(_do())
    except Exception as exc:
        logger.error("Could not run task_failure handler: %s", exc)


@task_rejected.connect
def _on_task_rejected(sender=None, task_id=None, **kwargs):
    """Log rejected tasks; Celery handles re-queueing via ``task_reject_on_worker_lost``."""
    logger.warning("Task %s was rejected: %s", task_id, kwargs)


celery_app = Celery(
    "indic_books",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.ocr_tasks", "app.tasks.llm_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_routes={
        "preprocess_pages_for_book": {"queue": "ocr"},
        "run_ocr_for_book": {"queue": "ocr"},
        "run_llm_extraction": {"queue": "llm"},
    },
)
