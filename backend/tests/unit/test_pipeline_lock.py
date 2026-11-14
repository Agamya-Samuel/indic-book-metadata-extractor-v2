"""The single-book pipeline lock fails open, retries when busy, and releases."""

from unittest.mock import MagicMock

import pytest

from app.tasks import pipeline_lock as pl


class _Retry(Exception):
    pass


class _Task:
    def retry(self, **kwargs):
        raise _Retry(kwargs)


def test_acquire_returns_true_when_set_succeeds(monkeypatch):
    client = MagicMock()
    client.set.return_value = True
    monkeypatch.setattr(pl, "_redis_client", lambda: client)

    assert pl.acquire("job-1") is True
    client.set.assert_called_once_with(pl.LOCK_KEY, "job-1", nx=True, ex=pl.LOCK_TTL_SECONDS)


def test_acquire_returns_false_when_held(monkeypatch):
    client = MagicMock()
    client.set.return_value = None
    monkeypatch.setattr(pl, "_redis_client", lambda: client)

    assert pl.acquire("job-1") is False


def test_acquire_fails_open_when_redis_is_down(monkeypatch):
    client = MagicMock()
    client.set.side_effect = RuntimeError("redis down")
    monkeypatch.setattr(pl, "_redis_client", lambda: client)

    assert pl.acquire("job-1") is True


def test_decorator_retries_while_the_lock_is_held(monkeypatch):
    fn = MagicMock()
    wrapped = pl.single_book_task(fn)
    monkeypatch.setattr(pl, "acquire", lambda owner: False)

    with pytest.raises(_Retry):
        wrapped(_Task(), "job-1", "book-1")

    fn.assert_not_called()


def test_decorator_runs_the_body_and_releases(monkeypatch):
    released: list[str] = []
    monkeypatch.setattr(pl, "acquire", lambda owner: True)
    monkeypatch.setattr(pl, "release", lambda owner: released.append(owner))

    wrapped = pl.single_book_task(lambda self, job_id, value=0: value + 1)

    assert wrapped(object(), "job-1", 2) == 3
    assert released == ["job-1"]


def test_decorator_releases_after_a_body_failure(monkeypatch):
    released: list[str] = []
    monkeypatch.setattr(pl, "acquire", lambda owner: True)
    monkeypatch.setattr(pl, "release", lambda owner: released.append(owner))

    def boom(self, job_id):
        raise ValueError("bad page")

    wrapped = pl.single_book_task(boom)

    with pytest.raises(ValueError):
        wrapped(object(), "job-1")

    assert released == ["job-1"]
