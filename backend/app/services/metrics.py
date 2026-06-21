"""Custom business metrics helpers for New Relic.

These functions emit custom events that appear in the New Relic data
explorer and can be used to build dashboards and alerts for
domain-specific KPIs (book uploads, OCR completions, LLM extractions).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _record(event_type: str, attributes: dict) -> None:
    """Safely record a custom event, no-op when New Relic is unavailable."""
    try:
        import newrelic.agent

        newrelic.agent.record_custom_event(event_type, attributes)
    except ImportError:
        pass
    except Exception as exc:
        logger.debug("Failed to record New Relic event %s: %s", event_type, exc)


def record_book_upload(
    book_id: str,
    filename: str,
    total_pages: int,
    language: str,
) -> None:
    _record("BookUpload", {
        "book_id": book_id,
        "language": language,
        "total_pages": total_pages,
    })


def record_ocr_completion(
    book_id: str,
    avg_confidence: float,
    pages_processed: int,
    duration_sec: float,
) -> None:
    _record("OCRComplete", {
        "book_id": book_id,
        "avg_confidence": avg_confidence,
        "pages_processed": pages_processed,
        "duration_sec": round(duration_sec, 2),
    })


def record_llm_extraction(
    book_id: str,
    model: str,
    batches: int,
    errors: int,
    duration_sec: float,
) -> None:
    _record("LLMExtraction", {
        "book_id": book_id,
        "model": model,
        "batches": batches,
        "errors": errors,
        "duration_sec": round(duration_sec, 2),
    })
