"""Shared pagination envelope across list endpoints."""

from __future__ import annotations

import uuid


class TestBookPagesPagination:
    async def test_slices_items(self, client, make_book_with_pages):
        book = await make_book_with_pages(selected_pages=[1, 2, 3])

        response = await client.get(f"/api/books/{book['id']}/pages?page=2&page_size=1")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 2
        assert data["page_size"] == 1
        assert data["total_pages"] == 3
        assert [p["page_number"] for p in data["items"]] == [2]

    async def test_out_of_range_page_is_empty(self, client, make_book_with_pages):
        book = await make_book_with_pages(selected_pages=[1, 2, 3])

        response = await client.get(f"/api/books/{book['id']}/pages?page=99&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 3

    async def test_page_size_bounds(self, client, make_book_with_pages):
        book = await make_book_with_pages()

        assert (await client.get(f"/api/books/{book['id']}/pages?page_size=0")).status_code == 422
        assert (await client.get(f"/api/books/{book['id']}/pages?page_size=101")).status_code == 422


class TestOtherCollections:
    async def test_jobs_envelope(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_pages"] == 0

    async def test_stages_envelope(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/stages")
        assert response.status_code == 200
        data = response.json()
        assert {"items", "total", "page", "page_size", "total_pages"} <= set(data)
        assert data["total"] >= 1

    async def test_metadata_fields_envelope(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/metadata/fields?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] > 10
        assert data["total_pages"] > 1

    async def test_metadata_evidence_envelope(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/metadata/evidence")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_llm_runs_envelope(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/llm-runs")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total_pages"] == 0


class TestAdminJobsEnvelope:
    async def test_admin_jobs_page_size_cap(self, admin_client):
        response = await admin_client.get("/api/admin/jobs?page_size=201")
        assert response.status_code == 422

    async def test_admin_jobs_envelope(self, admin_client):
        response = await admin_client.get("/api/admin/jobs")
        assert response.status_code == 200
        data = response.json()
        assert {"items", "total", "page", "page_size", "total_pages"} <= set(data)


class TestJobById:
    async def test_owner_can_fetch_job(self, client, make_book_with_pages, mock_celery):
        book = await make_book_with_pages()
        created = (await client.post(f"/api/books/{book['id']}/run-ocr")).json()

        response = await client.get(f"/api/jobs/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    async def test_unknown_job_returns_404(self, client):
        response = await client.get(f"/api/jobs/{uuid.uuid4()}")
        assert response.status_code == 404
