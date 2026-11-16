"""Infrastructure probe: host metrics, degraded paths, caching."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services import system_metrics_service as svc


@pytest.fixture(autouse=True)
def _reset_cache():
    svc.reset_cache()
    yield
    svc.reset_cache()


class FakeRedis:
    def __init__(self, depths: dict[str, int] | None = None):
        self.depths = depths or {}
        self.calls: list[str] = []

    async def llen(self, name: str) -> int:
        self.calls.append(name)
        return self.depths.get(name, 0)

    async def ping(self) -> bool:
        return True


class TestOverallStatus:
    def test_critical_when_postgres_unreachable(self) -> None:
        status = svc._overall_status({}, [{"name": "PostgreSQL", "status": "unreachable"}])
        assert status == "critical"

    def test_degraded_on_high_cpu(self) -> None:
        status = svc._overall_status(
            {"cpu_percent": 91, "memory_percent": 10, "disk_percent": 10},
            [{"name": "Backend API", "status": "ok"}],
        )
        assert status == "degraded"

    def test_ok_when_healthy(self) -> None:
        status = svc._overall_status(
            {"cpu_percent": 10, "memory_percent": 20, "disk_percent": 30},
            [{"name": "Backend API", "status": "ok"}],
        )
        assert status == "ok"


class TestServerMetrics:
    async def test_reports_host_values(self) -> None:
        metrics = await svc._server_metrics()
        assert metrics["available"] is True
        assert metrics["memory_total_mb"] > 0
        assert metrics["disk_total_gb"] > 0
        assert 0 <= metrics["cpu_percent"] <= 100
        assert metrics["uptime_seconds"] >= 0

    async def test_missing_psutil_degrades(self) -> None:
        with patch.object(svc, "psutil", None):
            metrics = await svc._server_metrics()
        assert metrics == {"available": False}


class TestServiceChecks:
    async def test_redis_without_pool_is_unreachable(self) -> None:
        result = await svc._check_redis(None)
        assert result["status"] == "unreachable"

    async def test_redis_ping_success(self) -> None:
        result = await svc._check_redis(FakeRedis())
        assert result["status"] == "ok"
        assert result["latency_ms"] is not None

    async def test_postgres_check(self, db_session) -> None:
        result = await svc._check_postgres(db_session)
        assert result["status"] == "ok"

    async def test_tesseract_state(self) -> None:
        result = svc._check_tesseract()
        assert result["status"] in ("ok", "unavailable")

    async def test_celery_skipped_when_broker_down(self) -> None:
        result = await svc._check_celery(redis_reachable=False)
        assert result["status"] == "unreachable"
        assert "Redis down" in result["detail"]


class TestQueueActivity:
    async def test_reads_depth_and_status_counts(self, db_session) -> None:
        redis = FakeRedis({"ocr": 3, "llm": 1, "default": 0})
        activity = await svc._queue_activity(db_session, redis)

        depths = {row["name"]: row["depth"] for row in activity["queues"]}
        assert depths["ocr"] == 3
        assert depths["llm"] == 1
        assert set(redis.calls) >= {"ocr", "llm", "default"}
        assert activity["by_status"] == {}
        assert activity["completed_last_15m"] == 0

    async def test_without_redis_reports_zero(self, db_session) -> None:
        activity = await svc._queue_activity(db_session, None)
        assert all(row["depth"] == 0 for row in activity["queues"])

    async def test_survives_database_failure(self) -> None:
        class BrokenDB:
            async def execute(self, *args, **kwargs):
                raise RuntimeError("db down")

            async def scalar(self, *args, **kwargs):
                raise RuntimeError("db down")

        activity = await svc._queue_activity(BrokenDB(), None)
        assert activity["by_status"] == {}
        assert activity["by_type"] == {}
        assert activity["completed_last_15m"] == 0


class TestCollectCache:
    async def test_cached_result_is_reused(self, db_session) -> None:
        celery = AsyncMock(return_value={"name": "Celery workers", "status": "ok", "detail": "1 worker"})
        ollama = AsyncMock(return_value={"name": "LLM (Ollama)", "status": "ok"})
        with patch.object(svc, "_check_celery", celery), patch.object(svc, "_check_ollama", ollama):
            first = await svc.collect_system_metrics(db_session, None)
            second = await svc.collect_system_metrics(db_session, None)

        assert first is second
        assert celery.await_count == 1
        assert ollama.await_count == 1
        assert len(first["services"]) == 6
        assert first["overall_status"] in ("ok", "degraded", "critical")

    async def test_reset_cache_forces_a_new_probe(self, db_session) -> None:
        celery = AsyncMock(return_value={"name": "Celery workers", "status": "ok"})
        with patch.object(svc, "_check_celery", celery), patch.object(svc, "_check_ollama", AsyncMock()):
            await svc.collect_system_metrics(db_session, None)
            svc.reset_cache()
            await svc.collect_system_metrics(db_session, None)

        assert celery.await_count == 2
