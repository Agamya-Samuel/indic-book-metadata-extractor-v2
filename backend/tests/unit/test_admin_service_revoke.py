"""Revocation of dispatched Celery tasks when a job is cancelled."""

from unittest.mock import patch

import pytest

from app.models.job import Job, JobStatus
from app.services import admin_service


def _job(task_id: str | None, status: str) -> Job:
    job = Job(job_type="ocr", status=status, progress=0.0)
    job.celery_task_id = task_id
    return job


class TestRevokeCeleryTask:
    def test_running_job_is_terminated(self):
        with patch("app.tasks.celery_app.celery_app.control.revoke") as revoke:
            admin_service._revoke_celery_task(_job("task-1", JobStatus.RUNNING))

        revoke.assert_called_once_with("task-1", terminate=True, reply=False)

    def test_queued_job_is_revoked_without_termination(self):
        with patch("app.tasks.celery_app.celery_app.control.revoke") as revoke:
            admin_service._revoke_celery_task(_job("task-2", JobStatus.QUEUED))

        revoke.assert_called_once_with("task-2", terminate=False, reply=False)

    def test_job_without_task_id_is_a_noop(self):
        with patch("app.tasks.celery_app.celery_app.control.revoke") as revoke:
            admin_service._revoke_celery_task(_job(None, JobStatus.RUNNING))

        revoke.assert_not_called()

    def test_broker_failure_does_not_raise(self):
        with patch(
            "app.tasks.celery_app.celery_app.control.revoke",
            side_effect=RuntimeError("broker down"),
        ):
            admin_service._revoke_task_ids([("task-3", True), (None, False)])

    def test_batch_revokes_each_task(self):
        with patch("app.tasks.celery_app.celery_app.control.revoke") as revoke:
            admin_service._revoke_task_ids([("a", True), ("b", False)])

        assert revoke.call_count == 2
        revoke.assert_any_call("a", terminate=True, reply=False)
        revoke.assert_any_call("b", terminate=False, reply=False)


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.RUNNING])
def test_revoke_helper_exists_for_every_cancelled_status(status):
    """Regression: the helper was called but never defined (AttributeError 500)."""
    assert hasattr(admin_service, "_revoke_celery_task")
    with patch("app.tasks.celery_app.celery_app.control.revoke") as revoke:
        admin_service._revoke_celery_task(_job("task-x", status))
    assert revoke.called