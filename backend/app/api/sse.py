"""
SSE (Server-Sent Events) API endpoints for real-time job updates.
"""

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_owned_book_or_404
from app.models.book import Book
from app.services.sse_service import sse_service

router = APIRouter(prefix="/sse", tags=["SSE"])


@router.get("/books/{book_id}/events")
async def stream_book_events(
    request: Request,
    book: Book = Depends(get_owned_book_or_404),
):
    """
    Stream real-time events for a book's jobs.

    Clients connect to this endpoint to receive SSE events when:
    - A job starts (job_started)
    - A job makes progress (job_progress)
    - A job completes (job_complete)
    - A job fails (job_failed)

    The connection is kept alive until the client disconnects.
    """
    return await sse_service.connect(str(book.id), request)
