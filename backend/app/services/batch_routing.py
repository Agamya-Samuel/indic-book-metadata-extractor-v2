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
#
# ``relationships`` is widened so short books pick up colophon pages in
# their initial slice; longer books reach the colophon via BACK_MATTER_SLICES.
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
    # Title page + colophon (back). Use a wider front window so the
    # ``first_published_in`` colophon entry is reachable.
    "relationships": (0, 8),
    # Dedication + foreword (front-matter), abbreviations/scribes (back).
    "ancillary_content": (0, 5),
    # Anywhere; harvest from full pool last.
    "physical_extra": (0, None),
}

# Optional back-matter windows applied as a *union* to certain batches so
# that fields living exclusively on the colophon (last 1-3 pages) are
# reachable.
BACK_MATTER_SLICES: dict[str, tuple[int, int | None]] = {
    "relationships": (-3, None),
    "publication": (-3, None),
    "edition_series": (-3, None),
    "ancillary_content": (-3, None),
}


def _resolve_slice(slice_: tuple[int, int | None], length: int) -> tuple[int, int]:
    """Convert a logical slice ``(start, end)`` into absolute ``[start, end)``.

    Convention (matches :data:`BATCH_PAGE_SLICES`):
      - ``None`` or ``-1`` end → use ``length``
      - negative end → count from the end (``-1`` is the last element)
      - negative start → count from the end too
      - values are then clamped to ``[0, length]``.
    """
    start, end = slice_
    if end is None or end == -1:
        end = length
    elif end < 0:
        end = max(0, length + end)
    else:
        end = min(end, length)
    if start < 0:
        start = max(0, length + start)
    else:
        start = min(start, length)
    return start, end


def select_pages_for_batch(
    pages: list[PageText],
    batch_name: str,
) -> list[PageText]:
    """Return the page subset most likely to contain this batch's fields.

    Selection is by *position*, not by content classification. If the
    front-matter slice is empty (book is shorter than the window), we
    fall back to all pages. Back-matter slices from BACK_MATTER_SLICES
    are unioned in to reach colophon content.
    """
    if not pages:
        return []

    front = BATCH_PAGE_SLICES.get(batch_name, (0, None))
    start, end = _resolve_slice(front, len(pages))
    front_selected = list(pages[start:end])

    back: list[PageText] = []
    back_slice = BACK_MATTER_SLICES.get(batch_name)
    if back_slice is not None:
        b_start, b_end = _resolve_slice(back_slice, len(pages))
        # Dedupe against front_selected via page_number identity.
        seen = {p.page_number for p in front_selected}
        for p in pages[b_start:b_end]:
            if p.page_number not in seen:
                back.append(p)
                seen.add(p.page_number)

    selected = front_selected + back

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
    then truncated to ``max_chars`` total at the nearest whitespace so we
    don't chop the last word of a page.
    """
    pages_list = list(pages)
    parts: list[str] = []
    # Per-page budget: total / page_count so a 10-page batch budget of
    # 2500 chars gives each page ~250 chars instead of shrinking toward 0.
    per_page_budget = max_chars // max(1, len(pages_list))
    for page in pages_list:
        text = page.text.strip()
        if not text:
            continue
        if len(text) > per_page_budget:
            text = text[:per_page_budget]
        parts.append(f"[Page {page.page_number}]\n{text}")

    joined = "\n\n---\n\n".join(parts)
    if len(joined) > max_chars:
        # Round down to a whitespace boundary so we don't chop the last
        # word of a page. Keep a "..." marker so the LLM knows the text
        # was truncated.
        head = joined[: max_chars - 4]
        last_ws = max(head.rfind("\n"), head.rfind(" "))
        if last_ws > max_chars // 2:
            joined = head[:last_ws].rstrip() + " ..."
        else:
            joined = head + " ..."
    return joined
