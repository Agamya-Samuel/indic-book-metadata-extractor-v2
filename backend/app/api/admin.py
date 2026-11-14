"""Admin HTTP endpoints: users, library stats, book CRUD, cross-book job control."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.models.user import AccountStatus, User
from app.schemas.auth import (
    AdminPasswordResetRequest,
    AdminUserCreateRequest,
    AdminUserDetailResponse,
    AdminUserRejectRequest,
    AdminUserUpdateRequest,
    UserListResponse,
    UserResponse,
)
from app.schemas.book import (
    BookListResponse,
    BookSearchResult,
    FilterOptionsResponse,
)
from app.schemas.job import AdminJobsResponse
from app.services import admin_service, auth_service
from app.services.auth_service import AuthError
from app.services.notification_service import deliver_notification_emails
from app.services.search_service import SearchService

router = APIRouter(dependencies=[Depends(require_admin)])


def _auth_http_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


async def _get_user_or_404(db: AsyncSession, user_id: UUID) -> User:
    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=UserListResponse)
async def admin_list_users(
    query: str | None = Query(default=None),
    role: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    account_status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    users, total = await auth_service.list_users(
        db,
        query=query,
        role=role,
        is_active=is_active,
        account_status=account_status,
        page=page,
        page_size=page_size,
    )
    return UserListResponse.create(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def admin_create_user(
    body: AdminUserCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    try:
        user = await auth_service.create_user(
            db,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
            role=body.role,
            verified=True,
        )
    except AuthError as exc:
        raise _auth_http_error(exc)
    return UserResponse.model_validate(user)


# Registered before /users/{user_id} so the literal path is not captured as a
# UUID path parameter.
@router.get("/users/pending-count")
async def admin_pending_user_count(db: AsyncSession = Depends(get_db)) -> dict:
    count = await auth_service.count_users_by_status(db, AccountStatus.PENDING)
    return {"count": count}


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def admin_get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AdminUserDetailResponse:
    user = await _get_user_or_404(db, user_id)
    book_count, active_jobs = await auth_service.get_user_counts(db, user_id)
    return AdminUserDetailResponse(
        **UserResponse.model_validate(user).model_dump(),
        book_count=book_count,
        active_job_count=active_jobs,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: UUID,
    body: AdminUserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    try:
        user = await auth_service.update_user_admin(
            db,
            admin,
            target,
            display_name=body.display_name,
            role=body.role.value if body.role is not None else None,
            is_active=body.is_active,
        )
    except AuthError as exc:
        raise _auth_http_error(exc)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def admin_approve_user(
    user_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    try:
        user, notification_id = await auth_service.approve_user(db, admin, target)
    except AuthError as exc:
        raise _auth_http_error(exc)
    if notification_id is not None:
        background_tasks.add_task(deliver_notification_emails, [notification_id])
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reject", response_model=UserResponse)
async def admin_reject_user(
    user_id: UUID,
    body: AdminUserRejectRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> UserResponse:
    target = await _get_user_or_404(db, user_id)
    try:
        user = await auth_service.reject_user(db, admin, target, body.rejection_reason)
    except AuthError as exc:
        raise _auth_http_error(exc)
    return UserResponse.model_validate(user)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def admin_reset_user_password(
    user_id: UUID,
    body: AdminPasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await _get_user_or_404(db, user_id)
    await auth_service.reset_user_password_admin(db, target, body.new_password)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> None:
    target = await _get_user_or_404(db, user_id)
    try:
        await auth_service.delete_user_admin(db, admin, target)
    except AuthError as exc:
        raise _auth_http_error(exc)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.get_admin_stats(db)


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------


@router.get("/filters", response_model=FilterOptionsResponse)
async def admin_filter_options(
    db: AsyncSession = Depends(get_db),
) -> FilterOptionsResponse:
    return await SearchService.get_filter_options(db)


@router.get("/books", response_model=BookListResponse)
async def admin_list_books(
    query: str | None = Query(default=None, alias="query"),
    language: str | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    genre: str | None = Query(default=None),
    publisher: str | None = Query(default=None),
    has_metadata: bool | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> BookListResponse:
    items_raw, total = await SearchService.list_books(
        db,
        language=language,
        status=status_,
        genre=genre,
        publisher=publisher,
        page=page,
        page_size=page_size,
        owner_id=owner_id,
        has_metadata=has_metadata,
    )

    if query and query.strip():
        # When a search term is provided, switch to similarity search.
        items_raw, total = await SearchService.search_books(
            db,
            q=query.strip(),
            language=language,
            status=status_,
            genre=genre,
            publisher=publisher,
            page=page,
            page_size=page_size,
            owner_id=owner_id,
            has_metadata=has_metadata,
        )

    items = []
    for item in items_raw:
        thumb = f"/api/books/{item['id']}/pages/1/thumbnail"
        items.append(
            BookSearchResult(
                id=item["id"],
                title=item["title"],
                filename=item["filename"],
                language=item["language"],
                status=item["status"],
                total_pages=item["total_pages"],
                created_at=item["created_at"],
                metadata_fields=item["metadata_fields"],
                thumbnail_url=thumb,
                owner_id=item.get("owner_id"),
                owner_display_name=item.get("owner_display_name"),
                owner_email=item.get("owner_email"),
            )
        )

    return BookListResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_book(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await admin_service.delete_book(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")


@router.post("/books/{book_id}/reset")
async def admin_reset_book(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        book = await admin_service.reset_book(db, book_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": str(book.id), "status": book.status}


@router.post("/books/{book_id}/rerun-ocr", status_code=status.HTTP_201_CREATED)
async def admin_rerun_ocr(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    try:
        job = await admin_service.rerun_ocr(db, book_id, requested_by_id=admin.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book_id),
        "status": job.status,
    }


@router.post("/books/{book_id}/rerun-extraction", status_code=status.HTTP_201_CREATED)
async def admin_rerun_extraction(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict:
    try:
        job = await admin_service.rerun_extraction(db, book_id, requested_by_id=admin.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book_id),
        "status": job.status,
    }


# ---------------------------------------------------------------------------
# Jobs (cross-book)
# ---------------------------------------------------------------------------


@router.get("/jobs", response_model=AdminJobsResponse)
async def admin_list_jobs(
    status: str | None = Query(default=None),
    job_type: str | None = Query(default=None, alias="job_type"),
    book_id: UUID | None = Query(default=None),
    owner_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> AdminJobsResponse:
    items, total = await admin_service.list_admin_jobs(
        db,
        status=status,
        job_type=job_type,
        book_id=book_id,
        owner_id=owner_id,
        page=page,
        page_size=page_size,
    )
    return AdminJobsResponse.create(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/jobs/{job_id}/cancel")
async def admin_cancel_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        job, notification_id = await admin_service.cancel_job(db, job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if notification_id is not None:
        background_tasks.add_task(deliver_notification_emails, [notification_id])
    return {"id": str(job.id), "status": job.status}
