"""Authentication and user-management request/response schemas."""

from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.user import UserRole


def _validate_password(value: str) -> str:
    if len(value) < settings.password_min_length:
        raise ValueError(
            f"Password must be at least {settings.password_min_length} characters"
        )
    if len(value) > 128:
        raise ValueError("Password must be at most 128 characters")
    return value


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    email_verified_at: datetime.datetime | None
    last_login_at: datetime.datetime | None
    created_at: datetime.datetime | None

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str

    _password = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    new_password: str

    _password = field_validator("new_password")(_validate_password)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    _password = field_validator("new_password")(_validate_password)


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str
    role: UserRole = UserRole.USER

    _password = field_validator("password")(_validate_password)


class AdminUserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: UserRole | None = None
    is_active: bool | None = None


class AdminPasswordResetRequest(BaseModel):
    new_password: str

    _password = field_validator("new_password")(_validate_password)


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AdminUserDetailResponse(UserResponse):
    book_count: int
    active_job_count: int
