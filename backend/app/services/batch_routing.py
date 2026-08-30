"""Per-batch page routing for the 8 metadata extraction batches.

The 1500-char global OCR cap in LLMService used to feed every batch the
title page only. Fields like dedication, forewords, illustrators, printer,
sponsor, etc. that live on back-matter pages were physically unreachable.

This module splits pages into front / back / middle sections and lets each
batch pull from the section most likely to contain its fields, while still
falling back to a global pool so we never starve a batch entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PageText:
    """Lightweight view of a page's OCR text for routing purposes."""

    page_number: int
    text: str


# Mapping from batch name to which page-position slices to use.
# Each value is a tuple of (start_offset, end_offset) measured from the
# page list, where -1 refers to the last page. A value of (0, -1) means
# "all pages". (0, 3) means "first three pages". (-3, -1) means "last
# three pages". None entries mean "include all pages" (fallback).
BATCH_PAGE_SLICES: dict[str, tuple[int, int | None]] = {
    # Title page, half-title, copyright — these fields live up front.
    "core_identity": (0, 3),
    # Title page + colophon (back). Contributors show up in both places.
    "contributors": (0, 3),
    # Copyright page + colophon. Use an expanded window for both ends.
    "publication": (0, 4),
    # Title page + back cover. Often on cover for popular books.
    "content_classification": (0, 3),
    # Title page + copyright. Edition info is consistent across both.
    "edition_series": (0, 4),
    # Often on colophon / acknowledgements (back-matter).
    "relationships": (0, 5),
    # Dedication + foreword (front-matter), abbreviations/scribes (back).
    "ancillary_content": (0, 5),
    # Anywhere; harvest from full pool last.
    "physical_extra": (0, None),
}


def select_pages_for_batch(
    pages: list[PageText],
    batch_name: str,
) -> list[PageText]:
    """Return the page subset most likely to contain this batch's fields.

    The selection is by *position*, not by content classification. The
    rationale is documented in BATCH_PAGE_SLICES. If the slice is empty
    (book is shorter than the window), we fall back to all pages so
    short books still get coverage.
    """
    if not pages:
        return []

    start, end = BATCH_PAGE_SLICES.get(batch_name, (0, None))

    # Clamp end relative to list length.
    if end is None or end == -1:
        end = len(pages)
    elif end < 0:
        end = max(0, len(pages) + end)
    else:
        end = min(end, len(pages))

    start = max(0, min(start, len(pages)))

    selected = pages[start:end]

    # Fallback: if slice is empty (shouldn't happen given clamping, but
    # be safe), return all pages.
    if not selected:
        return list(pages)

    return selected


def assemble_ocr_text(
    pages: Iterable[PageText],
    max_chars: int,
) -> str:
    """Join the given pages' OCR text with a clear page separator, truncated.

    Each page contributes its full text (subject to a per-page cap so a
    pathological page doesn't dominate the budget). The whole assembly is
    then truncated to ``max_chars`` total.
    """
    parts: list[str] = []
    # Per-page budget: half the total. Within budget, the page is kept whole
    # so we don't break a single field across the truncation boundary.
    per_page_budget = max_chars // 2
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        if len(text) > per_page_budget:
            text = text[:per_page_budget]
        parts.append(f"[Page {page.page_number}]\n{text}")

    joined = "\n\n---\n\n".join(parts)
    if len(joined) > max_chars:
        joined = joined[:max_chars]
    return joined
