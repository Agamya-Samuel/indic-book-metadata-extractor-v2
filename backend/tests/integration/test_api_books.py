from __future__ import annotations

import io
import uuid

import pytest


class TestUploadBook:
    async def test_upload_book_success(self, client, sample_pdf, test_storage):
        pdf_bytes = sample_pdf.read_bytes()
        response = await client.post(
            "/api/books/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"language": "tel"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.pdf"
        assert data["language"] == "tel"
        assert data["status"] == "uploaded"
        assert data["total_pages"] == 3
        assert "id" in data

    async def test_upload_book_with_hindi(self, client, sample_pdf, test_storage):
        pdf_bytes = sample_pdf.read_bytes()
        response = await client.post(
            "/api/books/upload",
            files={"file": ("hindi.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"language": "hin"},
        )
        assert response.status_code == 201
        assert response.json()["language"] == "hin"

    async def test_upload_non_pdf_rejected(self, client, test_storage):
        response = await client.post(
            "/api/books/upload",
            files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        )
        assert response.status_code == 400

    async def test_upload_invalid_language(self, client, sample_pdf, test_storage):
        pdf_bytes = sample_pdf.read_bytes()
        response = await client.post(
            "/api/books/upload",
            files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"language": "fra"},
        )
        assert response.status_code == 422

    async def test_upload_corrupted_pdf(self, client, test_storage):
        response = await client.post(
            "/api/books/upload",
            files={"file": ("bad.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
        )
        assert response.status_code == 400


class TestGetBook:
    async def test_get_book_success(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == book["id"]

    async def test_get_book_not_found(self, client):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/books/{fake_id}")
        assert response.status_code == 404


class TestSelectPages:
    async def test_select_pages_success(self, client, make_book):
        book = await make_book()
        response = await client.post(
            f"/api/books/{book['id']}/pages",
            json={"selected_pages": [1, 3]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["selected_count"] == 2
        assert data["status"] == "pages_selected"

    async def test_select_pages_out_of_range(self, client, make_book):
        book = await make_book()
        response = await client.post(
            f"/api/books/{book['id']}/pages",
            json={"selected_pages": [1, 999]},
        )
        assert response.status_code == 422

    async def test_select_pages_empty(self, client, make_book):
        book = await make_book()
        response = await client.post(
            f"/api/books/{book['id']}/pages",
            json={"selected_pages": []},
        )
        assert response.status_code == 422

    async def test_select_pages_duplicate_deduped(self, client, make_book):
        book = await make_book()
        response = await client.post(
            f"/api/books/{book['id']}/pages",
            json={"selected_pages": [1, 1, 2]},
        )
        assert response.status_code == 200
        assert response.json()["selected_count"] == 2


class TestListPages:
    async def test_list_pages(self, client, make_book_with_pages):
        book = await make_book_with_pages(selected_pages=[1, 3])
        response = await client.get(f"/api/books/{book['id']}/pages")
        assert response.status_code == 200
        pages = response.json()
        assert len(pages) == 2
        assert pages[0]["page_number"] == 1
        assert pages[1]["page_number"] == 3


class TestThumbnail:
    async def test_get_thumbnail_success(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/pages/1/thumbnail")
        assert response.status_code == 200

    async def test_get_thumbnail_out_of_range(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/pages/999/thumbnail")
        assert response.status_code == 404


class TestRunOcr:
    async def test_run_ocr_dispatch(self, client, make_book_with_pages, mock_celery):
        book = await make_book_with_pages()
        response = await client.post(f"/api/books/{book['id']}/run-ocr")
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_type"] == "ocr"
        # The endpoint dispatches preprocess_pages_for_book, which chains
        # into run_ocr_for_book.
        mock_celery["preprocess"].delay.assert_called_once()

    async def test_run_ocr_wrong_status(self, client, make_book, mock_celery):
        book = await make_book()
        response = await client.post(f"/api/books/{book['id']}/run-ocr")
        assert response.status_code == 400


class TestOcrStatus:
    async def test_get_ocr_status_initial(self, client, make_book_with_pages):
        book = await make_book_with_pages()
        response = await client.get(f"/api/books/{book['id']}/ocr-status")
        assert response.status_code == 200
        data = response.json()
        assert data["total_pages"] == 2
        assert data["ocr_complete_count"] == 0
        assert data["ocr_pending_count"] == 2


class TestListJobs:
    async def test_list_jobs_empty(self, client, make_book):
        book = await make_book()
        response = await client.get(f"/api/books/{book['id']}/jobs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_jobs_after_ocr(self, client, make_book_with_pages, mock_celery):
        book = await make_book_with_pages()
        await client.post(f"/api/books/{book['id']}/run-ocr")
        response = await client.get(f"/api/books/{book['id']}/jobs")
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["job_type"] == "ocr"
