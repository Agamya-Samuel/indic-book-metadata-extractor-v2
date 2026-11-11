from __future__ import annotations

import io
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
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
from app.core.security import create_access_token, hash_password
from app.models.base import Base
from app.models.book import Book
from app.models.user import User, UserRole


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


CSRF_HEADER = "X-CSRF-Token"
_TEST_CSRF = "test-csrf-token"


def _authenticate(ac: AsyncClient, user: User) -> None:
    """Attach session cookies and the CSRF header to a test client."""
    token = create_access_token(
        user_id=str(user.id),
        role=user.role,
        token_version=user.token_version,
    )
    ac.cookies.set("access_token", token)
    ac.cookies.set("csrf_token", _TEST_CSRF)
    ac.headers[CSRF_HEADER] = _TEST_CSRF


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
async def client(test_app, regular_user) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        _authenticate(ac, regular_user)
        yield ac


@pytest.fixture
async def anon_client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
async def admin_client(test_app, admin_user) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        _authenticate(ac, admin_user)
        yield ac


def _user_factory():
    async def _create(
        *,
        email: str | None = None,
        display_name: str = "Test User",
        role: str = UserRole.USER,
        is_active: bool = True,
        verified: bool = True,
        password: str = "correct horse battery staple",
    ) -> User:
        async with TestSessionFactory() as session:
            user = User(
                email=email or f"{uuid.uuid4().hex[:12]}@example.com",
                display_name=display_name,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
                email_verified_at=(
                    datetime.now(timezone.utc) if verified else None
                ),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user

    return _create


@pytest.fixture
def create_user(test_app):
    return _user_factory()


@pytest.fixture
async def regular_user(test_app) -> User:
    return await _user_factory()(
        email="user@example.com", display_name="Regular User"
    )


@pytest.fixture
async def admin_user(test_app) -> User:
    return await _user_factory()(
        email="admin@example.com",
        display_name="Admin User",
        role=UserRole.ADMIN,
    )


@pytest.fixture
async def auth_client(test_app) -> AsyncGenerator:
    """Factory that returns an authenticated client for a given user."""
    clients: list[AsyncClient] = []

    async def _make(user: User) -> AsyncClient:
        transport = ASGITransport(app=test_app)
        ac = AsyncClient(transport=transport, base_url="http://testserver")
        _authenticate(ac, user)
        clients.append(ac)
        return ac

    try:
        yield _make
    finally:
        for ac in clients:
            await ac.aclose()


def _make_celery_mocks():
    """Return a list of (mock, target) tuples for all the Celery tasks the
    API endpoints can dispatch."""
    return [
        ("ocr", "app.tasks.ocr_tasks.run_ocr_for_book"),
        ("preprocess", "app.tasks.ocr_tasks.preprocess_pages_for_book"),
        ("llm", "app.tasks.llm_tasks.run_llm_extraction"),
    ]


@pytest.fixture
def mock_celery():
    mocks = _make_celery_mocks()
    handles = {name: patch(target).__enter__() for name, target in mocks}
    for h in handles.values():
        h.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
    try:
        yield handles
    finally:
        for _, target in mocks:
            patch(target).__exit__(None, None, None)


@pytest.fixture(autouse=True)
def _auto_mock_celery(request):
    """Auto-apply Celery task mocks to every test that does not explicitly
    request ``mock_celery``. Prevents integration tests from trying to reach
    a real broker when the upload handler dispatches the orchestrator.
    """
    if "mock_celery" in request.fixturenames:
        yield
        return

    mocks = _make_celery_mocks()
    handles = [(name, patch(target).__enter__()) for name, target in mocks]
    for _, h in handles:
        h.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
    try:
        yield
    finally:
        for _, target in mocks:
            patch(target).__exit__(None, None, None)


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
        status: str | None = None,
    ) -> dict:
        pdf_bytes = sample_pdf.read_bytes()
        response = await client.post(
            "/api/books/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"language": language},
        )
        assert response.status_code == 201
        book = response.json()
        if status is not None:
            async with TestSessionFactory() as session:
                row = await session.get(Book, uuid.UUID(book["id"]))
                assert row is not None
                row.status = status
                await session.commit()
            book["status"] = status
        return book

    return _make_book


@pytest.fixture
def make_book_with_pages(client, make_book, db_session, sample_pdf, test_storage):
    async def _make(selected_pages: list[int] | None = None) -> dict:
        from app.models.page import Page
        from app.services import pdf_service, preprocessing, storage
        from app.services.stage_manager import StageManager

        book = await make_book()
        book_id = book["id"]
        pages = selected_pages or [1, 2]
        # Page rendering is asynchronous (PAGE_EXTRACTION job) in production;
        # tests seed the rows and images directly so they stay deterministic.
        for page_number in pages:
            output_path = storage.full_page_path(book_id, page_number)
            pdf_service.render_full_page(sample_pdf, page_number, output_path)
            db_session.add(
                Page(
                    book_id=uuid.UUID(book_id),
                    page_number=page_number,
                    image_path=storage.relative(output_path),
                    preprocessing_config=preprocessing.DEFAULT_PREPROCESSING_CONFIG,
                )
            )
        await db_session.commit()

        # Mirror the production end state of the asynchronous render task.
        await StageManager.initiate_stage(
            db_session, uuid.UUID(book_id), "page_selection"
        )
        await StageManager.start_stage(db_session, uuid.UUID(book_id), "page_selection")
        await StageManager.complete_stage(
            db_session, uuid.UUID(book_id), "page_selection"
        )
        await db_session.commit()
        return book

    return _make
