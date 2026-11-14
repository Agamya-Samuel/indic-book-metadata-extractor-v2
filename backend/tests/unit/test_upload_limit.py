"""The upload endpoint rejects an oversized body before it is spooled."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.main import UploadSizeLimitMiddleware


async def _ok_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _run(middleware, scope) -> list[dict]:
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    await middleware(scope, receive, send)
    return messages


def _scope(path: str, content_length: int | None) -> dict:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    return {"type": "http", "path": path, "headers": headers}


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected_from_content_length(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    middleware = UploadSizeLimitMiddleware(_ok_app)

    messages = await _run(middleware, _scope("/api/books/upload", 5 * 1024 * 1024))

    assert messages[0]["status"] == 413


@pytest.mark.asyncio
async def test_upload_within_the_limit_passes(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    middleware = UploadSizeLimitMiddleware(_ok_app)

    messages = await _run(middleware, _scope("/api/books/upload", 512 * 1024))

    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_other_paths_are_not_affected(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size_mb", 1)
    middleware = UploadSizeLimitMiddleware(_ok_app)

    messages = await _run(middleware, _scope("/api/books/123/pages", 50 * 1024 * 1024))

    assert messages[0]["status"] == 200
