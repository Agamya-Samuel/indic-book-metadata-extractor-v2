"""Central audit logging.

Every entry is written by the backend, never by the client. The table is
append-only: a database trigger rejects ``UPDATE``, ``DELETE`` and ``TRUNCATE``,
and no API route exposes a mutation.

Two write paths:

* :func:`record` adds the row to the caller's transaction. Use it where the
  route (or service) owns the commit, so the action and its audit row commit or
  roll back together. **Critical actions must use this path** — a failed audit
  insert then fails the action instead of leaving it unaudited.
* :func:`record_isolated` writes and commits immediately on the caller's
  session, after the action has already committed. Auth flows and workers
  commit inside their services, so they cannot share the transaction. A failure
  is reported loudly through the application log rather than breaking the
  user's request, but it is never silently discarded.

Secrets never reach a row: :func:`sanitize` redacts credential-shaped keys
recursively and truncates oversized values.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import client_ip, get_request_id
from app.models.audit_log import AuditLog, AuditResult
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event catalogue
# ---------------------------------------------------------------------------


class AuditActorType(StrEnum):
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    ANONYMOUS = "anonymous"


class AuditCategory(StrEnum):
    AUTH = "auth"
    USER = "user"
    BOOK = "book"
    PROCESSING = "processing"
    JOB = "job"
    EXPORT = "export"
    CONFIG = "config"
    SYSTEM = "system"


class AuditAction(StrEnum):
    # Authentication and self-service account changes.
    AUTH_REGISTER = "auth.register"
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REFRESH_REUSE = "auth.refresh_reuse_detected"
    AUTH_EMAIL_VERIFIED = "auth.email_verified"
    AUTH_VERIFICATION_RESENT = "auth.verification_resent"
    AUTH_PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    AUTH_PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    AUTH_PASSWORD_CHANGED = "auth.password_changed"
    AUTH_EMAIL_CHANGE_REQUESTED = "auth.email_change_requested"
    AUTH_EMAIL_CHANGE_CONFIRMED = "auth.email_change_confirmed"
    AUTH_PROFILE_UPDATED = "auth.profile_updated"

    # Administrator user management.
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_APPROVED = "user.approved"
    USER_REJECTED = "user.rejected"
    USER_PASSWORD_RESET = "user.password_reset_admin"
    USER_DELETED = "user.deleted"

    # Books.
    BOOK_UPLOADED = "book.uploaded"
    BOOK_DELETED = "book.deleted"
    BOOK_LANGUAGE_CHANGED = "book.language_changed"
    BOOK_RESET = "book.reset"
    BOOK_RERUN_OCR = "book.rerun_ocr"
    BOOK_RERUN_EXTRACTION = "book.rerun_extraction"

    # Processing pipeline.
    PAGES_SELECTED = "pages.selected"
    PREPROCESSING_UPDATED = "preprocessing.updated"
    PREPROCESSING_APPLIED = "preprocessing.applied"
    OCR_REQUESTED = "ocr.requested"
    OCR_CORRECTION_SAVED = "ocr.correction_saved"
    OCR_PARTIAL_FAILURE = "ocr.partial_failure"
    EXTRACTION_REQUESTED = "extraction.requested"
    EXTRACTION_RETRIED = "extraction.retried"
    METADATA_UPDATED = "metadata.updated"
    METADATA_REVIEW_COMPLETED = "metadata.review_completed"

    # Jobs.
    JOB_CANCELLED = "job.cancelled"
    JOB_RETRIED = "job.retried"
    JOB_FAILED = "job.failed"
    JOB_REAPED = "job.reaped"

    # Exports and bulk operations.
    EXPORT_METADATA = "export.metadata"
    EXPORT_WIKIBASE = "export.wikibase"
    BULK_IMPORT = "bulk.import"

    # Runtime configuration.
    CONFIG_SMTP_UPDATED = "config.smtp_updated"
    CONFIG_SMTP_TESTED = "config.smtp_tested"
    CONFIG_MAINTENANCE_UPDATED = "config.maintenance_updated"

    # System and meta.
    SYSTEM_WATCHDOG_ALERT = "system.watchdog_alert"
    AUDIT_VIEWED = "audit.viewed"


@dataclass(frozen=True)
class ActionSpec:
    category: AuditCategory
    label: str


def _spec(category: AuditCategory, label: str) -> ActionSpec:
    return ActionSpec(category=category, label=label)


ACTION_SPECS: dict[AuditAction, ActionSpec] = {
    AuditAction.AUTH_REGISTER: _spec(AuditCategory.AUTH, "Account registered"),
    AuditAction.AUTH_LOGIN: _spec(AuditCategory.AUTH, "Signed in"),
    AuditAction.AUTH_LOGIN_FAILED: _spec(AuditCategory.AUTH, "Sign-in failed"),
    AuditAction.AUTH_LOGOUT: _spec(AuditCategory.AUTH, "Signed out"),
    AuditAction.AUTH_REFRESH_REUSE: _spec(AuditCategory.AUTH, "Revoked session replayed"),
    AuditAction.AUTH_EMAIL_VERIFIED: _spec(AuditCategory.AUTH, "Email verified"),
    AuditAction.AUTH_VERIFICATION_RESENT: _spec(AuditCategory.AUTH, "Verification email resent"),
    AuditAction.AUTH_PASSWORD_RESET_REQUESTED: _spec(AuditCategory.AUTH, "Password reset requested"),
    AuditAction.AUTH_PASSWORD_RESET_COMPLETED: _spec(AuditCategory.AUTH, "Password reset completed"),
    AuditAction.AUTH_PASSWORD_CHANGED: _spec(AuditCategory.AUTH, "Password changed"),
    AuditAction.AUTH_EMAIL_CHANGE_REQUESTED: _spec(AuditCategory.AUTH, "Email change requested"),
    AuditAction.AUTH_EMAIL_CHANGE_CONFIRMED: _spec(AuditCategory.AUTH, "Email address changed"),
    AuditAction.AUTH_PROFILE_UPDATED: _spec(AuditCategory.AUTH, "Profile updated"),
    AuditAction.USER_CREATED: _spec(AuditCategory.USER, "User created"),
    AuditAction.USER_UPDATED: _spec(AuditCategory.USER, "User updated"),
    AuditAction.USER_APPROVED: _spec(AuditCategory.USER, "Account approved"),
    AuditAction.USER_REJECTED: _spec(AuditCategory.USER, "Account rejected"),
    AuditAction.USER_PASSWORD_RESET: _spec(AuditCategory.USER, "Password reset by admin"),
    AuditAction.USER_DELETED: _spec(AuditCategory.USER, "User deleted"),
    AuditAction.BOOK_UPLOADED: _spec(AuditCategory.BOOK, "Book uploaded"),
    AuditAction.BOOK_DELETED: _spec(AuditCategory.BOOK, "Book deleted"),
    AuditAction.BOOK_LANGUAGE_CHANGED: _spec(AuditCategory.BOOK, "Book language changed"),
    AuditAction.BOOK_RESET: _spec(AuditCategory.BOOK, "Book reset"),
    AuditAction.BOOK_RERUN_OCR: _spec(AuditCategory.BOOK, "OCR re-run"),
    AuditAction.BOOK_RERUN_EXTRACTION: _spec(AuditCategory.BOOK, "Extraction re-run"),
    AuditAction.PAGES_SELECTED: _spec(AuditCategory.PROCESSING, "Pages selected"),
    AuditAction.PREPROCESSING_UPDATED: _spec(AuditCategory.PROCESSING, "Page preprocessing updated"),
    AuditAction.PREPROCESSING_APPLIED: _spec(AuditCategory.PROCESSING, "Preprocessing applied to book"),
    AuditAction.OCR_REQUESTED: _spec(AuditCategory.PROCESSING, "OCR started"),
    AuditAction.OCR_CORRECTION_SAVED: _spec(AuditCategory.PROCESSING, "OCR correction saved"),
    AuditAction.OCR_PARTIAL_FAILURE: _spec(AuditCategory.PROCESSING, "OCR completed with failures"),
    AuditAction.EXTRACTION_REQUESTED: _spec(AuditCategory.PROCESSING, "Metadata extraction started"),
    AuditAction.EXTRACTION_RETRIED: _spec(AuditCategory.PROCESSING, "Metadata extraction retried"),
    AuditAction.METADATA_UPDATED: _spec(AuditCategory.PROCESSING, "Metadata updated"),
    AuditAction.METADATA_REVIEW_COMPLETED: _spec(AuditCategory.PROCESSING, "Review completed"),
    AuditAction.JOB_CANCELLED: _spec(AuditCategory.JOB, "Job cancelled"),
    AuditAction.JOB_RETRIED: _spec(AuditCategory.JOB, "Job retried"),
    AuditAction.JOB_FAILED: _spec(AuditCategory.JOB, "Job failed"),
    AuditAction.JOB_REAPED: _spec(AuditCategory.JOB, "Stale job reaped"),
    AuditAction.EXPORT_METADATA: _spec(AuditCategory.EXPORT, "Metadata exported"),
    AuditAction.EXPORT_WIKIBASE: _spec(AuditCategory.EXPORT, "Wikibase export"),
    AuditAction.BULK_IMPORT: _spec(AuditCategory.EXPORT, "Metadata imported"),
    AuditAction.CONFIG_SMTP_UPDATED: _spec(AuditCategory.CONFIG, "SMTP configuration updated"),
    AuditAction.CONFIG_SMTP_TESTED: _spec(AuditCategory.CONFIG, "SMTP test run"),
    AuditAction.CONFIG_MAINTENANCE_UPDATED: _spec(AuditCategory.CONFIG, "Maintenance mode updated"),
    AuditAction.SYSTEM_WATCHDOG_ALERT: _spec(AuditCategory.SYSTEM, "Host watchdog alert"),
    AuditAction.AUDIT_VIEWED: _spec(AuditCategory.SYSTEM, "Audit log viewed"),
}

# These must be recorded inside the action's transaction. If the insert fails,
# the action fails too: an unaudited role change or config edit is worse than a
# retry.
CRITICAL_ACTIONS: frozenset[AuditAction] = frozenset(
    {
        AuditAction.USER_DELETED,
        AuditAction.USER_UPDATED,
        AuditAction.CONFIG_SMTP_UPDATED,
        AuditAction.CONFIG_MAINTENANCE_UPDATED,
    }
)


def category_for(action: AuditAction) -> AuditCategory:
    return ACTION_SPECS[action].category


# ---------------------------------------------------------------------------
# Actor context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditContext:
    """Who is acting, from where, and on which request."""

    actor_type: str = AuditActorType.SYSTEM
    actor_id: uuid.UUID | None = None
    actor_role: str | None = None
    actor_email: str | None = None
    actor_display_name: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


def context_from_request(request: Request, user: User | None) -> AuditContext:
    """Build a context from the live request, or an anonymous one."""
    if user is None:
        actor_type = AuditActorType.ANONYMOUS
    elif user.role == UserRole.ADMIN:
        actor_type = AuditActorType.ADMIN
    else:
        actor_type = AuditActorType.USER

    user_agent = (request.headers.get("user-agent") or "")[:500] or None
    return AuditContext(
        actor_type=actor_type,
        actor_id=user.id if user is not None else None,
        actor_role=user.role if user is not None else None,
        actor_email=user.email if user is not None else None,
        actor_display_name=user.display_name if user is not None else None,
        ip_address=client_ip(request),
        user_agent=user_agent,
        request_id=get_request_id(),
    )


def system_context(*, label: str = "worker") -> AuditContext:
    return AuditContext(actor_type=AuditActorType.SYSTEM, actor_display_name=label)


def anonymous_context(*, request: Request | None = None) -> AuditContext:
    if request is None:
        return AuditContext(actor_type=AuditActorType.ANONYMOUS)
    return context_from_request(request, None)


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------

_REDACTED = "[redacted]"
_MAX_STRING = 2000
_MAX_ITEMS = 50
_MAX_DEPTH = 5

# Substrings that mark a credential. ``password_set`` is an intentional
# boolean we do want to keep; ``token_version`` is a counter, not a secret.
_SENSITIVE_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "csrf",
    "credential",
    "private_key",
)
_SENSITIVE_ALLOWED = frozenset({"password_set", "password_changed", "token_version"})


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in _SENSITIVE_ALLOWED:
        return False
    return any(part in normalized for part in _SENSITIVE_PARTS)


def sanitize(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    """Return ``(safe_value, truncated)`` with credentials removed."""
    if depth > _MAX_DEPTH:
        return "[truncated]", True

    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        truncated = False
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                truncated = True
                break
            name = str(key)
            if _is_sensitive_key(name):
                cleaned[name] = _REDACTED
                continue
            safe, was_truncated = sanitize(item, depth=depth + 1)
            cleaned[name] = safe
            truncated = truncated or was_truncated
        return cleaned, truncated

    if isinstance(value, (list, tuple, set, frozenset)):
        items: list[Any] = []
        truncated = False
        for index, item in enumerate(value):
            if index >= _MAX_ITEMS:
                truncated = True
                break
            safe, was_truncated = sanitize(item, depth=depth + 1)
            items.append(safe)
            truncated = truncated or was_truncated
        return items, truncated

    if isinstance(value, str):
        if len(value) > _MAX_STRING:
            return f"{value[:_MAX_STRING]}…", True
        return value, False

    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value), False

    if isinstance(value, (bool, int, float)) or value is None:
        return value, False

    text = str(value)
    if len(text) > _MAX_STRING:
        return f"{text[:_MAX_STRING]}…", True
    return text, False


def diff(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    fields: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Only the fields that actually changed, as ``{field: {from, to}}``."""
    keys = list(fields) if fields is not None else list(dict.fromkeys([*before, *after]))
    changes: dict[str, dict[str, Any]] = {}
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes[key] = {"from": old, "to": new}
    return changes


