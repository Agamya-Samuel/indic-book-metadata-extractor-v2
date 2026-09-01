"""Tests for batch_routing and page_classifier."""

from __future__ import annotations

import pytest

from app.services.batch_routing import (
    BATCH_PAGE_SLICES,
    PageText,
    assemble_ocr_text,
    select_pages_for_batch,
)


def _pages(n: int) -> list[PageText]:
    return [PageText(page_number=i + 1, text=f"page {i+1} content") for i in range(n)]


class TestSelectPagesForBatch:
    def test_core_identity_takes_first_three(self):
        result = select_pages_for_batch(_pages(10), "core_identity")
        assert [p.page_number for p in result] == [1, 2, 3]

    def test_ancillary_content_takes_first_five_plus_back_matter(self):
        result = select_pages_for_batch(_pages(10), "ancillary_content")
        # Front slice 1..5 plus back-matter pages 8..10.
        assert [p.page_number for p in result] == [1, 2, 3, 4, 5, 8, 9, 10]

    def test_relationships_unions_back_matter(self):
        result = select_pages_for_batch(_pages(10), "relationships")
        # Front slice (0, 8) → pages 1..8, back slice (-3, None) →
        # 8,9,10 (deduped against the front window).
        assert [p.page_number for p in result] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    def test_physical_extra_takes_all(self):
        result = select_pages_for_batch(_pages(5), "physical_extra")
        assert [p.page_number for p in result] == [1, 2, 3, 4, 5]

    def test_short_book_falls_back_to_all(self):
        # Book has only 2 pages but the slice wants 3.
        result = select_pages_for_batch(_pages(2), "core_identity")
        assert [p.page_number for p in result] == [1, 2]

    def test_empty_pages_returns_empty(self):
        assert select_pages_for_batch([], "core_identity") == []

    def test_unknown_batch_defaults_to_all(self):
        result = select_pages_for_batch(_pages(3), "nonexistent_batch")
        assert [p.page_number for p in result] == [1, 2, 3]

    def test_all_eight_batches_have_a_slice(self):
        """Sanity check: every batch has a routing rule."""
        for batch_name in [
            "core_identity",
            "contributors",
            "publication",
            "content_classification",
            "edition_series",
            "relationships",
            "ancillary_content",
            "physical_extra",
        ]:
            assert batch_name in BATCH_PAGE_SLICES


class TestAssembleOcrText:
    def test_joins_pages_with_separator(self):
        pages = [PageText(page_number=1, text="AAA"), PageText(page_number=2, text="BBB")]
        text = assemble_ocr_text(pages, max_chars=1000)
        assert "[Page 1]" in text
        assert "[Page 2]" in text
        assert "AAA" in text
        assert "BBB" in text

    def test_truncates_to_max_chars(self):
        pages = [PageText(page_number=1, text="X" * 5000), PageText(page_number=2, text="Y" * 5000)]
        text = assemble_ocr_text(pages, max_chars=1000)
        assert len(text) <= 1000

    def test_skips_empty_pages(self):
        pages = [
            PageText(page_number=1, text="AAA"),
            PageText(page_number=2, text=""),
            PageText(page_number=3, text="CCC"),
        ]
        text = assemble_ocr_text(pages, max_chars=1000)
        assert "AAA" in text
        assert "CCC" in text
        assert "[Page 2]" not in text

    def test_caps_individual_page_text(self):
        # A single very long page should be cut to per-page budget.
        long = "Z" * 10000
        pages = [PageText(page_number=1, text=long)]
        text = assemble_ocr_text(pages, max_chars=4000)
        assert len(text) <= 4000
