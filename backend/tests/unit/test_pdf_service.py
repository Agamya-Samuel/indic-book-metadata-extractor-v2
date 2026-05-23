from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.services.pdf_service import get_page_count, render_full_page, render_thumbnail


def _create_pdf(path: Path, num_pages: int = 3) -> Path:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1}")
    doc.save(str(path))
    doc.close()
    return path


class TestGetPageCount:
    def test_correct_count(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=3)
        assert get_page_count(pdf) == 3

    def test_single_page(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=1)
        assert get_page_count(pdf) == 1

    def test_five_pages(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=5)
        assert get_page_count(pdf) == 5


class TestRenderThumbnail:
    def test_creates_file(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        out = tmp_path / "thumb.jpg"
        render_thumbnail(pdf, 1, out)
        assert out.exists()

    def test_file_is_image(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        out = tmp_path / "thumb.jpg"
        render_thumbnail(pdf, 1, out)
        assert out.stat().st_size > 0

    def test_page_2(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=3)
        out = tmp_path / "thumb_p2.jpg"
        render_thumbnail(pdf, 2, out)
        assert out.exists()

    def test_creates_parent_dirs(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        out = tmp_path / "nested" / "dir" / "thumb.jpg"
        render_thumbnail(pdf, 1, out)
        assert out.exists()


class TestRenderFullPage:
    def test_creates_file(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        out = tmp_path / "full.png"
        render_full_page(pdf, 1, out, dpi=150)
        assert out.exists()

    def test_different_dpi_sizes(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        low = tmp_path / "low.png"
        high = tmp_path / "high.png"
        render_full_page(pdf, 1, low, dpi=72)
        render_full_page(pdf, 1, high, dpi=300)
        assert high.stat().st_size > low.stat().st_size

    def test_creates_parent_dirs(self, tmp_path):
        pdf = _create_pdf(tmp_path / "test.pdf", num_pages=2)
        out = tmp_path / "deep" / "nested" / "page.png"
        render_full_page(pdf, 1, out)
        assert out.exists()
