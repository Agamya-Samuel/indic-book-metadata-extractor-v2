"""Schemas for the admin-managed runtime SMTP configuration."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SmtpConfigUpdateRequest(BaseModel):
    enabled: bool | None = None
    host: str | None = Field(default=None, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=255)
    # Blank/omitted keeps the stored password unchanged.
    password: str | None = Field(default=None, max_length=1024)
    from_email: EmailStr | None = None
    from_name: str | None = Field(default=None, max_length=255)
    use_tls: bool | None = None
    use_starttls: bool | None = None


class SmtpConfigResponse(BaseModel):
    enabled: bool
    host: str
    port: int
    username: str
    password_set: bool
    from_email: str
    from_name: str
    use_tls: bool
    use_starttls: bool
    source: str  # "db" or "env"
    updated_at: str | None = None
    updated_by: str | None = None


class SmtpTestRequest(BaseModel):
    # Optional test recipient; when omitted, only the connection/login is checked.
    to_email: EmailStr | None = None
    # Unsaved values to test; omitted fields inherit the effective config.
    config: SmtpConfigUpdateRequest | None = None


class SmtpTestResponse(BaseModel):
    ok: bool
    detail: str