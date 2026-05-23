from __future__ import annotations

import io
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.models.base import Base


def create_test_pdf(path: Path, num_pages: int = 2, text_per_page: dict[int, str] | None = None) -> Path:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        text = (text_per_page or {}).get(i, f"Test page {i + 1}")
        page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _patch_jsonb_columns():
    from sqlalchemy.dialects.postgresql import JSONB

    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()
            elif hasattr(column.type, "with_variant"):
                pass


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        yield session


def _create_test_app() -> FastAPI:
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
async def setup_database():
    _patch_jsonb_columns()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture
def test_app(setup_database):
    app = _create_test_app()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def mock_celery():
    with (
        patch("app.tasks.ocr_tasks.run_ocr_for_book") as mock_ocr_task,
        patch("app.tasks.llm_tasks.run_llm_extraction") as mock_llm_task,
    ):
        mock_ocr_task.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
        mock_llm_task.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
        yield {"ocr": mock_ocr_task, "llm": mock_llm_task}


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    return create_test_pdf(tmp_path / "test.pdf", num_pages=3)


@pytest.fixture
def test_storage(tmp_path, monkeypatch):
    storage_path = tmp_path / "storage"
    storage_path.mkdir()
    monkeypatch.setattr(settings, "storage_path", str(storage_path))
    return storage_path


@pytest.fixture
def make_book(client, sample_pdf, test_storage):
    async def _make_book(
        language: str = "tel",
    ) -> dict:
        pdf_bytes = sample_pdf.read_bytes()
        response = await client.post(
            "/api/books/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"language": language},
        )
        assert response.status_code == 201
        return response.json()

    return _make_book


@pytest.fixture
def make_book_with_pages(client, make_book):
    async def _make(selected_pages: list[int] | None = None) -> dict:
        book = await make_book()
        book_id = book["id"]
        pages = selected_pages or [1, 2]
        response = await client.post(
            f"/api/books/{book_id}/pages",
            json={"selected_pages": pages},
        )
        assert response.status_code == 200
        return book

    return _make
