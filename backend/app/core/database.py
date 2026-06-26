import logging
import time
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy engine / session factory
# ---------------------------------------------------------------------------
# The engine MUST be created inside a running event loop so that asyncpg
# binds its internal futures to the correct loop.  At module-import time
# (Celery main process, before fork) no loop exists, so we defer creation.
# ---------------------------------------------------------------------------

_engine = None
_async_session_factory = None


def _ensure_engine():
    """Create the engine and session factory on first use (inside a loop)."""
    global _engine, _async_session_factory
    if _async_session_factory is not None:
        return

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        poolclass=NullPool,
    )

    # Slow-query detection
    @event.listens_for(_engine.sync_engine, "before_cursor_execute")
    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        conn.info.setdefault("query_start_time", []).append(time.monotonic())

    @event.listens_for(_engine.sync_engine, "after_cursor_execute")
    def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start_times = conn.info.get("query_start_time")
        if not start_times:
            return
        elapsed = time.monotonic() - start_times.pop(-1)
        if elapsed > 1.0:
            logger.warning("Slow query (%.2fs): %s", elapsed, statement[:300])

    _async_session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )


class _LazySessionFactory:
    """Proxy that lazily initialises the engine on first use.

    Task code does ``from app.core.database import async_session_factory``
    and then ``async with async_session_factory() as db: ...``.  The
    ``__call__`` delegates to the real factory after ensuring the engine
    exists.
    """

    def __call__(self):
        _ensure_engine()
        return _async_session_factory()

    def __getattr__(self, name):
        _ensure_engine()
        return getattr(_async_session_factory, name)


async_session_factory = _LazySessionFactory()


# Used by FastAPI via ``Depends(get_db)``
def get_engine():
    _ensure_engine()
    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _ensure_engine()
    async with _async_session_factory() as session:
        yield session
