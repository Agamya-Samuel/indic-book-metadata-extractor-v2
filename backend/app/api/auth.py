"""Authentication endpoints: registration, login, sessions, and passwords."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_csrf, get_current_user, get_optional_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_COOKIE,
    CSRF_COOKIE,
    REFRESH_TOKEN_COOKIE,
    generate_opaque_token,
)
from app.models.user import User
from app.schemas.auth import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    UserResponse,
    VerifyEmailRequest,
    VerifyNewEmailRequest,
)
from app.services import audit_service, auth_service
from app.services.audit_service import AuditAction, AuditResult
from app.services.auth_service import AuthError
from app.services.notification_service import deliver_notification_emails

router = APIRouter()


def _http_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    common = {
        "path": "/",
        "secure": settings.cookie_secure,
        "samesite": "lax",
    }
    if settings.cookie_domain:
        common["domain"] = settings.cookie_domain

    response.set_cookie(
        ACCESS_TOKEN_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        **common,
    )
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        **common,
    )
    # Readable by the frontend so it can echo it in the X-CSRF-Token header.
    response.set_cookie(
        CSRF_COOKIE,
        generate_opaque_token(),
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=False,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name,
            path="/",
            domain=settings.cookie_domain or None,
            secure=settings.cookie_secure,
            samesite="lax",
        )


async def _start_session(
    db: AsyncSession,
    user: User,
    response: Response,
    request: Request,
) -> UserResponse:
    refresh = await auth_service.create_refresh_token(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    access = auth_service.issue_access_token(user)
    _set_auth_cookies(response, access_token=access, refresh_token=refresh)
    return UserResponse.model_validate(user)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        user, notification_ids = await auth_service.register_user(
            db,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
        )
    except AuthError as exc:
        raise _http_error(exc)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_REGISTER,
        ctx=audit_service.context_from_request(request, user),
        description=f"Registered account {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        details={"account_status": user.account_status, "role": user.role},
    )
    if notification_ids:
        background_tasks.add_task(deliver_notification_emails, notification_ids)
    if settings.registration_requires_approval:
        message = (
            "Account created. Verify your email address; an administrator will "
            "review your account before you can sign in."
        )
    else:
        message = "Account created. Check your email to verify your address."
    return {"message": message, "email": user.email}


@router.post("/login", response_model=UserResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    try:
        user = await auth_service.authenticate_user(db, body.email, body.password)
    except AuthError as exc:
        await audit_service.record_isolated(
            db,
            action=AuditAction.AUTH_LOGIN_FAILED,
            ctx=audit_service.anonymous_context(request=request),
            description=f"Failed sign-in for {body.email}",
            result=AuditResult.FAILURE,
            error_message=exc.detail,
            details={"attempted_email": body.email, "reason": exc.code},
        )
        raise _http_error(exc)
    result = await _start_session(db, user, response, request)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_LOGIN,
        ctx=audit_service.context_from_request(request, user),
        description=f"Signed in as {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
    )
    return result


@router.post("/refresh", response_model=UserResponse)
async def refresh_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    raw = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not raw:
        raise HTTPException(status_code=401, detail="No refresh session")
    try:
        user, new_refresh = await auth_service.rotate_refresh_token(
            db,
            raw,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except AuthError as exc:
        _clear_auth_cookies(response)
        if exc.code == "refresh_reused":
            await audit_service.record_isolated(
                db,
                action=AuditAction.AUTH_REFRESH_REUSE,
                ctx=audit_service.anonymous_context(request=request),
                description="A revoked refresh token was replayed",
                resource_type="user",
                resource_id=exc.user_id,
                subject_user_id=exc.user_id,
                result=AuditResult.FAILURE,
                error_message=exc.detail,
                details={"reason": exc.code},
            )
        raise _http_error(exc)

    access = auth_service.issue_access_token(user)
    _set_auth_cookies(response, access_token=access, refresh_token=new_refresh)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_optional_user),
) -> None:
    # Logout must work with an expired access token: browser sessions outlive
    # the 15-minute JWT, and requiring it left the refresh cookie alive, so the
    # next page load silently signed the user back in. CSRF still applies to
    # cookie-authenticated calls.
    if not request.headers.get("Authorization"):
        check_csrf(request)

    raw = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if raw:
        await auth_service.revoke_refresh_token(db, raw)
    _clear_auth_cookies(response)

    if user is not None:
        await audit_service.record_isolated(
            db,
            action=AuditAction.AUTH_LOGOUT,
            ctx=audit_service.context_from_request(request, user),
            description=f"Signed out {user.email}",
            resource_type="user",
            resource_id=user.id,
            resource_label=user.email,
            subject_user_id=user.id,
        )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserResponse:
    before = {"display_name": user.display_name}
    updated = await auth_service.update_profile(db, user, display_name=body.display_name)
    changed_before, changed_after = audit_service.change_snapshots(before, {"display_name": updated.display_name})
    if changed_before:
        await audit_service.record_isolated(
            db,
            action=AuditAction.AUTH_PROFILE_UPDATED,
            ctx=audit_service.context_from_request(request, updated),
            description=f"Updated profile for {updated.email}",
            resource_type="user",
            resource_id=updated.id,
            resource_label=updated.email,
            subject_user_id=updated.id,
            before=changed_before,
            after=changed_after,
        )
    return UserResponse.model_validate(updated)


@router.post("/me/email", status_code=status.HTTP_202_ACCEPTED)
async def request_email_change(
    body: ChangeEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        await auth_service.request_email_change(db, user, body.new_email, body.current_password)
    except AuthError as exc:
        raise _http_error(exc)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_EMAIL_CHANGE_REQUESTED,
        ctx=audit_service.context_from_request(request, user),
        description=f"Requested an email change for {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        details={"new_email": body.new_email},
    )
    return {"message": f"Verification sent to {body.new_email}. Confirm it to complete the change."}


@router.post("/verify-new-email", response_model=UserResponse)
async def verify_new_email(
    body: VerifyNewEmailRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    try:
        user, previous_email = await auth_service.confirm_email_change(db, body.token)
    except AuthError as exc:
        raise _http_error(exc)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_EMAIL_CHANGE_CONFIRMED,
        ctx=audit_service.context_from_request(request, user),
        description=f"Changed email address for account {user.id}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        before={"email": previous_email},
        after={"email": user.email},
    )
    # Sessions were revoked on the email change; the client must sign in again.
    return UserResponse.model_validate(user)


@router.post("/verify-email", response_model=UserResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    try:
        user = await auth_service.verify_email(db, body.token)
    except AuthError as exc:
        raise _http_error(exc)
    result = await _start_session(db, user, response, request)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_EMAIL_VERIFIED,
        ctx=audit_service.context_from_request(request, user),
        description=f"Verified the email address for {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        details={"via": "email_token"},
    )
    return result


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await auth_service.resend_verification(db, body.email)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_VERIFICATION_RESENT,
        ctx=audit_service.anonymous_context(request=request),
        description=f"Verification email requested for {body.email}",
        details={"attempted_email": body.email},
    )
    return {"message": "If that address needs verification, a new link has been sent."}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await auth_service.request_password_reset(db, body.email)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_PASSWORD_RESET_REQUESTED,
        ctx=audit_service.anonymous_context(request=request),
        description=f"Password reset requested for {body.email}",
        details={"attempted_email": body.email},
    )
    return {"message": "If that address is registered, a reset link has been sent."}


@router.post("/reset-password", response_model=UserResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    try:
        user = await auth_service.reset_password(db, body.token, body.new_password)
    except AuthError as exc:
        raise _http_error(exc)
    result = await _start_session(db, user, response, request)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_PASSWORD_RESET_COMPLETED,
        ctx=audit_service.context_from_request(request, user),
        description=f"Completed a password reset for {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        details={"via": "email_token", "sessions_revoked": True},
    )
    return result


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await auth_service.change_password(db, user, body.current_password, body.new_password)
    except AuthError as exc:
        raise _http_error(exc)
    _clear_auth_cookies(response)
    await audit_service.record_isolated(
        db,
        action=AuditAction.AUTH_PASSWORD_CHANGED,
        ctx=audit_service.context_from_request(request, user),
        description=f"Changed the password for {user.email}",
        resource_type="user",
        resource_id=user.id,
        resource_label=user.email,
        subject_user_id=user.id,
        details={"sessions_revoked": True},
    )
