"""
SSE (Server-Sent Events) service backed by Redis pub/sub.

Replaces the previous DB-polling implementation with a single long-lived
Redis subscription that fans out to connected SSE clients per book.

Publishers (Celery workers, the pipeline orchestrator, FastAPI request
handlers) call :func:`publish` from either the sync `redis` client
(workers) or `redis.asyncio` (FastAPI). Both connect to the same broker
and write to channels of the form ``book:{book_id}:events``.

The FastAPI process holds a single :class:`redis.asyncio.client` pubsub
connection started during the application lifespan. When a message
arrives, the broker pushes it into the per-book set of in-process
``asyncio.Queue`` objects, one per connected SSE client.

Postgres remains the source of truth — SSE is a notification, not the
state itself. If Redis is unavailable the connection simply never
delivers events and clients fall back to HTTP polling.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
import redis as sync_redis
from fastapi import Request
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.book import Book
from app.models.job import Job

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "book:"
CHANNEL_SUFFIX = ":events"
KEEPALIVE_SECONDS = 15
QUEUE_MAX_SIZE = 100


def channel_for(book_id: str | UUID) -> str:
    return f"{CHANNEL_PREFIX}{book_id}{CHANNEL_SUFFIX}"


def book_id_from_channel(channel: str) -> str | None:
    if not channel.startswith(CHANNEL_PREFIX) or not channel.endswith(CHANNEL_SUFFIX):
        return None
    return channel[len(CHANNEL_PREFIX) : -len(CHANNEL_SUFFIX)]


class SSEService:
    """Fan-out hub: single Redis subscription -> per-book queue sets."""

    def __init__(self) -> None:
        self._connections: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._pubsub: aioredis.client.PubSub | None = None
        self._dispatcher_task: asyncio.Task | None = None
        self._redis: aioredis.Redis | None = None
        self._started = asyncio.Event()
        self._dispatcher_restarts: int = 0

    async def start(self, redis: aioredis.Redis) -> None:
        """Attach to the supplied Redis client and begin the dispatcher loop.

        Called from the FastAPI lifespan handler in :mod:`app.main`.
        """
        if self._started.is_set():
            return
        self._redis = redis
        self._pubsub = redis.pubsub()
        await self._pubsub.psubscribe(f"{CHANNEL_PREFIX}*{CHANNEL_SUFFIX}")
        self._dispatcher_task = asyncio.create_task(self._dispatch_loop(), name="sse-dispatcher")
        self._started.set()
        logger.info("SSE service started (Redis pub/sub fanout)")

    async def stop(self) -> None:
        if not self._started.is_set():
            return
        self._started.clear()
        if self._dispatcher_task is not None:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._dispatcher_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001
                logger.debug("SSE pubsub aclose raised", exc_info=True)
            self._pubsub = None
        async with self._lock:
            self._connections.clear()
        logger.info("SSE service stopped")

    async def _dispatch_loop(self) -> None:
        """Read messages from the global pubsub and fan out to per-book queues.

        Restarts with a 1s backoff on unhandled exceptions so a single
        bad message can't silently drop the rest of the event stream.
        """
        assert self._pubsub is not None
        while True:
            try:
                while True:
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=1.0
                    )
                    if message is None:
                        await asyncio.sleep(0)
                        continue
                    channel = message.get("channel")
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8", errors="replace")
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8", errors="replace")
                    book_id = book_id_from_channel(channel or "")
                    if book_id is None or data is None:
                        continue
                    await self._fanout(book_id, data)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self._dispatcher_restarts += 1
                logger.exception(
                    "SSE dispatcher loop crashed; restarting (attempt %d)",
                    self._dispatcher_restarts,
                )
                await asyncio.sleep(1.0)

    async def _fanout(self, book_id: str, data: str) -> None:
        async with self._lock:
            queues = list(self._connections.get(book_id, ()))
        for q in queues:
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                logger.warning("SSE queue full for book %s; dropping message", book_id)

    async def connect(self, book_id: str, request: Request) -> EventSourceResponse:
        """Open an SSE stream for a single client."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
        async with self._lock:
            self._connections[book_id].add(queue)

        async def event_generator():
            try:
                snapshot = await self._build_snapshot(book_id)
                yield {
                    "event": "snapshot",
                    "id": f"snapshot-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                    "data": json.dumps(snapshot),
                }
                yield {
                    "event": "connected",
                    "data": json.dumps({"book_id": book_id, "status": "connected"}),
                }

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_SECONDS)
                    except asyncio.TimeoutError:
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps(
                                {
                                    "book_id": book_id,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            ),
                        }
                        continue

                    try:
                        payload = json.loads(data)
                    except (TypeError, ValueError):
                        payload = {"raw": data}

                    event_type = payload.get("type") if isinstance(payload, dict) else None
                    yield {
                        "event": event_type or "message",
                        "id": payload.get("id") if isinstance(payload, dict) else None,
                        "data": data,
                    }
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("SSE event generator error for book %s", book_id)
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "internal_error"}),
                }
            finally:
                async with self._lock:
                    self._connections[book_id].discard(queue)
                    if not self._connections[book_id]:
                        self._connections.pop(book_id, None)
                logger.info("SSE client disconnected for book %s", book_id)

        return EventSourceResponse(event_generator())

    async def _build_snapshot(self, book_id: str) -> dict[str, Any]:
        """Initial state dump sent on connect — derived from Postgres."""
        try:
            book_uuid = UUID(book_id)
        except (TypeError, ValueError):
            return {"book": None, "jobs": []}

        try:
            async with async_session_factory() as db:
                book_result = await db.execute(select(Book).where(Book.id == book_uuid))
                book = book_result.scalar_one_or_none()
                jobs_result = await db.execute(
                    select(Job).where(Job.book_id == book_uuid).order_by(Job.created_at.desc())
                )
                jobs = jobs_result.scalars().all()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to build SSE snapshot for book %s", book_id)
            return {"book": None, "jobs": []}

        return {
            "book": _serialise_book(book) if book else None,
            "jobs": [_serialise_job(j) for j in jobs],
        }

    def get_connection_count(self, book_id: str) -> int:
        return len(self._connections.get(book_id, ()))


