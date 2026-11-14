import asyncio
import logging
import os
import re
import time
import uuid as _uuid
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging_config import setup_logging

logger = logging.getLogger(__name__)

# Rate limiter configuration
RATE_LIMIT_REQUESTS = 60  # max requests per window
RATE_LIMIT_WINDOW = 60  # seconds

# Credential endpoints get a stricter per-IP budget.
AUTH_RATE_LIMIT_REQUESTS = 10
AUTH_RATE_LIMIT_WINDOW = 60
AUTH_RATE_LIMIT_PATHS = frozenset(
    {
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/forgot-password",
        "/api/auth/reset-password",
        "/api/auth/resend-verification",
    }
)

_redis_pool: aioredis.Redis | None = None


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


_THUMBNAIL_PATH_RE = re.compile(r"^/api/books/[^/]+/pages/\d+/thumbnail$")
_SSE_PATH_RE = re.compile(r"^/api/sse/books/[^/]+/events$")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple Redis-based sliding window rate limiter per client IP."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static assets
        if request.url.path in ("/health", "/api/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Skip rate limiting for thumbnail GETs — they serve cached static files
        if request.method == "GET" and _THUMBNAIL_PATH_RE.match(request.url.path):
            return await call_next(request)

        # Skip rate limiting for SSE event streams — they are long-lived and
        # would otherwise consume the per-IP quota in a single connection.
        if request.method == "GET" and _SSE_PATH_RE.match(request.url.path):
            return await call_next(request)

        if _redis_pool is None:
            # Redis not available — skip rate limiting
            return await call_next(request)

        ip = client_ip(request)

        is_auth = request.url.path in AUTH_RATE_LIMIT_PATHS
        limit = AUTH_RATE_LIMIT_REQUESTS if is_auth else RATE_LIMIT_REQUESTS
        window = AUTH_RATE_LIMIT_WINDOW if is_auth else RATE_LIMIT_WINDOW
        scope = "auth" if is_auth else "global"

        key = f"rate_limit:{scope}:{ip}"
        now = time.time()
        window_start = now - window
        # Use a unique member per request to avoid collisions under concurrency
        member = f"{now}:{_uuid.uuid4().hex[:8]}"

        try:
            pipe = _redis_pool.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, window)
            results = await pipe.execute()

            request_count = results[2]
            if request_count > limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(window)},
                )
        except Exception:
            # If Redis is down, allow the request through
            pass

        return await call_next(request)


REAPER_INTERVAL_SECONDS = 300


class UploadSizeLimitMiddleware:
    """Reject an oversized upload from its Content-Length before it is spooled.

    Starlette parses and spools the multipart part to disk before the route
    runs, so the handler-level check is too late to protect the disk. Bodies
    without a length still hit the copy-loop cap in the upload endpoint.
    """

    def __init__(self, app):
        self.app = app
        self.max_bytes = settings.max_upload_size_mb * 1024 * 1024
        self.headroom = 1024 * 1024  # multipart envelope

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != "/api/books/upload":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers") or [])
        raw_length = headers.get(b"content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                length = -1
            if length > self.max_bytes + self.headroom:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"File exceeds {settings.max_upload_size_mb} MB limit",
                        "type": "http_error",
                    },
                )
                await response(scope, receive, send)
                return
        return await self.app(scope, receive, send)


def _validate_security_settings() -> None:
    """Refuse an insecure production start rather than discovering it later."""
    if not settings.debug and len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be at least 32 characters outside DEBUG mode."
        )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if "*" in origins:
        logger.warning(
            "CORS_ORIGINS contains '*': credentialed browser requests from any "
            "origin will be accepted. Set the public frontend origin instead."
        )


async def _reaper_loop() -> None:
    """Periodically fail jobs no worker will ever finish."""
    from app.core.database import async_session_factory
    from app.services.job_reaper import reap_stale_jobs

    while True:
        try:
            async with async_session_factory() as db:
                reaped = await reap_stale_jobs(db)
                if reaped:
                    logger.warning("Stale-job sweep reaped %d job(s)", reaped)
        except Exception:  # noqa: BLE001
            logger.exception("Stale-job sweep failed")
        await asyncio.sleep(REAPER_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    _validate_security_settings()

    global _redis_pool
    from app.core.database import get_engine
    from app.services.llm_service import llm_service
    from app.services.sse_service import sse_service

    logger.info("Application starting up...")
    try:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_pool.ping()
        logger.info("Redis connection established for rate limiting.")
    except Exception as e:
        logger.warning("Redis not available for rate limiting: %s", e)
        _redis_pool = None
    if _redis_pool is not None:
        try:
            await sse_service.start(_redis_pool)
        except Exception:
            logger.exception("Failed to start SSE service; clients will see no events")

    reaper_task: asyncio.Task | None = None
    if settings.stale_job_reaper_enabled:
        reaper_task = asyncio.create_task(_reaper_loop(), name="job-reaper")

    yield
    # Shutdown
    logger.info("Application shutting down...")
    if reaper_task is not None:
        reaper_task.cancel()
        try:
            await reaper_task
        except asyncio.CancelledError:
            pass
    await sse_service.stop()
    if _redis_pool:
        await _redis_pool.aclose()
    engine = get_engine()
    if engine is not None:
        await engine.dispose()
    await llm_service.close()


# /docs, /redoc and /openapi.json make the whole API surface enumerable, so
# they stay off outside debug builds.
app = FastAPI(
    title="Indic Book Metadata Extractor",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Initialise the New Relic agent if enabled.
# When running under `newrelic-admin run-program` (Docker), the agent is already
# bootstrapped via sitecustomize and auto-instruments FastAPI/Starlette — so we
# must NOT apply ASGIApplicationWrapper here (that would double-wrap and produce
# duplicate traces). We still call initialize() as a safe, idempotent fallback
# for local development where `newrelic-admin` is not used.
if settings.new_relic_enabled:
    try:
        import newrelic.agent  # noqa: F401

        _nr_config = os.environ.get("NEW_RELIC_CONFIG_FILE", "newrelic.ini")
        newrelic.agent.initialize(_nr_config)
        logger.info("New Relic agent initialised (config=%s).", _nr_config)
    except ImportError:
        logger.warning("newrelic package not installed; skipping APM.")
    except Exception as exc:
        logger.critical(
            "New Relic is ENABLED but initialisation failed — "
            "APM data will NOT be reported. Error: %s",
            exc,
        )

# Rate limiting middleware (must be added BEFORE CORS — runs after CORS in the stack)
app.add_middleware(RateLimitMiddleware)

# Reject oversized upload bodies before the multipart part is spooled.
app.add_middleware(UploadSizeLimitMiddleware)

# CORS from config
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


# Applied to every API response, including rate-limit and error responses.
# frame-ancestors stays minimal (no script-src) so it cannot break the app.
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


# ---------------------------------------------------------------------------
# Health check — verifies downstream dependencies
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    checks: dict = {}

    # PostgreSQL
    try:
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    # Redis — reuse the connection pool from lifespan
    try:
        if _redis_pool is not None:
            await _redis_pool.ping()
            checks["redis"] = "ok"
        else:
            checks["redis"] = "error: not connected"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
        checks["ollama"] = "ok"
    except Exception as e:
        checks["ollama"] = f"error: {e}"

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # ``ctx`` can hold the original Exception from a custom validator, which is
    # not JSON serializable; dropping it and encoding the rest keeps a bad
    # payload a 422 instead of a 500.
    errors = [
        {key: value for key, value in error.items() if key != "ctx"}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(errors), "type": "validation_error"},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_error"},
        headers=exc.headers,
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "type": "internal_error",
        },
    )
