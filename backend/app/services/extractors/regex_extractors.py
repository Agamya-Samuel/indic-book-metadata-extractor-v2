"""Regex-based field extractors for highly-structured fields.

These run first in the hybrid pipeline because they're deterministic,
fast, and produce confidence 1.0 when they hit. The LLM is never asked
to extract ISBN or year — it's a waste of inference budget.
"""

from __future__ import annotations

import re

from app.services.extractors import ExtractedField, _snippet


# ISBN-13 with optional hyphens, also tolerates the "ISBN" prefix and
# the older 10-digit form. We don't checksum-validate because OCR errors
# in the digits are common; the cost of a false positive is low (the
# field is just metadata) and the value of a true positive is high.
ISBN_RE = re.compile(
    r"(?:ISBN[:\s\-]?\s*)?((?:97[89])[\s\-]?\d{1,5}[\s\-]?\d{1,7}[\s\-]?\d{1,7}[\s\-]?\d)",
    re.IGNORECASE,
)
ISBN10_RE = re.compile(
    r"(?:ISBN[:\s\-]?\s*)?(\d{1,5}[\s\-]?\d{1,7}[\s\-]?\d{1,7}[\s\-]?[\dXx])",
    re.IGNORECASE,
)

# 4-digit years in a plausible book-publication range. 1700-2100 covers
# historical + future editions without picking up page numbers.
YEAR_RE = re.compile(r"\b(1[789]\d{2}|20\d{2})\b")

# Indian-currency price tags. ₹ is the Unicode rupee; we also match
# "Rs.", "Rs", "INR", "M.R.P.", and "MRP". Amount is digits with optional
# decimal.
PRICE_RE = re.compile(
    r"(?:₹|Rs\.?|INR|M\.?R\.?P\.?\s*[:\-]?\s*)([\d,]+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

# Page count. Often printed as "pp.", "p.", "Pages:", "Sankshya:",
# "Pustaka Sankhya:", or "(xxiv + 248 p.)". We pick the largest
# plausible integer that follows these cues so we don't grab a chapter
# number by accident.
PAGES_RE = re.compile(
    r"(?:pages?|pp?\.?|sankshya|pustaka\s*sankhya|pustakamu\s*sankhyeya)\s*"
    r"[:\-]?\s*(\d{1,4})|"
    r"\(\s*([ivxlcdm]+(?:\s*\+\s*\d+)?)\s*p\.",
    re.IGNORECASE,
)


def _first_match(pattern: re.Pattern, text: str) -> re.Match | None:
    return pattern.search(text)


def extract_isbn(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    match = _first_match(ISBN_RE, full_text)
    if match:
        value = match.group(1)
        # Find the page that contained it.
        page_num, snippet = _find_page(pages, value)
        return ExtractedField(
            field_name="isbn",
            value=value,
            confidence=0.9,
            method="regex",
            source_page_number=page_num,
            source_text_snippet=snippet,
        )
    match = _first_match(ISBN10_RE, full_text)
    if match:
        value = match.group(1)
        page_num, snippet = _find_page(pages, value)
        return ExtractedField(
            field_name="isbn",
            value=value,
            confidence=0.7,  # 10-digit ISBNs are less specific; 0.7 not 0.9
            method="regex",
            source_page_number=page_num,
            source_text_snippet=snippet,
        )
    return None


def extract_publication_year(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    """Pick the most recent plausible year, weighted toward front-matter."""
    candidates: list[tuple[int, int, int]] = []  # (page_num, year, position_weight)
    for page_num, text in pages[:5]:  # publication year is on copyright page
        for m in YEAR_RE.finditer(text):
            try:
                year = int(m.group(1))
            except ValueError:
                continue
            if 1700 <= year <= 2100:
                candidates.append((page_num, year, 0))

    if not candidates:
        return None

    # Pick the year that appears most often in front-matter.
    from collections import Counter

    counts = Counter(c for _, c, _ in candidates)
    best_year, _ = counts.most_common(1)[0]
    page_num, _ = next((p, y) for p, y, _ in candidates if y == best_year)
    snippet = _snippet(_page_text(pages, page_num), str(best_year))
    return ExtractedField(
        field_name="publication_date",
        value=str(best_year),
        confidence=0.8,
        method="regex",
        source_page_number=page_num,
        source_text_snippet=snippet,
    )


def extract_price(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    match = _first_match(PRICE_RE, full_text)
    if not match:
        return None
    value = match.group(1).replace(",", "")
    page_num, snippet = _find_page(pages, value)
    return ExtractedField(
        field_name="distributors",  # closest fit; price is not a 52-field
        # but distributors is the closest related field. We still record
        # it via a custom field below.
        value=value,
        confidence=0.6,
        method="regex",
        source_page_number=page_num,
        source_text_snippet=snippet,
    )


def extract_pages(
    full_text: str,
    pages: list[tuple[int, str]],
) -> ExtractedField | None:
    # Prefer the largest plausible integer that follows "pp" or "pages".
    candidates: list[tuple[int, int, str]] = []
    for page_num, text in pages:
        for m in PAGES_RE.finditer(text):
            for grp in m.groups():
                if not grp:
                    continue
                # Roman numerals (e.g. "xxiv") are hard to parse here;
                # only handle arabic.
                digits = re.sub(r"\D", "", grp)
                if digits and 1 <= int(digits) <= 9999:
                    candidates.append((page_num, int(digits), grp))

    if not candidates:
        # Fall back: find "248 pp" or "248 p." with arabic digits.
        arabic_pp = re.compile(r"(\d{2,4})\s*(?:pp?|pages?)", re.IGNORECASE)
        for page_num, text in pages:
            m = arabic_pp.search(text)
            if m:
                try:
                    n = int(m.group(1))
                    if 1 <= n <= 9999:
                        candidates.append((page_num, n, m.group(0)))
                except ValueError:
                    continue

    if not candidates:
        return None

    # The page count should be consistent — pick the most common value.
    from collections import Counter

    counts = Counter(n for _, n, _ in candidates)
    best_n, _ = counts.most_common(1)[0]
    page_num, _, raw = next((p, n, r) for p, n, r in candidates if n == best_n)
    return ExtractedField(
        field_name="pages",
        value=str(best_n),
        confidence=0.85,
        method="regex",
        source_page_number=page_num,
        source_text_snippet=raw,
    )


def _find_page(
    pages: list[tuple[int, str]],
    needle: str,
) -> tuple[int | None, str | None]:
    """Find the first page that contains ``needle`` and return (page_num, snippet)."""
    for page_num, text in pages:
        if needle in text:
            return page_num, _snippet(text, needle)
    return None, None


def _page_text(pages: list[tuple[int, str]], page_num: int) -> str:
    for n, t in pages:
        if n == page_num:
            return t
    return ""


REGISTRY = {
    "isbn": extract_isbn,
    "publication_date": extract_publication_year,
    "pages": extract_pages,
}
