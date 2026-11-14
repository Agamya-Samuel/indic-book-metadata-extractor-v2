"""A single global lock so only one book is processed at a time.

The host is 4 vCPU / 16 GB with no swap; running two books oversubscribes the
CPU and makes both slower. This lock is the cross-worker guarantee (the worker
also runs with concurrency 1). It fails open when Redis is unavailable: losing
serialisation is better than stalling the whole pipeline.
"""

from __future__ import annotations

import functools
import logging
import threading

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

LOCK_KEY = "pipeline:single-book"
LOCK_TTL_SECONDS = 300

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""

_REFRESH_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""

_client: redis.Redis | None = None
_client_lock = threading.Lock()


def _redis_client() -> redis.Redis:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                )
    return _client


def acquire(owner: str) -> bool:
    """Take the lock, or return False when another book holds it."""
    try:
        return bool(
            _redis_client().set(
                LOCK_KEY, owner, nx=True, ex=LOCK_TTL_SECONDS
            )
        )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Single-book pipeline lock unavailable; continuing without it",
            exc_info=True,
        )
        return True


def refresh(owner: str) -> None:
    """Extend the lock while work is still progressing."""
    try:
        _redis_client().eval(
            _REFRESH_SCRIPT, 1, LOCK_KEY, owner, LOCK_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001
        logger.debug("Could not refresh the pipeline lock", exc_info=True)


def release(owner: str) -> None:
    """Release the lock only if this owner still holds it."""
    try:
        _redis_client().eval(_RELEASE_SCRIPT, 1, LOCK_KEY, owner)
    except Exception:  # noqa: BLE001
        logger.debug("Could not release the pipeline lock", exc_info=True)


def single_book_task(fn):
    """Celery task decorator: acquire the global pipeline lock around the task.

    Must be applied under ``@celery_app.task(bind=True)`` so ``self.retry`` is
    available when another book holds the lock.
    """

    @functools.wraps(fn)
    def wrapper(self, job_id_str, *args, **kwargs):
        if not acquire(job_id_str):
            logger.info(
                "Job %s is waiting for the single-book pipeline lock", job_id_str
            )
            # ~3 hours of 15s waits; with concurrency 1 this is only reached
            # when a second worker container is added.
            raise self.retry(countdown=15, max_retries=720)
        try:
            return fn(self, job_id_str, *args, **kwargs)
        finally:
            release(job_id_str)

    return wrapper