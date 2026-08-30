"""
SSE (Server-Sent Events) API endpoints for real-time job updates.
"""

from fastapi import APIRouter, Request

from app.services.sse_service import sse_service

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/books/{book_id}/events")
async def stream_book_events(book_id: str, request: Request):
    """
    Stream real-time events for a book's jobs.
    
    Clients connect to this endpoint to receive SSE events when:
    - A job starts (job_started)
    - A job makes progress (job_progress)
    - A job completes (job_complete)
    - A job fails (job_failed)
    
    The connection is kept alive until the client disconnects.
    """
    return await sse_service.connect(book_id, request)
