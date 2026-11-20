"""Audit service: sanitisation, diffing, write paths, and the event catalogue."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog, AuditResult
from app.services import audit_service
from app.services.audit_service import (
    ACTION_SPECS,
    CRITICAL_ACTIONS,
    AuditAction,
    AuditActorType,
    AuditCategory,
    AuditContext,
    category_for,
    change_snapshots,
    context_from_request,
    diff,
    sanitize,
    system_context,
)


# ---------------------------------------------------------------------------
# Event catalogue
# ---------------------------------------------------------------------------


def test_every_action_has_a_spec() -> None:
    for action in AuditAction:
        assert action in ACTION_SPECS, action
        assert ACTION_SPECS[action].label
        assert ACTION_SPECS[action].category in set(AuditCategory)


def test_critical_actions_are_known_actions() -> None:
    assert CRITICAL_ACTIONS
    assert CRITICAL_ACTIONS <= set(AuditAction)
    assert category_for(AuditAction.USER_DELETED) is AuditCategory.USER


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------


def test_sanitize_redacts_credentials_recursively() -> None:
    payload = {
        "password": "hunter2",
        "smtp": {"password": "secret", "host": "smtp.example.com"},
        "nested": [{"api_key": "xyz", "ok": 1}],
        "csrf_token": "abc",
        "password_set": True,
        "token_version": 3,
    }
    safe, truncated = sanitize(payload)
    assert truncated is False
    assert safe["password"] == "[redacted]"
    assert safe["smtp"] == {"password": "[redacted]", "host": "smtp.example.com"}
    assert safe["nested"][0] == {"api_key": "[redacted]", "ok": 1}
    assert safe["csrf_token"] == "[redacted]"
    # Intentional booleans/counters survive.
    assert safe["password_set"] is True
    assert safe["token_version"] == 3


def test_sanitize_truncates_long_strings_and_deep_structures() -> None:
    safe, truncated = sanitize({"text": "x" * 5000})
    assert truncated is True
    assert safe["text"].endswith("…")

    deep: dict = {}
    cursor = deep
    for _ in range(10):
        cursor["child"] = {}
        cursor = cursor["child"]
    safe_deep, deep_truncated = sanitize(deep)
    assert deep_truncated is True
    # Walk to the innermost value: it must be the truncation marker.
    node = safe_deep
    seen = 0
    while isinstance(node, dict) and "child" in node:
        node = node["child"]
        seen += 1
    assert node == "[truncated]"
    assert seen <= 6


def test_sanitize_handles_uuids_and_datetimes() -> None:
    from datetime import datetime, timezone

    value = uuid.uuid4()
    safe, _ = sanitize({"id": value, "at": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    assert safe["id"] == str(value)
    assert safe["at"].startswith("2026-01-01")


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------


def test_diff_reports_only_changed_fields() -> None:
    before = {"title": "A", "author": "X", "publisher": "P"}
    after = {"title": "A", "author": "Y", "publisher": "P"}
    changes = diff(before, after)
    assert changes == {"author": {"from": "X", "to": "Y"}}


def test_change_snapshots_limits_to_changed_keys() -> None:
    before = {"title": "A", "author": "X"}
    after = {"title": "A", "author": "Y", "language": "tel"}
    before_changes, after_changes = change_snapshots(before, after)
    # Keys only present on one side still count as changed (None on the other).
    assert before_changes == {"author": "X", "language": None}
    assert after_changes == {"author": "Y", "language": "tel"}

    assert change_snapshots(after, after) == ({}, {})


# ---------------------------------------------------------------------------
# Actor contexts
# ---------------------------------------------------------------------------


def test_system_and_anonymous_contexts() -> None:
    ctx = system_context(label="job-reaper")
    assert ctx.actor_type == AuditActorType.SYSTEM
    assert ctx.actor_display_name == "job-reaper"

    anon = audit_service.anonymous_context()
    assert anon.actor_type == AuditActorType.ANONYMOUS
    assert anon.actor_id is None


# ---------------------------------------------------------------------------
# Write paths
# ---------------------------------------------------------------------------


async def test_record_stages_in_caller_transaction(db_session) -> None:
    ctx = AuditContext(actor_type=AuditActorType.USER, actor_id=uuid.uuid4(), actor_role="user")
    await audit_service.record(
        db_session,
        action=AuditAction.METADATA_UPDATED,
        ctx=ctx,
        description="test update",
        resource_type="book",
        resource_id=uuid.uuid4(),
        details={"password": "should-not-appear"},
    )

    # Visible inside the transaction...
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].details == {"password": "[redacted]"}
    assert rows[0].category == AuditCategory.PROCESSING.value

    # ...and gone after a rollback.
    await db_session.rollback()
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert rows == []


async def test_record_isolated_commits_immediately(db_session) -> None:
    ctx = AuditContext(actor_type=AuditActorType.ADMIN, actor_id=uuid.uuid4(), actor_role="admin")
    row = await audit_service.record_isolated(
        db_session,
        action=AuditAction.BOOK_UPLOADED,
        ctx=ctx,
        description="uploaded",
    )
    assert row is not None

    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1


async def test_record_isolated_rejects_critical_actions(db_session) -> None:
    ctx = AuditContext(actor_type=AuditActorType.ADMIN, actor_id=uuid.uuid4(), actor_role="admin")
    with pytest.raises(RuntimeError, match="must be recorded in the action's transaction"):
        await audit_service.record_isolated(
            db_session,
            action=AuditAction.USER_DELETED,
            ctx=ctx,
            description="delete",
        )


async def test_client_controlled_headers_are_bounded(db_session) -> None:
    # An oversized X-Request-ID / CF-Connecting-IP must not fail the INSERT
    # (varchar(64) / varchar(45) columns) or evade the audit row.
    ctx = AuditContext(
        ip_address="x" * 100,
        request_id="y" * 100,
    )
    await audit_service.record(
        db_session,
        action=AuditAction.AUTH_LOGIN,
        ctx=ctx,
        description="login",
    )
    rows = (await db_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 1
    assert rows[0].ip_address == "x" * 45
    assert rows[0].request_id == "y" * 64


def test_request_id_middleware_rejects_malformed_header() -> None:
    import asyncio

    from app.core.request_context import RequestIDMiddleware, get_request_id

    seen: list = []

    async def _run(header_value: str | None):
        app = RequestIDMiddleware(lambda scope, receive, send: _capture(scope, receive, send, seen))
        headers = []
        if header_value is not None:
            headers.append((b"x-request-id", header_value.encode()))
        scope = {
            "type": "http",
            "headers": headers,
            "method": "GET",
            "path": "/",
        }
        sent = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await app(scope, receive, send)
        return sent

    async def _capture(scope, receive, send, seen):
        seen.append(get_request_id())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    asyncio.run(_run("a" * 100))
    # Oversized: replaced with a generated uuid4 hex (32 chars).
    assert len(seen[0]) == 32

    asyncio.run(_run("valid-token_1.x"))
    assert seen[1] == "valid-token_1.x"

    asyncio.run(_run(None))
    assert len(seen[2]) == 32


async def test_record_isolated_never_raises_on_failure(db_session, monkeypatch) -> None:
    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(db_session, "commit", _boom)
    ctx = AuditContext()
    row = await audit_service.record_isolated(
        db_session,
        action=AuditAction.AUTH_LOGIN,
        ctx=ctx,
        description="login",
    )
    assert row is None


def test_record_system_writes_through_injected_factory() -> None:
    committed = []

    class _FakeSession:
        def __init__(self):
            self.added = []

        def add(self, row):
            self.added.append(row)

        async def commit(self):
            committed.extend(self.added)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    factory = lambda: _FakeSession()  # noqa: E731

    row = audit_service.record_system(
        action=audit_service.AuditAction.JOB_REAPED,
        label="job-reaper",
        description="reaped job",
        resource_type="job",
        resource_id=uuid.uuid4(),
        result=AuditResult.FAILURE,
        session_factory=factory,
    )
    assert row is not None
    assert row.actor_type == AuditActorType.SYSTEM.value
    assert row.action == AuditAction.JOB_REAPED.value
    assert committed == [row]


def test_record_system_never_raises_on_failure() -> None:
    def _boom():
        raise RuntimeError("no database")

    row = audit_service.record_system(
        action=audit_service.AuditAction.JOB_FAILED,
        description="task failed",
        session_factory=_boom,
    )
    assert row is None


def test_context_from_request_snapshots_actor() -> None:
    from app.models.user import UserRole

    class _FakeUser:
        id = uuid.uuid4()
        role = UserRole.ADMIN
        email = "admin@example.com"
        display_name = "Admin"

    class _FakeClient:
        host = "203.0.113.7"

    class _FakeRequest:
        headers = {"user-agent": "pytest"}
        client = _FakeClient()

        def url_for(self, *a, **k):  # pragma: no cover - unused
            raise NotImplementedError

    ctx = context_from_request(_FakeRequest(), _FakeUser())
    assert ctx.actor_type == AuditActorType.ADMIN
    assert ctx.actor_email == "admin@example.com"
    assert ctx.actor_display_name == "Admin"
    assert ctx.user_agent == "pytest"
    assert ctx.ip_address == "203.0.113.7"
