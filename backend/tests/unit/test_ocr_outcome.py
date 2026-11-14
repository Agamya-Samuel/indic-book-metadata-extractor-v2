"""Partial OCR runs complete; only an all-pages failure is a failure."""

from app.models.job import JobStatus
from app.tasks.ocr_tasks import ocr_outcome


def test_no_errors_completes_without_log():
    assert ocr_outcome(3, []) == (JobStatus.COMPLETED, None)


def test_partial_failure_still_completes():
    status, log = ocr_outcome(3, ["Page 2: boom"])
    assert status == JobStatus.COMPLETED
    assert log is not None and log.startswith("Some pages failed:")


def test_every_page_failing_is_a_failure():
    status, log = ocr_outcome(2, ["Page 1: boom", "Page 2: boom"])
    assert status == JobStatus.FAILED
    assert log is not None and log.startswith("All pages failed:")


def test_zero_page_run_is_treated_as_partial_not_all_failed():
    status, log = ocr_outcome(0, ["Page 1: boom"])
    assert status == JobStatus.COMPLETED
    assert log is not None and log.startswith("Some pages failed:")
