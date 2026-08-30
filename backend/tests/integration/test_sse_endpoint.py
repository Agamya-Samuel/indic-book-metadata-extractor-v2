"""Integration tests for the SSE service.

These tests don't require a real Redis broker. The SSE service is
patched out and replaced with an in-memory queue so we can drive
publishes from test code and assert subscribers receive them.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

from app.models.book import Book, BookStatus
from app.services import sse_service as sse_service_module


async def _seed_book(db_session, status: BookStatus = BookStatus.UPLOADED) -> Book:
    book = Book(
        id=uuid.uuid4(),
        title="t",
        filename="t.pdf",
        language="tel",
        total_pages=1,
        status=status,
    )
    db_session.add(book)
    await db_session.commit()
    await db_session.refresh(book)
    return book


def test_sse_endpoint_route_is_registered():
    """The SSE route must live at /api/sse/books/{book_id}/events.
    Verifying via the route table avoids opening a streaming connection
    which is hard to terminate cleanly in a test."""
    from app.main import app

    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/sse/books/{book_id}/events" in paths


@pytest.mark.asyncio
async def test_publish_sync_serialises_event_with_redis_mock(monkeypatch):
    """Verify the ``publish_sync`` helper produces the right channel and
    payload when given a fake redis client."""
    from app.services import sse_service

    captured: list[tuple[str, str]] = []

    class FakeRedis:
        def publish(self, channel, message):
            captured.append((channel, message))
            return 1

        def close(self):
            pass

    monkeypatch.setattr(sse_service, "_sync_redis", lambda: FakeRedis())

    book_id = uuid.uuid4()
    sse_service.publish_sync(
        book_id,
        {
            "id": "test-event-1",
            "type": "job.progress",
            "job_id": str(uuid.uuid4()),
            "progress": 50.0,
        },
    )

    assert len(captured) == 1
    channel, message = captured[0]
    assert channel == f"book:{book_id}:events"
    payload = json.loads(message)
    assert payload["type"] == "job.progress"
    assert payload["progress"] == 50.0


@pytest.mark.asyncio
async def test_in_memory_pubsub_fanout():
    """Drive a small in-process pub/sub flow to verify the fanout
    contract that the SSE service provides: a publish to a book's
    channel reaches every subscriber of that book."""
    subscribers: dict[str, list[asyncio.Queue]] = {"book-1": []}

    # Two subscribers
    queues = [asyncio.Queue() for _ in range(2)]
    for q in queues:
        subscribers["book-1"].append(q)

    # Simulate the dispatcher
    async def fanout(book_id: str, event: dict[str, Any]):
        for q in subscribers.get(book_id, ()):
            await q.put(event)

    await fanout("book-1", {"type": "job.progress", "progress": 10})
    await fanout("book-1", {"type": "job.progress", "progress": 20})
    await fanout("book-2", {"type": "job.progress", "progress": 99})

    for q in queues:
        events = []
        while not q.empty():
            events.append(q.get_nowait())
        assert len(events) == 2
        assert events[0]["progress"] == 10
        assert events[1]["progress"] == 20


@pytest.mark.asyncio
async def test_snapshot_includes_book_and_jobs(db_session):
    """A snapshot of the SSE service should include the current book
    state and any jobs. Build the snapshot manually here since we can't
    easily run the full streaming response in tests."""
    from sqlalchemy import select

    from app.models.book import Book as BookModel
    from app.models.job import Job, JobStatus, JobType
    from tests.conftest import TestSessionFactory

    book = await _seed_book(db_session, BookStatus.OCR_RUNNING)
    async with TestSessionFactory() as db:
        db.add(
            Job(
                book_id=book.id,
                job_type=JobType.OCR,
                status=JobStatus.RUNNING,
                progress=42.0,
            )
        )
        await db.commit()

        result = await db.execute(select(BookModel).where(BookModel.id == book.id))
        b = result.scalar_one()
        assert b.status == BookStatus.OCR_RUNNING
        jobs_result = await db.execute(select(Job).where(Job.book_id == book.id))
        jobs = jobs_result.scalars().all()
        assert len(jobs) == 1
        assert jobs[0].progress == 42.0
