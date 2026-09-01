"""Celery tasks for the Indic Book Metadata Extractor.

Re-exports the live tasks and the Celery app for tests and external
scripts so callers don't need the dotted module path.
"""

from app.tasks.celery_app import celery_app
from app.tasks.llm_tasks import run_llm_extraction
from app.tasks.ocr_tasks import (
    preprocess_pages_for_book,
    run_ocr_for_book,
)

__all__ = [
    "celery_app",
    "preprocess_pages_for_book",
    "run_ocr_for_book",
    "run_llm_extraction",
]
