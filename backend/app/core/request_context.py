"""Per-request identity shared by the rate limiter, audit log, and app logs.

``client_ip`` resolves the real caller behind Cloudflare/Traefik. It lives here
rather than in ``app.main`` so services and middleware can use it without
importing the application module (which would be circular).

``RequestIDMiddleware`` assigns (or accepts) a request id, keeps it in a
context variable for the lifetime of the request, and echoes it back in the
``X-Request-ID`` response header. Audit rows carry it so an entry can be
correlated with the application log line for the same request.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

# A supplied request id is echoed to clients and stored in audit_logs
# (varchar(64)); accept only a short token so a client cannot forge an
# oversized or malformed correlation id.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def client_ip(request: Request) -> str:
    """The real client address, not the edge proxy that delivered the request.

    Cloudflare sets ``CF-Connecting-IP``; behind Traefik the socket peer is the
    proxy, so keying limits on it would put every visitor in one bucket. Only
    the *last* ``X-Forwarded-For`` hop is trusted (the one our own proxy
    appended); earlier entries are client-controlled. Residual risk: until the
    origin only accepts Cloudflare, a direct caller can forge either header —
    see plans/011-launch-readiness.md.
    """
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded and forwarded.strip():
        return forwarded.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        last_hop = xff.split(",")[-1].strip()
        if last_hop:
            return last_hop
    return request.client.host if request.client else "unknown"


def get_request_id() -> str | None:
    """The current request's id, or None outside a request (e.g. a worker)."""
    return _request_id.get()


def _header(scope: Scope, name: str) -> str | None:
    target = name.lower().encode()
    for key, value in scope.get("headers") or []:
        if key.lower() == target:
            return value.decode("latin-1").strip() or None
    return None


class RequestIDMiddleware:
    """Pure ASGI middleware so the context variable survives into handlers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = _header(scope, REQUEST_ID_HEADER)
        request_id = supplied if supplied and _REQUEST_ID_RE.match(supplied) else uuid.uuid4().hex
        token = _request_id.set(request_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            _request_id.reset(token)