def change_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    fields: Iterable[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(before, after)`` limited to the keys that changed.

    Storing only the changed keys keeps a 49-field metadata save readable and
    bounded. Returns two empty dicts when nothing changed.
    """
    changes = diff(before, after, fields=fields)
    return (
        {key: value["from"] for key, value in changes.items()},
        {key: value["to"] for key, value in changes.items()},
    )


# ---------------------------------------------------------------------------
# Row construction and writing
# ---------------------------------------------------------------------------


def _resource_id(value: str | uuid.UUID | int | None) -> str | None:
    if value is None:
        return None
    return str(value)[:64]


def _build_row(
    *,
    action: AuditAction,
    ctx: AuditContext,
    description: str,
    resource_type: str | None,
    resource_id: str | uuid.UUID | int | None,
    resource_label: str | None,
    subject_user_id: uuid.UUID | None,
    result: str,
    error_message: str | None,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any] | None,
    details: Mapping[str, Any] | None,
) -> AuditLog:
    truncated = False

    safe_before, cut = sanitize(dict(before)) if before is not None else (None, False)
    truncated = truncated or cut
    safe_after, cut = sanitize(dict(after)) if after is not None else (None, False)
    truncated = truncated or cut
    safe_details, cut = sanitize(dict(details)) if details is not None else (None, False)
    truncated = truncated or cut

    return AuditLog(
        actor_type=ctx.actor_type,
        actor_user_id=ctx.actor_id,
        actor_role=ctx.actor_role,
        actor_email=ctx.actor_email,
        actor_display_name=ctx.actor_display_name,
        action=action.value,
        category=category_for(action).value,
        description=description[:1000],
        resource_type=resource_type,
        resource_id=_resource_id(resource_id),
        resource_label=(resource_label or None) and resource_label[:500],
        subject_user_id=subject_user_id,
        result=result,
        error_message=(error_message or None) and error_message[:1000],
        # Client-controlled headers reach these fixed-width columns; bound them
        # here so an oversized X-Request-ID / CF-Connecting-IP can never fail
        # the INSERT and take the audited action down with it.
        ip_address=(ctx.ip_address or "")[:45] or None,
        user_agent=ctx.user_agent,
        request_id=(ctx.request_id or "")[:64] or None,
        before=safe_before,
        after=safe_after,
        details=safe_details,
        truncated=truncated,
    )


def _log_failure(
    *,
    action: AuditAction,
    ctx: AuditContext,
    description: str,
    resource_type: str | None,
    resource_id: str | uuid.UUID | int | None,
    result: str,
    details: Mapping[str, Any] | None,
    error: Exception,
) -> None:
    """Fallback so a failed insert is recoverable from the application log."""
    safe_details, _ = sanitize(dict(details)) if details is not None else (None, False)
    logger.error(
        "audit_write_failed action=%s actor_type=%s actor_id=%s resource=%s:%s "
        "result=%s description=%s details=%r error=%s",
        action.value,
        ctx.actor_type,
        ctx.actor_id,
        resource_type,
        _resource_id(resource_id),
        result,
        description[:300],
        safe_details,
        error,
        exc_info=True,
    )


async def record(
    db: AsyncSession,
    *,
    action: AuditAction,
    ctx: AuditContext,
    description: str,
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | int | None = None,
    resource_label: str | None = None,
    subject_user_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    error_message: str | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
) -> AuditLog:
    """Stage an audit row in the caller's transaction (caller commits)."""
    row = _build_row(
        action=action,
        ctx=ctx,
        description=description,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label,
        subject_user_id=subject_user_id,
        result=result,
        error_message=error_message,
        before=before,
        after=after,
        details=details,
    )
    db.add(row)
    return row


async def record_isolated(
    db: AsyncSession,
    *,
    action: AuditAction,
    ctx: AuditContext,
    description: str,
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | int | None = None,
    resource_label: str | None = None,
    subject_user_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    error_message: str | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
) -> AuditLog | None:
    """Write and commit immediately; never raise.

    Call only after the action's own commit. A critical action must use
    :func:`record` instead, so an audit failure blocks the action.
    """
    if action in CRITICAL_ACTIONS:
        raise RuntimeError(f"{action.value} must be recorded in the action's transaction")

    try:
        row = _build_row(
            action=action,
            ctx=ctx,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_label=resource_label,
            subject_user_id=subject_user_id,
            result=result,
            error_message=error_message,
            before=before,
            after=after,
            details=details,
        )
        db.add(row)
        await db.commit()
        return row
    except Exception as exc:  # noqa: BLE001 — logging must not break the request
        _log_failure(
            action=action,
            ctx=ctx,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            details=details,
            error=exc,
        )
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            logger.debug("Could not roll back after a failed audit insert", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# System-event writes (workers, background loops)
# ---------------------------------------------------------------------------


def _run_coroutine_sync(coro):
    """Run ``coro`` from sync code, whatever loop state the caller is in.

    * No loop running (Celery task body): use the worker's persistent loop via
      :func:`app.tasks.async_utils.run_async`.
    * A loop already running in this thread (signal handler, FastAPI loop):
      run on a fresh thread with a fresh loop so we never deadlock against the
      caller's loop.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        from app.tasks.async_utils import run_async

        return run_async(coro)

    import concurrent.futures

    def _runner():
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def record_system(
    *,
    action: AuditAction,
    description: str,
    label: str = "worker",
    resource_type: str | None = None,
    resource_id: str | uuid.UUID | int | None = None,
    resource_label: str | None = None,
    subject_user_id: uuid.UUID | None = None,
    result: str = AuditResult.SUCCESS,
    error_message: str | None = None,
    before: Mapping[str, Any] | None = None,
    after: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    session_factory=None,
) -> AuditLog | None:
    """Write a system-originated audit row from synchronous code.

    Celery signal handlers and background loops have no request session, so
    this opens a fresh one (``async_session_factory`` unless ``session_factory``
    is injected) and commits immediately. It never raises: a failure is logged
    loudly through the application log and ``None`` is returned.
    """
    factory = session_factory
    if factory is None:
        from app.core.database import async_session_factory as factory

    ctx = system_context(label=label)

    async def _write() -> AuditLog:
        async with factory() as db:
            row = _build_row(
                action=action,
                ctx=ctx,
                description=description,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_label=resource_label,
                subject_user_id=subject_user_id,
                result=result,
                error_message=error_message,
                before=before,
                after=after,
                details=details,
            )
            db.add(row)
            await db.commit()
            return row

    try:
        return _run_coroutine_sync(_write())
    except Exception as exc:  # noqa: BLE001 — never break the worker
        _log_failure(
            action=action,
            ctx=ctx,
            description=description,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            details=details,
            error=exc,
        )
        return None
