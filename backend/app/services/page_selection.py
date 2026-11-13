"""Choose which OCR'd pages to treat as bibliographic front/back matter.

Feeding body-text pages into the extraction prompt adds OCR noise, so a book's
metadata window should be the pages that actually hold title/copyright/colophon
matter, not "the first N and last M". ``select_pages`` implements the strategies
the page-detector POC compares, so the POC and the fill share one definition.
"""

from __future__ import annotations

import re

CUE = re.compile(
    r"(ప్రచురణ|ముద్రా|సంవత్సర|ప్రకాశక|प्रकाशक|मुद्र|©|\(c\)|copyright|isbn|press|printed|publisher|registered)",
    re.IGNORECASE,
)


def is_body_page(text: str) -> bool:
    """True if the page looks like running body content rather than front/back matter."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return len(text) > 1200 and len(lines) > 14 and not CUE.search(text)


def select_pages(
    total: int,
    page_text: dict[int, str],
    strategy: str = "heuristic",
    front: int = 6,
    back: int = 2,
) -> list[int]:
    """Return the pages to keep, from the pages we have text for (``page_text``)."""
    order = sorted(p for p in page_text if 1 <= p <= total)
    if strategy == "fixed":
        return [p for p in order if p <= front or p > total - back]

    if strategy != "heuristic":
        raise ValueError(f"unknown strategy: {strategy}")

    picked: list[int] = []
    for p in order:  # front: keep until a body page, then stop
        if is_body_page(page_text[p]):
            break
        if page_text[p].strip():
            picked.append(p)
    for p in reversed(order):  # back: keep from the end until a body page
        if p in picked:
            continue
        if is_body_page(page_text[p]):
            break
        if page_text[p].strip():
            picked.append(p)
    return sorted(set(picked))