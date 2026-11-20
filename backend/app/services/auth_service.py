"""User account lifecycle, credentials, and session tokens."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    password_needs_rehash,
    utcnow,
    verify_password,
)
from app.models.book import Book
from app.models.job import Job, JobStatus
from app.models.user import (
    AccountStatus,
    EmailToken,
    EmailTokenPurpose,
    RefreshToken,
    User,
    UserRole,
)
from app.services import audit_service, notification_service, smtp_service
from app.services.audit_service import AuditAction, AuditContext
from app.services.email_service import (
    send_email_change_email,
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """An authentication or account-management failure with an HTTP mapping."""

    def __init__(
        self,
        detail: str,
        status_code: int = 400,
        code: str = "auth_error",
        *,
        user_id: UUID | None = None,
    ):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.code = code
        # Set when the failure is attributable to a known account, so a route
        # can record the event against that account (e.g. token replay).
        self.user_id = user_id


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_expired(value: datetime) -> bool:
    return _as_aware(value) <= utcnow()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def create_user(
    db: AsyncSession,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str = UserRole.USER,
    verified: bool = False,
    account_status: str = AccountStatus.APPROVED,
) -> User:
    normalized = normalize_email(email)
    if await get_user_by_email(db, normalized) is not None:
        raise AuthError("An account with this email already exists", 409, "email_taken")

    user = User(
        email=normalized,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        account_status=account_status,
        email_verified_at=utcnow() if verified else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_email_token(
    db: AsyncSession,
    user: User,
    purpose: EmailTokenPurpose,
    *,
    pending_email: str | None = None,
) -> str:
    """Invalidate older links of the same purpose and return a fresh token."""
    await db.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )

    raw = generate_opaque_token()
    if purpose in (EmailTokenPurpose.VERIFY_EMAIL, EmailTokenPurpose.VERIFY_NEW_EMAIL):
        expires = utcnow() + timedelta(hours=settings.email_verification_expire_hours)
    else:
        expires = utcnow() + timedelta(minutes=settings.password_reset_expire_minutes)

    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_opaque_token(raw),
            expires_at=expires,
            pending_email=pending_email,
        )
    )
    await db.commit()
    return raw


async def register_user(db: AsyncSession, *, email: str, display_name: str, password: str) -> tuple[User, list[UUID]]:
    """Create a pending account and alert the admins who must approve it.

    Returns the user and the notification ids created for admins, so the route
    can deliver their emails after responding.
    """
    user = await create_user(
        db,
        email=email,
        display_name=display_name,
        password=password,
        role=UserRole.USER,
        verified=False,
        account_status=(AccountStatus.PENDING if settings.registration_requires_approval else AccountStatus.APPROVED),
    )
    token = await create_email_token(db, user, EmailTokenPurpose.VERIFY_EMAIL)
    notification_ids: list[UUID] = []
    if user.account_status == AccountStatus.PENDING:
        notification_ids = await notification_service.notify_admins_registration(db, user)
        await db.commit()
    config = await smtp_service.get_effective_config(db)
    await send_verification_email(user, token, config=config)
    return user, notification_ids


async def resend_verification(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is None or user.email_verified_at is not None:
        # Do not disclose whether the address is registered.
        return
    token = await create_email_token(db, user, EmailTokenPurpose.VERIFY_EMAIL)
    config = await smtp_service.get_effective_config(db)
    await send_verification_email(user, token, config=config)


async def verify_email(db: AsyncSession, raw_token: str) -> User:
    token = await _consume_email_token(db, raw_token, EmailTokenPurpose.VERIFY_EMAIL)
    user = await db.get(User, token.user_id)
    if user is None:
        raise AuthError("This link is invalid", 400, "invalid_token")
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
        await db.commit()
        await db.refresh(user)
    return user


async def _consume_email_token(db: AsyncSession, raw_token: str, purpose: EmailTokenPurpose) -> EmailToken:
    result = await db.execute(
        select(EmailToken).where(
            EmailToken.token_hash == hash_opaque_token(raw_token),
            EmailToken.purpose == purpose,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise AuthError("This link is invalid", 400, "invalid_token")
    if token.used_at is not None:
        raise AuthError("This link has already been used", 400, "token_used")
    if _is_expired(token.expires_at):
        raise AuthError("This link has expired", 400, "token_expired")
    token.used_at = utcnow()
    await db.flush()
    return token


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", 401, "invalid_credentials")
    if not user.is_active:
        raise AuthError("This account has been deactivated", 403, "account_inactive")
    if user.email_verified_at is None:
        raise AuthError(
            "Please verify your email address before signing in",
            403,
            "email_unverified",
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    await db.commit()
    await db.refresh(user)
    return user


def issue_access_token(user: User) -> str:
    return create_access_token(
        user_id=str(user.id),
        role=user.role,
        token_version=user.token_version,
    )


async def create_refresh_token(
    db: AsyncSession,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    raw = generate_opaque_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_expire_days),
            user_agent=(user_agent or "")[:500] or None,
            ip_address=(ip_address or "")[:45] or None,
        )
    )
    await db.commit()
    return raw


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, str]:
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_opaque_token(raw_token)))
    token = result.scalar_one_or_none()
    if token is None:
        raise AuthError("Invalid session", 401, "invalid_refresh")

    if token.revoked_at is not None:
        # A revoked token was replayed. Treat the whole session family as
        # compromised and invalidate every refresh token for the user.
        await revoke_all_sessions(db, token.user_id)
        raise AuthError("Session revoked", 401, "refresh_reused", user_id=token.user_id)

    if _is_expired(token.expires_at):
        token.revoked_at = utcnow()
        await db.commit()
        raise AuthError("Session expired", 401, "refresh_expired")

    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        token.revoked_at = utcnow()
        await db.commit()
        raise AuthError("Account is not active", 403, "account_inactive")

    token.revoked_at = utcnow()
    await db.flush()
    new_raw = await create_refresh_token(db, user, user_agent=user_agent, ip_address=ip_address)
    return user, new_raw


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_opaque_token(raw_token),
            RefreshToken.revoked_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    if token is not None:
        token.revoked_at = utcnow()
        await db.commit()


async def revoke_all_sessions(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    user = await db.get(User, user_id)
    if user is not None:
        user.token_version += 1
    await db.commit()


async def request_password_reset(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        return
    token = await create_email_token(db, user, EmailTokenPurpose.RESET_PASSWORD)
    config = await smtp_service.get_effective_config(db)
    await send_password_reset_email(user, token, config=config)


async def _invalidate_password_reset_tokens(db: AsyncSession, user_id: UUID) -> None:
    """Burn every outstanding reset link after the password changes."""
    await db.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user_id,
            EmailToken.purpose == EmailTokenPurpose.RESET_PASSWORD,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )


async def reset_password(db: AsyncSession, raw_token: str, new_password: str) -> User:
    token = await _consume_email_token(db, raw_token, EmailTokenPurpose.RESET_PASSWORD)
    user = await db.get(User, token.user_id)
    if user is None:
        raise AuthError("This link is invalid", 400, "invalid_token")
    user.password_hash = hash_password(new_password)
    await _invalidate_password_reset_tokens(db, user.id)
    await db.commit()
    await revoke_all_sessions(db, user.id)
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Current password is incorrect", 400, "invalid_password")
    user.password_hash = hash_password(new_password)
    await _invalidate_password_reset_tokens(db, user.id)
    await db.commit()
    await revoke_all_sessions(db, user.id)


async def update_profile(db: AsyncSession, user: User, *, display_name: str) -> User:
    user.display_name = display_name.strip()
    await db.commit()
    await db.refresh(user)
    return user


async def request_email_change(db: AsyncSession, user: User, new_email: str, current_password: str) -> None:
    """Begin an email change: verify the new address before switching to it.

    The current password is required to authorize the change. A verification
    link goes to the *new* address; the current address stays active until the
    link is confirmed.
    """
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Current password is incorrect", 400, "invalid_password")

    normalized = normalize_email(new_email)
    if normalized == user.email:
        raise AuthError("This is already your email address", 400, "email_unchanged")
    if await get_user_by_email(db, normalized) is not None:
        raise AuthError("An account with this email already exists", 409, "email_taken")

    token = await create_email_token(db, user, EmailTokenPurpose.VERIFY_NEW_EMAIL, pending_email=normalized)
    config = await smtp_service.get_effective_config(db)
    sent = await send_email_change_email(user, normalized, token, config=config)
    if not sent:
        raise AuthError(
            "Could not send a verification email to the new address. Please try again later.",
            502,
            "email_send_failed",
        )


async def confirm_email_change(db: AsyncSession, raw_token: str) -> tuple[User, str]:
    token = await _consume_email_token(db, raw_token, EmailTokenPurpose.VERIFY_NEW_EMAIL)
    user = await db.get(User, token.user_id)
    if user is None:
        raise AuthError("This link is invalid", 400, "invalid_token")

    new_email = (token.pending_email or "").strip().lower()
    if not new_email:
        raise AuthError("This link is invalid", 400, "invalid_token")

    existing = await get_user_by_email(db, new_email)
    if existing is not None and existing.id != user.id:
        raise AuthError("An account with this email already exists", 409, "email_taken")

    previous_email = user.email
    user.email = new_email
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    await db.commit()
    await db.refresh(user)
    # Email is a credential: force re-authentication everywhere after a change.
    await revoke_all_sessions(db, user.id)
    await db.refresh(user)
    return user, previous_email


# ---------------------------------------------------------------------------
# Admin user management
# ---------------------------------------------------------------------------


async def _count_active_admins(db: AsyncSession) -> int:
    return int(
        await db.scalar(select(func.count(User.id)).where(User.role == UserRole.ADMIN, User.is_active.is_(True))) or 0
    )


async def list_users(
    db: AsyncSession,
    *,
    query: str | None,
    role: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
    account_status: str | None = None,
) -> tuple[list[User], int]:
    base = select(User)
    if query and query.strip():
        like = f"%{query.strip().lower()}%"
        base = base.where(func.lower(User.email).like(like) | func.lower(User.display_name).like(like))
    if role:
        base = base.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active.is_(is_active))
    if account_status:
        base = base.where(User.account_status == account_status)

    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    result = await db.execute(base.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total


async def count_users_by_status(db: AsyncSession, account_status: str) -> int:
    return int(await db.scalar(select(func.count(User.id)).where(User.account_status == account_status)) or 0)


async def get_user_counts(db: AsyncSession, user_id: UUID) -> tuple[int, int]:
    book_count = int(await db.scalar(select(func.count(Book.id)).where(Book.owner_id == user_id)) or 0)
    active_jobs = int(
        await db.scalar(
            select(func.count(Job.id)).where(
                Job.requested_by_id == user_id,
                Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
        )
        or 0
    )
    return book_count, active_jobs


def _ensure_admin_target_preserved(
    acting_admin: User,
    target: User,
    *,
    new_role: str | None,
    new_active: bool | None,
    new_account_status: str | None = None,
    deleting: bool = False,
) -> None:
    if target.id == acting_admin.id and (
        deleting
        or new_role == UserRole.USER
        or new_active is False
        or (new_account_status is not None and new_account_status != AccountStatus.APPROVED)
    ):
        raise AuthError(
            "You cannot demote, reject, or deactivate your own admin account",
            400,
            "self_admin_protection",
        )


def _apply_account_status(
    acting_admin: User | None,
    target: User,
    status: str,
    *,
    reason: str | None = None,
) -> None:
    target.account_status = status
    target.status_reviewed_at = utcnow()
    target.status_reviewed_by_id = acting_admin.id if acting_admin else None
    target.rejection_reason = reason if status == AccountStatus.REJECTED else None


async def approve_user(db: AsyncSession, admin: User, target: User) -> tuple[User, UUID | None]:
    """Approve a pending account and tell its owner.

    Returns the user and the notification id (None if one already existed), so
    the route can deliver the alert email after responding.
    """
    _ensure_admin_target_preserved(
        admin, target, new_role=None, new_active=None, new_account_status=AccountStatus.APPROVED
    )
    _apply_account_status(admin, target, AccountStatus.APPROVED)
    await db.commit()
    await db.refresh(target)
    notification_id = await notification_service.notify_account_approved(db, target)
    await db.commit()
    return target, notification_id


async def reject_user(db: AsyncSession, admin: User, target: User, reason: str | None = None) -> User:
    _ensure_admin_target_preserved(
        admin, target, new_role=None, new_active=None, new_account_status=AccountStatus.REJECTED
    )
    _apply_account_status(admin, target, AccountStatus.REJECTED, reason=reason)
    await db.commit()
    await db.refresh(target)
    # Revoke other sessions so a rejected user cannot keep using the app; they
    # can still log back in to the "registration not approved" holding screen.
    await revoke_all_sessions(db, target.id)
    await db.refresh(target)
    return target


async def update_user_admin(
    db: AsyncSession,
    acting_admin: User,
    target: User,
    *,
    display_name: str | None,
    role: str | None,
    is_active: bool | None,
    audit: AuditContext | None = None,
) -> User:
    _ensure_admin_target_preserved(
        acting_admin,
        target,
        new_role=role,
        new_active=is_active,
    )

    demoting_or_disabling = (
        target.role == UserRole.ADMIN
        and target.is_active
        and ((role is not None and role != UserRole.ADMIN) or is_active is False)
    )
    if demoting_or_disabling and await _count_active_admins(db) <= 1:
        raise AuthError(
            "At least one active administrator must remain",
            400,
            "last_admin_protection",
        )

    before = {
        "display_name": target.display_name,
        "role": target.role,
        "is_active": target.is_active,
    }
    if display_name is not None:
        target.display_name = display_name.strip()
    if role is not None:
        target.role = role
    if is_active is not None:
        target.is_active = is_active

    after = {
        "display_name": target.display_name,
        "role": target.role,
        "is_active": target.is_active,
    }
    if audit is not None:
        changed_before, changed_after = audit_service.change_snapshots(before, after)
        if changed_before:
            # Critical: staged in this transaction so a failed insert blocks
            # the role/permission change instead of leaving it unaudited.
            await audit_service.record(
                db,
                action=AuditAction.USER_UPDATED,
                ctx=audit,
                description=f"Updated account {target.email}",
                resource_type="user",
                resource_id=target.id,
                resource_label=target.email,
                subject_user_id=target.id,
                before=changed_before,
                after=changed_after,
            )

    await db.commit()
    await db.refresh(target)

    if role is not None or is_active is False:
        await revoke_all_sessions(db, target.id)
    return target


async def reset_user_password_admin(db: AsyncSession, target: User, new_password: str) -> None:
    target.password_hash = hash_password(new_password)
    await db.commit()
    await revoke_all_sessions(db, target.id)


async def delete_user_admin(
    db: AsyncSession,
    acting_admin: User,
    target: User,
    *,
    audit: AuditContext | None = None,
) -> None:
    _ensure_admin_target_preserved(acting_admin, target, new_role=None, new_active=None, deleting=True)

    if target.role == UserRole.ADMIN and target.is_active:
        if await _count_active_admins(db) <= 1:
            raise AuthError(
                "At least one active administrator must remain",
                400,
                "last_admin_protection",
            )

    book_count = int(await db.scalar(select(func.count(Book.id)).where(Book.owner_id == target.id)) or 0)
    if book_count:
        raise AuthError(
            f"This user owns {book_count} book(s). Delete or transfer those books first.",
            409,
            "user_has_books",
        )

    if audit is not None:
        # Critical: staged before the delete so the audit row and the deletion
        # commit together. There is no FK, so the row survives the delete.
        await audit_service.record(
            db,
            action=AuditAction.USER_DELETED,
            ctx=audit,
            description=f"Deleted account {target.email}",
            resource_type="user",
            resource_id=target.id,
            resource_label=target.email,
            subject_user_id=target.id,
            before={
                "email": target.email,
                "display_name": target.display_name,
                "role": target.role,
                "account_status": target.account_status,
                "is_active": target.is_active,
            },
        )

    await db.delete(target)
    await db.commit()


async def delete_user_sessions(db: AsyncSession, user_id: UUID) -> None:
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()
