from __future__ import annotations

import hmac
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    decode_access_token,
)
from app.models.book import Book
from app.models.job import Job
from app.models.user import AccountStatus, User, UserRole

_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginationParams:
    """Standard ``?page=&page_size=`` dependency (1-based, capped at 100)."""
    return PaginationParams(page=page, page_size=page_size)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _extract_token(request: Request) -> tuple[str | None, bool]:
    """Return the token and whether it came from the cookie."""
    cookie_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if cookie_token:
        return cookie_token, True
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip(), False
    return None, False


def check_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


async def _user_from_token(db: AsyncSession, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        return None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        return None
    if user.email_verified_at is None:
        return None
    if int(payload.get("tv", -1)) != user.token_version:
        return None
    if payload.get("role") != user.role:
        return None
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token, from_cookie = _extract_token(request)
    if not token:
        raise _unauthorized()

    user = await _user_from_token(db, token)
    if user is None:
        raise _unauthorized("Invalid or expired session")

    if from_cookie and request.method in _MUTATION_METHODS:
        check_csrf(request)

    return user


async def require_approved_user(
    user: User = Depends(get_current_user),
) -> User:
    """Gate application routers on moderator approval.

    Allow-list check: only ``approved`` accounts pass, so any future status is
    denied by default. Pending and rejected accounts still hold a session so the
    frontend can render a status-specific holding screen; only ``/auth/*`` stays
    reachable.
    """
    if user.account_status != AccountStatus.APPROVED:
        code = "account_rejected" if user.account_status == AccountStatus.REJECTED else "account_pending"
        raise HTTPException(status_code=403, detail=code)
    return user


async def require_admin(
    user: User = Depends(require_approved_user),
) -> User:
    # require_admin composes the approval gate so a pending/rejected account can
    # never reach the admin surface, even if it carries the admin role.
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def can_view_full_book(book: Book, user: User) -> bool:
    return user.role == UserRole.ADMIN or book.owner_id == user.id


async def get_book_or_404(book_id: UUID, db: AsyncSession = Depends(get_db)) -> Book:
    """Compatibility helper for internal callers; does not authorize."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


async def get_owned_book_or_404(
    book_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Book:
    """Return a book only when the caller owns it or is an administrator."""
    book = await db.get(Book, book_id)
    if book is None or not can_view_full_book(book, user):
        # 404 rather than 403: do not confirm that another user's book exists.
        raise HTTPException(status_code=404, detail="Book not found")
    return book


async def get_job_for_user_or_404(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Job:
    """Return a job when the caller requested it, owns its book, or is an admin."""
    job = await db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if user.role == UserRole.ADMIN:
        return job
    if job.requested_by_id == user.id:
        return job
    if job.book_id is not None:
        book = await db.get(Book, job.book_id)
        if book is not None and book.owner_id == user.id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")
