from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services import storage


class TestStoragePaths:
    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "storage_path", str(tmp_path / "storage"))

    def test_uploads_dir(self):
        result = storage.uploads_dir("book-123")
        assert "uploads" in str(result)
        assert "book-123" in str(result)
        assert result.exists()

    def test_thumbnails_dir(self):
        result = storage.thumbnails_dir("book-123")
        assert "thumbnails" in str(result)
        assert "book-123" in str(result)
        assert result.exists()

    def test_pages_dir(self):
        result = storage.pages_dir("book-123")
        assert "pages" in str(result)
        assert "book-123" in str(result)
        assert result.exists()

    def test_original_pdf_path(self):
        result = storage.original_pdf_path("book-123")
        assert result.name == "original.pdf"

    def test_thumbnail_path(self):
        result = storage.thumbnail_path("book-123", 1)
        assert result.name == "p0001.jpg"

    def test_thumbnail_path_large_number(self):
        result = storage.thumbnail_path("book-123", 999)
        assert result.name == "p0999.jpg"

    def test_full_page_path(self):
        result = storage.full_page_path("book-123", 1)
        assert result.name == "p0001.png"

    def test_processed_dir(self):
        result = storage.processed_dir("book-123")
        assert "processed" in str(result)
        assert result.exists()

    def test_processed_image_path(self):
        result = storage.processed_image_path("book-123", 5)
        assert result.name == "p0005_processed.png"

    def test_relative(self, tmp_path, monkeypatch):
        base = tmp_path / "storage"
        monkeypatch.setattr(settings, "storage_path", str(base))
        full_path = base / "uploads" / "book-123" / "original.pdf"
        result = storage.relative(full_path)
        assert result == str(Path("uploads") / "book-123" / "original.pdf")

    def test_relative_outside_base(self, tmp_path, monkeypatch):
        base = tmp_path / "storage"
        monkeypatch.setattr(settings, "storage_path", str(base))
        outside = tmp_path / "other" / "file.txt"
        result = storage.relative(outside)
        assert result == str(outside)
