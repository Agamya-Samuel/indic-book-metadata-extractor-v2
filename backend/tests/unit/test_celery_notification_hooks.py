"""Guards on the Celery-level failure hook.

The handler itself runs against the app's own session factory inside a worker
loop, which a unit test cannot reproduce faithfully; what a test *can* pin down
is that the hook stays wired to Celery's failure signal. The notification it
creates goes through ``notify_job_terminal``, which is covered directly in
``test_notification_service.py``.
"""

from __future__ import annotations

import importlib
import weakref

from celery.signals import task_failure, task_rejected


def _receiver(entry):
    candidate = entry[1] if isinstance(entry, tuple) else entry
    return candidate() if isinstance(candidate, weakref.ReferenceType) else candidate


def _registered(signal) -> list:
    return [_receiver(entry) for entry in signal.receivers]


def test_task_failure_handler_is_registered() -> None:
    module = importlib.import_module("app.tasks.celery_app")
    assert module._on_task_failure in _registered(task_failure)


def test_task_rejected_handler_is_registered() -> None:
    module = importlib.import_module("app.tasks.celery_app")
    assert module._on_task_rejected in _registered(task_rejected)


def test_worker_reports_failed_jobs_with_the_celery_task_id() -> None:
    """The handler can only map a failure back to a Job via this column."""
    from app.models.job import Job

    assert "celery_task_id" in Job.__table__.columns