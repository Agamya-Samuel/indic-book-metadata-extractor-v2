from __future__ import annotations

import uuid

import pytest

from app.models.metadata import BookMetadata
from app.models.ocr_result import OcrResult
from app.models.page import Page


class TestAdminListBooks:
    async def test_list_books_requires_admin(self, client):
        response = await client.get("/api/admin/books")
        assert response.status_code == 403

    async def test_list_books_empty(self, admin_client):
        response = await admin_client.get("/api/admin/books")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["total_pages"] == 0

    async def test_list_books_with_data(self, admin_client, make_book):
        await make_book(status="awaiting_review")
        await make_book(status="awaiting_review")

        response = await admin_client.get("/api/admin/books")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_list_books_filter_language(self, admin_client, make_book):
        await make_book(language="tel", status="awaiting_review")
        await make_book(language="hin", status="awaiting_review")

        response = await admin_client.get("/api/admin/books?language=tel")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["language"] == "tel"

    async def test_list_books_pagination(self, admin_client, make_book):
        for i in range(5):
            await make_book(status="awaiting_review")

        response = await admin_client.get("/api/admin/books?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5
        assert data["total_pages"] == 3


class TestAdminFilterOptions:
    @pytest.mark.skip(
        reason="Requires PostgreSQL JSONB .astext support (SQLite incompatible). Run against Docker stack for full validation."
    )
    async def test_get_filter_options(self, admin_client, make_book):
        await make_book(language="tel")
        await make_book(language="hin")

        response = await admin_client.get("/api/admin/filters")
        assert response.status_code == 200
        data = response.json()
        assert "tel" in data["languages"]
        assert "hin" in data["languages"]
        assert isinstance(data["statuses"], list)
        assert isinstance(data["genres"], list)
        assert isinstance(data["publishers"], list)


class TestBookDetail:
    async def test_get_book_detail(self, client, make_book_with_pages, db_session):
        book = await make_book_with_pages(selected_pages=[1, 2])
        book_id = uuid.UUID(book["id"])

        from sqlalchemy import select

        pages_result = await db_session.execute(select(Page).where(Page.book_id == book_id))
        pages = pages_result.scalars().all()

        for page in pages:
            ocr = OcrResult(
                page_id=page.id,
                raw_text="OCR text here",
                confidence=88.0,
            )
            db_session.add(ocr)

        await db_session.commit()

        response = await client.get(f"/api/books/{book['id']}/detail")
        assert response.status_code == 200
        data = response.json()
        assert data["book"]["id"] == book["id"]
        assert "pages" not in data
        assert "jobs" not in data
        assert "llm_runs" not in data

        pages_response = await client.get(f"/api/books/{book['id']}/pages?include_ocr=true")
        pages = pages_response.json()["items"]
        assert len(pages) == 2
        assert pages[0]["ocr_text"] == "OCR text here"

    async def test_get_book_detail_not_found(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/books/{fake_id}/detail")
        assert response.status_code == 404

    async def test_get_book_detail_with_metadata(self, client, make_book, db_session):
        book = await make_book()
        book_id = uuid.UUID(book["id"])

        meta = BookMetadata(
            book_id=book_id,
            fields={"title": "Detail Title", "author": "Detail Author"},
        )
        db_session.add(meta)
        await db_session.commit()

        response = await client.get(f"/api/books/{book['id']}/detail")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["title"] == "Detail Title"

    async def test_book_detail_enforces_ownership(self, admin_client, auth_client, create_user, make_book):
        book = await make_book()

        # Admin may read any book's detail.
        assert (await admin_client.get(f"/api/books/{book['id']}/detail")).status_code == 200

        other = await create_user(email="detail-other@example.com")
        other_client = await auth_client(other)
        assert (await other_client.get(f"/api/books/{book['id']}/detail")).status_code == 404


class TestRetiredLibraryRoutes:
    async def test_library_routes_are_gone(self, admin_client):
        assert (await admin_client.get("/api/library/books")).status_code == 404
        assert (await admin_client.get("/api/library/search?q=x")).status_code == 404
        assert (await admin_client.get("/api/library/filters")).status_code == 404