def _serialise_book(book: Book) -> dict[str, Any]:
    return {
        "id": str(book.id),
        "filename": book.filename,
        "title": book.title,
        "language": book.language,
        "status": book.status,
        "total_pages": book.total_pages,
        "created_at": book.created_at.isoformat() if book.created_at else None,
        "updated_at": book.updated_at.isoformat() if book.updated_at else None,
    }


def _serialise_job(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "book_id": str(job.book_id) if job.book_id else None,
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_log": job.error_log,
    }


# ---------------------------------------------------------------------------
# Publish helpers — used by Celery workers (sync) and FastAPI (async)
# ---------------------------------------------------------------------------

# Reuse a single connection pool across calls so a 200-page book with
# per-page progress doesn't open/close hundreds of TCP connections.
_sync_pool: sync_redis.ConnectionPool | None = None
_sync_pool_lock = threading.Lock()


def _sync_redis() -> sync_redis.Redis:
    global _sync_pool
    if _sync_pool is None:
        with _sync_pool_lock:
            if _sync_pool is None:
                _sync_pool = sync_redis.ConnectionPool.from_url(
                    settings.redis_url,
                    decode_responses=True,
                    max_connections=16,
                )
    return sync_redis.Redis(connection_pool=_sync_pool)


def publish_sync(book_id: str | UUID, event: dict[str, Any]) -> None:
    """Publish an event from a Celery worker (no event loop available)."""
    try:
        client = _sync_redis()
        client.publish(channel_for(book_id), json.dumps(event, default=str))
    except Exception:  # noqa: BLE001
        logger.exception("SSE publish_sync failed for book %s", book_id)


async def publish_async(book_id: str | UUID, event: dict[str, Any]) -> None:
    """Publish an event from the FastAPI process (uses the shared pool)."""
    from app.main import _redis_pool  # local import to avoid circular

    if _redis_pool is None:
        return
    try:
        await _redis_pool.publish(channel_for(book_id), json.dumps(event, default=str))
    except Exception:  # noqa: BLE001
        logger.exception("SSE publish_async failed for book %s", book_id)


def event_id(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"


# Global instance — wired up in app.main lifespan
sse_service = SSEService()
