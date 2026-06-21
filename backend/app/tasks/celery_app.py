from celery import Celery

from app.core.config import settings

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
        "run_ocr_for_page": {"queue": "ocr"},
        "run_ocr_for_book": {"queue": "ocr"},
        "_ocr_book_complete": {"queue": "ocr"},
        "run_llm_extraction": {"queue": "llm"},
    },
)
