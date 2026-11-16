"""Block non-admin API traffic while maintenance mode is enabled.

Admins keep full access (so they can turn maintenance off), and the auth,
status, and health routes stay reachable. The check reads the in-process
snapshot maintained by ``maintenance_service``; it never touches the database
on the request path.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.security import ACCESS_TOKEN_COOKIE, decode_access_token
from app.services import maintenance_service

_ALLOW_EXACT = {
    "/health",
    "/api/health",
    "/api/status",
    "/api/auth",
    "/api/admin",
    "/docs",
    "/redoc",
    "/openapi.json",
}
_ALLOW_PREFIXES = ("/api/auth/", "/api/admin/")


def _request_is_admin(request) -> bool:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
    if not token:
        return False
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001
        return False
    return payload.get("role") == "admin"


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if (
            request.method == "OPTIONS"
            or path in _ALLOW_EXACT
            or path.startswith(_ALLOW_PREFIXES)
        ):
            return await call_next(request)

        state = maintenance_service.get_state()
        if not state["enabled"] or _request_is_admin(request):
            return await call_next(request)

        return JSONResponse(
            status_code=503,
            content={
                "detail": state["message"],
                "type": "maintenance",
                "maintenance": {
                    "enabled": True,
                    "message": state["message"],
                    "until": state["until"],
                },
            },
        )
