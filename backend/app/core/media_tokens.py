"""Short-lived signed URLs for page images and thumbnails.

``<img>`` requests cannot run the access-token refresh interceptor, so a
15-minute access cookie used to leave broken images on a long review session.
Image URLs now carry a signed token scoped to one page or one book thumbnail,
issued only to a caller who already passed the ownership check.
"""

from __future__ import annotations

from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.security import utcnow

MEDIA_TOKEN_TYPE = "media"
MEDIA_TOKEN_TTL = timedelta(hours=6)


def issue_media_token(scope: str, resource_id: str) -> str:
    now = utcnow()
    payload = {
        "sub": resource_id,
        "scope": scope,
        "type": MEDIA_TOKEN_TYPE,
        "iat": now,
        "exp": now + MEDIA_TOKEN_TTL,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def verify_media_token(token: str | None, scope: str, resource_id: str) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.InvalidTokenError:
        return False
    return (
        payload.get("type") == MEDIA_TOKEN_TYPE
        and payload.get("scope") == scope
        and str(payload.get("sub")) == str(resource_id)
    )


def thumbnail_scope(book_id) -> tuple[str, str]:
    return ("thumbnail", str(book_id))


def page_scope(page_id) -> tuple[str, str]:
    return ("page", str(page_id))


def thumbnail_url(book_id, page_number: int) -> str:
    scope, resource = thumbnail_scope(book_id)
    token = issue_media_token(scope, resource)
    return f"/api/books/{book_id}/pages/{page_number}/thumbnail?token={token}"


def page_image_url(page_id) -> str:
    scope, resource = page_scope(page_id)
    token = issue_media_token(scope, resource)
    return f"/api/pages/{page_id}/image?token={token}"


def page_preview_url(page_id) -> str:
    scope, resource = page_scope(page_id)
    token = issue_media_token(scope, resource)
    return f"/api/pages/{page_id}/preprocessing/preview?token={token}"
