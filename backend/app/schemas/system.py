"""Schemas for admin infrastructure monitoring."""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


class ServerMetrics(BaseModel):
    available: bool = True
    cpu_percent: float | None = None
    cpu_count: int | None = None
    load_1: float | None = None
    load_5: float | None = None
    load_15: float | None = None
    memory_total_mb: float | None = None
    memory_used_mb: float | None = None
    memory_available_mb: float | None = None
    memory_percent: float | None = None
    swap_total_mb: float | None = None
    swap_used_mb: float | None = None
    disk_total_gb: float | None = None
    disk_used_gb: float | None = None
    disk_free_gb: float | None = None
    disk_percent: float | None = None
    storage_total_gb: float | None = None
    storage_used_mb: float | None = None
    uptime_seconds: float | None = None


class ServiceHealth(BaseModel):
    name: str
    status: str  # ok | degraded | unreachable | unavailable
    detail: str | None = None
    latency_ms: float | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class QueueDepth(BaseModel):
    name: str
    depth: int


class QueueActivity(BaseModel):
    queues: list[QueueDepth] = Field(default_factory=list)
    by_status: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    completed_last_15m: int = 0


class SystemMetricsResponse(BaseModel):
    generated_at: datetime.datetime
    overall_status: str  # ok | degraded | critical
    server: ServerMetrics
    services: list[ServiceHealth]
    queues: QueueActivity


class MaintenanceStatus(BaseModel):
    enabled: bool = False
    message: str | None = None
    until: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    updated_by: str | None = None


class MaintenanceUpdate(BaseModel):
    enabled: bool
    message: str | None = None
    until: datetime.datetime | None = None


class PublicStatusResponse(BaseModel):
    maintenance: MaintenanceStatus
