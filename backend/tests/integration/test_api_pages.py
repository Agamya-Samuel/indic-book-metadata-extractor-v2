from __future__ import annotations

import uuid

import pytest

from app.models.job import Job, JobStatus, JobType
from app.models.ocr_result import OcrResult
from app.models.page import Page


class TestUpdatePreprocessing:
    async def test_update_preprocessing(self, client, make_book_with_pages, db_session):
        book = await make_book_with_pages()
        book_id = book["id"]

        pages_resp = await client.get(f"/api/books/{book_id}/pages")
        page_id = pages_resp.json()[0]["id"]

        response = await client.put(
            f"/api/pages/{page_id}/preprocessing",
            json={
                "grayscale": True,
                "brightness": 20,
                "contrast": 10,
                "binarization": "otsu",
                "deskew": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["config_applied"]["grayscale"] is True
        assert data["config_applied"]["brightness"] == 20
        assert "processed_image_url" in data

    async def test_update_preprocessing_saves_config(self, client, make_book_with_pages, db_session):
        book = await make_book_with_pages()
        book_id = book["id"]

        pages_resp = await client.get(f"/api/books/{book_id}/pages")
        page_id = pages_resp.json()[0]["id"]

        await client.put(
            f"/api/pages/{page_id}/preprocessing",
            json={"grayscale": False, "deskew": True},
        )

        from sqlalchemy import select
        result = await db_session.execute(select(Page).where(Page.id == uuid.UUID(page_id)))
        page = result.scalar_one()
        assert page.preprocessing_config is not None
        assert page.preprocessing_config["grayscale"] is False


class TestGetPageImage:
    async def test_get_page_image_original(self, client, make_book_with_pages):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        response = await client.get(f"/api/pages/{page_id}/image")
        assert response.status_code == 200

    async def test_get_page_image_processed(self, client, make_book_with_pages):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        await client.put(
            f"/api/pages/{page_id}/preprocessing",
            json={"grayscale": True},
        )

        response = await client.get(f"/api/pages/{page_id}/image")
        assert response.status_code == 200

    async def test_get_page_image_not_found(self, client, db_session):
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/pages/{fake_id}/image")
        assert response.status_code == 404


class TestGetOcrResult:
    async def test_get_ocr_not_found(self, client, make_book_with_pages):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        response = await client.get(f"/api/pages/{page_id}/ocr")
        assert response.status_code == 404

    async def test_get_ocr_result_with_data(self, client, make_book_with_pages, db_session):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        ocr = OcrResult(
            page_id=uuid.UUID(page_id),
            raw_text="sample OCR text",
            bounding_boxes={"words": [{"text": "sample", "confidence": 90, "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}, "block_num": 1, "line_num": 1, "word_num": 1}]},
            confidence=90.0,
            language_detected="tel",
        )
        db_session.add(ocr)
        await db_session.commit()

        response = await client.get(f"/api/pages/{page_id}/ocr")
        assert response.status_code == 200
        data = response.json()
        assert data["raw_text"] == "sample OCR text"
        assert data["confidence"] == 90.0
        assert len(data["bounding_boxes"]) == 1


class TestUpdateOcrCorrection:
    async def test_update_correction(self, client, make_book_with_pages, db_session):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        ocr = OcrResult(
            page_id=uuid.UUID(page_id),
            raw_text="original text",
            confidence=80.0,
        )
        db_session.add(ocr)
        await db_session.commit()

        response = await client.put(
            f"/api/pages/{page_id}/ocr",
            json={"corrected_text": "corrected text"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["corrected_text"] == "corrected text"
        assert data["raw_text"] == "original text"

    async def test_update_correction_not_found(self, client, make_book_with_pages):
        book = await make_book_with_pages()
        pages_resp = await client.get(f"/api/books/{book['id']}/pages")
        page_id = pages_resp.json()[0]["id"]

        response = await client.put(
            f"/api/pages/{page_id}/ocr",
            json={"corrected_text": "text"},
        )
        assert response.status_code == 404
