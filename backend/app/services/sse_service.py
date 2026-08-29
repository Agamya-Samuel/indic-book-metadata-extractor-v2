"""
SSE (Server-Sent Events) service for real-time job progress updates.

This module manages SSE connections per book, allowing the frontend to receive
real-time updates when jobs start, make progress, or complete.

The service polls the database for job updates and streams events to connected clients.
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from app.core.database import async_session_factory
from app.models.job import Job, JobStatus

logger = logging.getLogger(__name__)


class SSEService:
    """
    Manages SSE connections for book job updates.
    
    Each book can have multiple connected clients (e.g., multiple browser tabs).
    The service polls the database for job updates and streams them to all
    connected clients for each book.
    """
    
    def __init__(self, poll_interval: float = 1.0):
        # book_id -> set of queues for connected clients
        self._connections: dict[str, set[asyncio.Queue]] = defaultdict(set)
        # book_id -> last known job state for comparison
        self._last_job_states: dict[str, dict[str, Any]] = defaultdict(dict)
        # Polling interval in seconds
        self._poll_interval = poll_interval
        self._lock = asyncio.Lock()
    
    async def connect(self, book_id: str, request: Request) -> EventSourceResponse:
        """
        Connect a client to receive SSE updates for a book.
        
        Returns an EventSourceResponse that keeps the connection open and
        polls the database for job updates, streaming them to the client.
        """
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        
        async with self._lock:
            self._connections[book_id].add(queue)
        
        logger.info(f"SSE client connected for book {book_id}")
        
        async def event_generator():
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({"book_id": book_id, "status": "connected"}),
            }
            
            try:
                while True:
                    # Poll for job updates
                    await asyncio.sleep(self._poll_interval)
                    
                    try:
                        jobs_data = await self._get_book_jobs(book_id)
                        
                        # Check for job state changes
                        for job_data in jobs_data:
                            job_id = job_data["id"]
                            last_state = self._last_job_states[book_id].get(job_id, {})
                            
                            if self._has_state_changed(last_state, job_data):
                                event_type = self._get_event_type(last_state, job_data)
                                if event_type:
                                    message = json.dumps({
                                        "type": event_type,
                                        "book_id": book_id,
                                        **job_data
                                    })
                                    try:
                                        queue.put_nowait(message)
                                    except asyncio.QueueFull:
                                        logger.warning(f"SSE queue full for book {book_id}")
                                    
                                    # Update last known state
                                    self._last_job_states[book_id][job_id] = job_data.copy()
                                
                        # Also send heartbeat
                        yield {"event": "heartbeat", "data": json.dumps({"book_id": book_id, "timestamp": datetime.now(timezone.utc).isoformat()})}
                        
                    except Exception as e:
                        logger.error(f"Error polling jobs for book {book_id}: {e}")
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": str(e)}),
                        }
                        
            except asyncio.CancelledError:
                logger.info(f"SSE client disconnected for book {book_id}")
                raise
            finally:
                async with self._lock:
                    self._connections[book_id].discard(queue)
                    if not self._connections[book_id]:
                        del self._connections[book_id]
                        if book_id in self._last_job_states:
                            del self._last_job_states[book_id]
        
        return EventSourceResponse(event_generator())
    
    async def _get_book_jobs(self, book_id: str) -> list[dict[str, Any]]:
        """Get all jobs for a book from the database."""
        try:
            async with async_session_factory() as db:
                result = await db.execute(
                    select(Job).where(Job.book_id == UUID(book_id))
                )
                jobs = result.scalars().all()
                
                return [
                    {
                        "id": str(job.id),
                        "job_type": job.job_type,
                        "status": job.status,
                        "progress": job.progress,
                        "error_log": job.error_log,
                        "created_at": job.created_at.isoformat() if job.created_at else None,
                        "started_at": job.started_at.isoformat() if job.started_at else None,
                        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    }
                    for job in jobs
                ]
        except Exception as e:
            logger.error(f"Error fetching jobs for book {book_id}: {e}")
            return []
    
    def _has_state_changed(self, old_state: dict, new_state: dict) -> bool:
        """Check if job state has changed."""
        if not old_state:
            return True
        return (
            old_state.get("status") != new_state.get("status") or
            old_state.get("progress") != new_state.get("progress") or
            old_state.get("error_log") != new_state.get("error_log")
        )
    
    def _get_event_type(self, old_state: dict, new_state: dict) -> str | None:
        """Determine the event type based on state change."""
        new_status = new_state.get("status")
        
        if new_status == "running":
            if old_state.get("status") in (None, "queued"):
                return "job_started"
            return "job_progress"
        elif new_status == "completed":
            return "job_complete"
        elif new_status == "failed":
            return "job_failed"
        elif new_status == "cancelled":
            return "job_cancelled"
        
        return None
    
    def get_connection_count(self, book_id: str) -> int:
        """Get the number of connected clients for a book."""
        return len(self._connections.get(book_id, []))
    
    async def close_all(self) -> None:
        """Close all connections (used during shutdown)."""
        async with self._lock:
            self._connections.clear()
            self._last_job_states.clear()


# Global SSE service instance
sse_service = SSEService()
