"""Shared async utilities for Celery tasks.

Provides a consistent way to run async coroutines from synchronous Celery tasks.

Each Celery prefork worker process maintains a single persistent event loop.
This is required because New Relic's asyncio instrumentation patches
``loop.create_task`` globally and caches references to the active loop —
creating a new loop per call causes "Future attached to a different loop"
errors inside New Relic's hooks.

The database engine uses :class:`NullPool` so that no connections are reused
across ``run_until_complete`` calls, avoiding stale asyncpg futures on pooled
connections.
"""

import asyncio
import atexit
import logging
import os

logger = logging.getLogger(__name__)

# One event loop per worker process, keyed by PID to handle forks safely.
_loop: asyncio.AbstractEventLoop | None = None
_loop_pid: int | None = None


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """Return the worker's persistent event loop, creating one if needed."""
    global _loop, _loop_pid
    pid = os.getpid()
    if _loop is None or _loop.is_closed() or _loop_pid != pid:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop_pid = pid
    return _loop


def _cleanup() -> None:
    """Dispose the engine and close the loop on worker shutdown."""
    global _loop, _loop_pid
    if _loop is not None and not _loop.is_closed():
        try:
            import app.core.database as _db
            if _db._engine is not None:
                _loop.run_until_complete(_db._engine.dispose())
        except Exception:
            pass
        _loop.close()
    _loop = None
    _loop_pid = None


atexit.register(_cleanup)


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task.

    Uses a persistent event loop per worker process so that New Relic's
    asyncio hooks stay bound to a single, long-lived loop.  The database
    engine uses NullPool, so each session creates a fresh connection and no
    stale futures leak between calls.

    NOT thread-safe — use :func:`run_async_threadsafe` from threads.
    """
    loop = _get_or_create_loop()
    return loop.run_until_complete(coro)


def run_async_threadsafe(coro):
    """Run an async coroutine from a background thread.

    Creates a fresh event loop for each call so that multiple threads can
    run concurrent async code without corrupting a shared loop.  Each call
    also ensures the database engine is initialised inside its own loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Lazy-init the DB engine inside this thread's loop
        import app.core.database as _db
        _db._ensure_engine()
        return loop.run_until_complete(coro)
    finally:
        loop.close()
