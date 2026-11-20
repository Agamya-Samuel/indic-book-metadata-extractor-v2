"""Append-only enforcement on ``audit_logs`` — requires a real Postgres.

The SQLite test suite cannot run the migration's plpgsql trigger, so this test
is skipped unless ``TEST_POSTGRES_URL`` points at a database whose schema has
already been migrated (e.g. a throwaway container from
``scripts/poc-audit-trigger.sh``). It proves that UPDATE, DELETE and TRUNCATE
are all rejected for the application's own role.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(
        not os.environ.get("TEST_POSTGRES_URL"),
        reason="set TEST_POSTGRES_URL to a migrated Postgres to verify the append-only trigger",
    ),
]

_INSERT = text(
    """
    INSERT INTO audit_logs (id, actor_type, action, category, description)
    VALUES (:id, 'system', 'auth.login', 'auth', 'trigger test row')
    """
)


@pytest.fixture
async def pg_session():
    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_update_is_rejected(pg_session) -> None:
    row_id = uuid.uuid4()
    await pg_session.execute(_INSERT, {"id": row_id})
    await pg_session.commit()

    with pytest.raises(Exception) as excinfo:  # noqa: B017 — asyncpg raises its own error
        await pg_session.execute(
            text("UPDATE audit_logs SET description = 'tampered' WHERE id = :id"),
            {"id": row_id},
        )
        await pg_session.commit()
    assert "append-only" in str(excinfo.value)


async def test_delete_is_rejected(pg_session) -> None:
    row_id = uuid.uuid4()
    await pg_session.execute(_INSERT, {"id": row_id})
    await pg_session.commit()

    with pytest.raises(Exception) as excinfo:  # noqa: B017
        await pg_session.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": row_id})
        await pg_session.commit()
    assert "append-only" in str(excinfo.value)


async def test_truncate_is_rejected(pg_session) -> None:
    with pytest.raises(Exception) as excinfo:  # noqa: B017
        await pg_session.execute(text("TRUNCATE audit_logs"))
        await pg_session.commit()
    assert "append-only" in str(excinfo.value)
