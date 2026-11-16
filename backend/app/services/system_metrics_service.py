"""Cached infrastructure probe for the admin system page.

A default Docker container shares the host kernel's ``/proc``, so ``psutil``
reports host-level CPU, memory, and disk numbers without host mounts or a
sidecar agent. Worker liveness is probed through Celery's broker ``inspect``
API and Ollama is asked for its loaded model over HTTP. Every call is cached
for a short window and single-flighted so concurrent dashboard polls do not
multiply the work.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.job import Job, JobStatus

try:  # psutil is a runtime dependency, but keep import failures non-fatal.
    import psutil
except ImportError:  # pragma: no cover - exercised only in a broken image
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 10.0
_cache: dict = {"at": 0.0, "data": None}
_lock: asyncio.Lock | None = None
_lock_loop: asyncio.AbstractEventLoop | None = None

_tesseract_version: str | None = None
_tesseract_checked = False

_BYTES_PER_MB = 1024 * 1024
_BYTES_PER_GB = 1024 * 1024 * 1024


def reset_cache() -> None:
    """Clear the probe cache (tests and manual refresh)."""
    _cache.update(at=0.0, data=None)


def _get_lock() -> asyncio.Lock:
    """A lock scoped to the running loop, so tests can use fresh loops."""
    global _lock, _lock_loop
    loop = asyncio.get_running_loop()
    if _lock is None or _lock_loop is not loop:
        _lock = asyncio.Lock()
        _lock_loop = loop
    return _lock


async def collect_system_metrics(db: AsyncSession, redis) -> dict:
    """Return server, service, and queue metrics, cached for 10 seconds."""
    if _cache["data"] is not None and time.monotonic() - _cache["at"] < _CACHE_TTL_SECONDS:
        return _cache["data"]

    async with _get_lock():
        if _cache["data"] is not None and time.monotonic() - _cache["at"] < _CACHE_TTL_SECONDS:
            return _cache["data"]

        server = await _server_metrics()
        services = await _service_health(db, redis)
        queues = await _queue_activity(db, redis)

        data = {
            "generated_at": datetime.now(timezone.utc),
            "overall_status": _overall_status(server, services),
            "server": server,
            "services": services,
            "queues": queues,
        }
        _cache.update(at=time.monotonic(), data=data)
        return data


async def _server_metrics() -> dict:
    if psutil is None:
        return {"available": False}

    cpu_percent = await asyncio.to_thread(psutil.cpu_percent, 0.2)
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except (AttributeError, OSError):  # pragma: no cover - Windows
        load_1 = load_5 = load_15 = None

    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")

    storage_total_gb = None
    storage_used_mb = None
    try:
        storage = psutil.disk_usage(settings.storage_path)
        storage_total_gb = round(storage.total / _BYTES_PER_GB, 2)
        storage_used_mb = round(storage.used / _BYTES_PER_MB, 2)
    except OSError:
        pass

    return {
        "available": True,
        "cpu_percent": round(cpu_percent, 1),
        "cpu_count": psutil.cpu_count(),
        "load_1": round(load_1, 2) if load_1 is not None else None,
        "load_5": round(load_5, 2) if load_5 is not None else None,
        "load_15": round(load_15, 2) if load_15 is not None else None,
        "memory_total_mb": round(memory.total / _BYTES_PER_MB, 1),
        "memory_used_mb": round(memory.used / _BYTES_PER_MB, 1),
        "memory_available_mb": round(memory.available / _BYTES_PER_MB, 1),
        "memory_percent": round(memory.percent, 1),
        "swap_total_mb": round(swap.total / _BYTES_PER_MB, 1),
        "swap_used_mb": round(swap.used / _BYTES_PER_MB, 1),
        "disk_total_gb": round(disk.total / _BYTES_PER_GB, 2),
        "disk_used_gb": round(disk.used / _BYTES_PER_GB, 2),
        "disk_free_gb": round(disk.free / _BYTES_PER_GB, 2),
        "disk_percent": round(disk.percent, 1),
        "storage_total_gb": storage_total_gb,
        "storage_used_mb": storage_used_mb,
        "uptime_seconds": round(time.time() - psutil.boot_time(), 0),
    }


async def _service_health(db: AsyncSession, redis) -> list[dict]:
    services = [{"name": "Backend API", "status": "ok", "detail": "Serving requests"}]
    services.append(await _check_postgres(db))
    redis_result = await _check_redis(redis)
    services.append(redis_result)
    # Kombu retries an unreachable broker for several seconds. Skip the inspect
    # entirely when Redis is already known to be down, and bound it regardless.
    services.append(await _check_celery(redis_result["status"] == "ok"))
    services.append(await _check_ollama())
    services.append(_check_tesseract())
    return services


async def _check_postgres(db: AsyncSession) -> dict:
    started = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return {"name": "PostgreSQL", "status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        return {"name": "PostgreSQL", "status": "unreachable", "detail": str(exc)[:300]}


async def _check_redis(redis) -> dict:
    if redis is None:
        return {"name": "Redis", "status": "unreachable", "detail": "No connection pool"}
    started = time.perf_counter()
    try:
        pong = await redis.ping()
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        if not pong:
            return {"name": "Redis", "status": "degraded", "detail": "PING returned false"}
        return {"name": "Redis", "status": "ok", "latency_ms": latency_ms}
    except Exception as exc:  # noqa: BLE001
        return {"name": "Redis", "status": "unreachable", "detail": str(exc)[:300]}


async def _check_celery(redis_reachable: bool = True) -> dict:
    if not redis_reachable:
        return {
            "name": "Celery workers",
            "status": "unreachable",
            "detail": "Broker unreachable (Redis down)",
        }
    try:
        info = await asyncio.wait_for(asyncio.to_thread(_inspect_workers), timeout=3.0)
        return {"name": "Celery workers", **info}
    except asyncio.TimeoutError:
        return {"name": "Celery workers", "status": "unreachable", "detail": "Inspect timed out"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "Celery workers", "status": "unreachable", "detail": str(exc)[:300]}


async def _check_ollama() -> dict:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            tags = await client.get(f"{settings.ollama_url}/api/tags")
            tags.raise_for_status()
            loaded = await client.get(f"{settings.ollama_url}/api/ps")
            loaded.raise_for_status()
        latency_ms = round((time.perf_counter() - started) * 1000, 1)

        models = [m.get("name") for m in tags.json().get("models", []) if m.get("name")]
        running = [
            {
                "name": m.get("name"),
                "size_mb": round((m.get("size") or 0) / _BYTES_PER_MB, 1),
            }
            for m in loaded.json().get("models", [])
        ]
        status = "ok"
        detail = f"{len(models)} model(s) available"
        if not running:
            # Ollama is reachable but cold; the first extraction pays the load.
            status = "degraded"
            detail = "No model loaded (cold start)"
        meta = {"models": models, "loaded": running}
        return {"name": "LLM (Ollama)", "status": status, "detail": detail, "latency_ms": latency_ms, "meta": meta}
    except Exception as exc:  # noqa: BLE001
        return {"name": "LLM (Ollama)", "status": "unreachable", "detail": str(exc)[:300]}


def _check_tesseract() -> dict:
    global _tesseract_version, _tesseract_checked
    if not _tesseract_checked:
        _tesseract_checked = True
        cmd = settings.tesseract_cmd
        if shutil.which(cmd):
            try:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                first_line = (result.stdout or result.stderr or "").strip().splitlines()
                _tesseract_version = first_line[0] if first_line else "installed"
            except (OSError, subprocess.SubprocessError):
                _tesseract_version = "installed (version unknown)"
        else:
            _tesseract_version = None

    if _tesseract_version is None:
        return {"name": "OCR (Tesseract)", "status": "unavailable", "detail": "Binary not found"}
    return {"name": "OCR (Tesseract)", "status": "ok", "detail": _tesseract_version}


def _inspect_workers() -> dict:
    """Synchronous Celery broker inspection, run off the event loop."""
    from app.tasks.celery_app import celery_app

    try:
        inspector = celery_app.control.inspect(timeout=1.0)
        ping = inspector.ping()
        active = inspector.active()
    except Exception as exc:  # noqa: BLE001
        return {"status": "unreachable", "detail": str(exc)[:300]}

    if not ping:
        return {"status": "unreachable", "detail": "No workers responded to ping"}

    workers = sorted(ping.keys())
    active_tasks = sum(len(task_list) for task_list in (active or {}).values())
    routes = celery_app.conf.task_routes or {}
    queues = sorted({route.get("queue") for route in routes.values() if route.get("queue")})

    return {
        "status": "ok",
        "detail": f"{len(workers)} worker(s), {active_tasks} active task(s)",
        "meta": {
            "workers": workers,
            "active_tasks": active_tasks,
            "queues": queues,
        },
    }


async def _queue_activity(db: AsyncSession, redis) -> dict:
    depths = []
    for name in _queue_names():
        depth = 0
        if redis is not None:
            try:
                depth = int(await redis.llen(name) or 0)
            except Exception:  # noqa: BLE001
                depth = 0
        depths.append({"name": name, "depth": depth})

    status_rows = []
    type_rows = []
    completed_recent = 0
    try:
        status_rows = (await db.execute(select(Job.status, func.count(Job.id)).group_by(Job.status))).all()
        type_rows = (await db.execute(select(Job.job_type, func.count(Job.id)).group_by(Job.job_type))).all()
        since = datetime.now(timezone.utc) - timedelta(minutes=15)
        completed_recent = (
            await db.scalar(
                select(func.count(Job.id)).where(
                    Job.status == JobStatus.COMPLETED,
                    Job.completed_at >= since,
                )
            )
            or 0
        )
    except Exception:  # noqa: BLE001
        # The endpoint must still report a critical database status instead of
        # failing outright when Postgres is down.
        logger.warning("Queue activity database query failed", exc_info=True)

    by_status = {status: count for status, count in status_rows}
    by_type = {job_type: count for job_type, count in type_rows}

    return {
        "queues": depths,
        "by_status": by_status,
        "by_type": by_type,
        "completed_last_15m": int(completed_recent),
    }


def _queue_names() -> list[str]:
    try:
        from app.tasks.celery_app import celery_app

        routes = celery_app.conf.task_routes or {}
        names = {route.get("queue") for route in routes.values() if route.get("queue")}
        names.add("default")
        return sorted(names)
    except Exception:  # noqa: BLE001
        return ["default", "llm", "ocr"]


def _overall_status(server: dict, services: list[dict]) -> str:
    by_name = {service["name"]: service for service in services}
    critical_services = ("PostgreSQL", "Redis", "Celery workers")
    if any(by_name.get(name, {}).get("status") in ("unreachable", "unavailable") for name in critical_services):
        return "critical"

    degraded = any(service.get("status") not in ("ok", None) for service in services)
    for key in ("cpu_percent", "memory_percent", "disk_percent"):
        value = server.get(key)
        if value is not None and value >= 85:
            degraded = True
    return "degraded" if degraded else "ok"
