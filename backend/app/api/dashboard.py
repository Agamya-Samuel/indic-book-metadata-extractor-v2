"""User dashboard: owned books, own jobs, queue position, and cancellation."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_job_for_user_or_404
from app.core.database import get_db
from app.core.media_tokens import thumbnail_url
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.book import BookListResponse, BookSearchResult
from app.schemas.dashboard import DashboardJobsResponse, DashboardSummary
from app.services import admin_service, dashboard_service
from app.services.notification_service import deliver_notification_emails
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    return DashboardSummary(**(await dashboard_service.get_summary(db, user.id)))


@router.get("/books", response_model=BookListResponse)
async def dashboard_books(
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    items_raw, total = await SearchService.list_books(
        db,
        status=status,
        page=page,
        page_size=page_size,
        owner_id=user.id,
    )

    items = [
        BookSearchResult(
            id=item["id"],
            title=item["title"],
            filename=item["filename"],
            language=item["language"],
            status=item["status"],
            total_pages=item["total_pages"],
            created_at=item["created_at"],
            metadata_fields=item["metadata_fields"],
            thumbnail_url=thumbnail_url(item["id"], 1),
            owner_id=item.get("owner_id"),
            owner_display_name=item.get("owner_display_name"),
        )
        for item in items_raw
    ]

    return BookListResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs", response_model=DashboardJobsResponse)
async def dashboard_jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardJobsResponse:
    items, total = await dashboard_service.list_jobs(
        db,
        user.id,
        status=status,
        job_type=job_type,
        page=page,
        page_size=page_size,
    )
    return DashboardJobsResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_own_job(
    background_tasks: BackgroundTasks,
    job: Job = Depends(get_job_for_user_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        cancelled, notification_id = await admin_service.cancel_job(
            db,
            job.id,
            reason="Cancelled by admin" if user.role == UserRole.ADMIN else "Cancelled by owner",
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if notification_id is not None:
        background_tasks.add_task(deliver_notification_emails, [notification_id])
    return {"id": str(cancelled.id), "status": cancelled.status}
