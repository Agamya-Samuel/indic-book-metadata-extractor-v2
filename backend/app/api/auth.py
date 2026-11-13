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

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    ACCESS_TOKEN_COOKIE,
    CSRF_COOKIE,
    REFRESH_TOKEN_COOKIE,
    generate_opaque_token,
    hash_opaque_token,
)
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services import auth_service
from app.services.auth_service import AuthError
from app.services.notification_service import deliver_notification_emails

router = APIRouter()


def _http_error(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _set_auth_cookies(
    response: Response, *, access_token: str, refresh_token: str
) -> None:
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
        raise _http_error(exc)
    return await _start_session(db, user, response, request)


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
        raise _http_error(exc)

    access = auth_service.issue_access_token(user)
    _set_auth_cookies(response, access_token=access, refresh_token=new_refresh)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    raw = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if raw:
        await auth_service.revoke_refresh_token(db, raw)
    _clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
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
    return await _start_session(db, user, response, request)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    body: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await auth_service.resend_verification(db, body.email)
    return {"message": "If that address needs verification, a new link has been sent."}


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await auth_service.request_password_reset(db, body.email)
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
    return await _start_session(db, user, response, request)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    try:
        await auth_service.change_password(
            db, user, body.current_password, body.new_password
        )
    except AuthError as exc:
        raise _http_error(exc)
    _clear_auth_cookies(response)
