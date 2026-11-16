"""Process-wide Redis accessor.

The API lifespan owns the connection pool and registers it here so request
handlers, the SSE publisher, and the system-metrics probe share one pool
instead of opening a new TCP connection per call.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_pool: aioredis.Redis | None = None


def set_redis_pool(pool: aioredis.Redis | None) -> None:
    global _pool
    _pool = pool


def get_redis_pool() -> aioredis.Redis | None:
    return _pool


def get_redis() -> aioredis.Redis:
    """Return the shared client, lazily creating a pool if none is registered."""
    global _pool
    if _pool is None:
        _pool = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _pool
