import logging
import time
import uuid as _uuid
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiter configuration
RATE_LIMIT_REQUESTS = 60  # max requests per window
RATE_LIMIT_WINDOW = 60  # seconds

_redis_pool: aioredis.Redis | None = None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple Redis-based sliding window rate limiter per client IP."""

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks and static assets
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        if _redis_pool is None:
            # Redis not available — skip rate limiting
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        # Respect X-Forwarded-For when behind a reverse proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        key = f"rate_limit:{client_ip}"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW
        # Use a unique member per request to avoid collisions under concurrency
        member = f"{now}:{_uuid.uuid4().hex[:8]}"

        try:
            pipe = _redis_pool.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {member: now})
            pipe.zcard(key)
            pipe.expire(key, RATE_LIMIT_WINDOW)
            results = await pipe.execute()

            request_count = results[2]
            if request_count > RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."},
                    headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
                )
        except Exception:
            # If Redis is down, allow the request through
            pass

        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global _redis_pool
    from app.core.database import engine
    from app.services.llm_service import llm_service

    logger.info("Application starting up...")
    try:
        _redis_pool = aioredis.from_url(settings.redis_url, decode_responses=True)
        await _redis_pool.ping()
        logger.info("Redis connection established for rate limiting.")
    except Exception as e:
        logger.warning("Redis not available for rate limiting: %s", e)
        _redis_pool = None
    yield
    # Shutdown
    logger.info("Application shutting down...")
    if _redis_pool:
        await _redis_pool.aclose()
    await engine.dispose()
    await llm_service.close()


app = FastAPI(
    title="Indic Book Metadata Extractor",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting middleware (must be added BEFORE CORS — runs after CORS in the stack)
app.add_middleware(RateLimitMiddleware)

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
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "type": "validation_error",
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "type": "http_error"},
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
