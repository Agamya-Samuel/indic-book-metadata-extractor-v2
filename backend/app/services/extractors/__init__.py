"""Hybrid extractors: regex / dictionary / NER / LLM.

The legacy pipeline asked the LLM to do everything. Per chat1's analysis,
that's wrong — many fields are better extracted with deterministic
methods (regex, dictionary lookup, NER) before escalating to the LLM.

Each extractor here returns an ``ExtractedField`` with a value, a
confidence score, the page it came from, the text snippet, and the
extraction method. The ``HybridExtractor`` runs them in priority order
so the LLM is only called for fields the cheap methods can't resolve.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ExtractedField:
    field_name: str
    value: str
    confidence: float  # 0.0 - 1.0
    method: str  # 'regex' | 'dictionary' | 'ner' | 'llm' | 'human'
    source_page_number: int | None = None
    source_text_snippet: str | None = None


def _normalize(s: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace.

    Used for fuzzy matching between predicted and expected values in the
    accuracy harness. Not used by the extractors themselves.
    """
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _snippet(text: str, value: str, context: int = 60) -> str:
    """Return a window of ``text`` around ``value`` for evidence."""
    if not text or not value:
        return text[: context * 2] if text else ""
    idx = text.find(value)
    if idx < 0:
        return text[: context * 2]
    start = max(0, idx - context)
    end = min(len(text), idx + len(value) + context)
    return text[start:end]


# Field → extractor function registry. Each extractor takes the full OCR
# text and the per-page text list, returns ExtractedField | None.
ExtractorFn = Callable[[str, list[tuple[int, str]]], "ExtractedField | None"]
