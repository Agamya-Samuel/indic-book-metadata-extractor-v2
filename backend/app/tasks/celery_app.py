from celery import Celery
from celery.signals import worker_init

from app.core.config import settings


@worker_init.connect
def _init_newrelic(**kwargs):
    """Safety-net: ensure the New Relic agent is initialised in each worker process.

    When launched via `newrelic-admin run-program` the sitecustomize hook normally
    handles this, but calling initialize() again is idempotent and protects against
    environments where the hook is not injected (e.g. bare `celery worker` invocations).
    """
    if not settings.new_relic_enabled:
        return
    try:
        import newrelic.agent
        import os

        _nr_config = os.environ.get("NEW_RELIC_CONFIG_FILE", "newrelic.ini")
        newrelic.agent.initialize(_nr_config)
    except ImportError:
        pass  # newrelic not installed — expected in dev
    except Exception as exc:
        import logging

        logging.getLogger(__name__).error(
            "New Relic worker init failed — Celery tasks will not be traced: %s", exc,
        )


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
