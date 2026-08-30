"""Tests for the regex/dictionary extractors and the hybrid orchestrator."""

from __future__ import annotations

import pytest

from app.services.extractors import ExtractedField
from app.services.extractors.dictionary_extractors import (
    REGISTRY as DICT_REGISTRY,
    detect_language,
    extract_publisher,
)
from app.services.extractors.hybrid import NON_LLM_FIELDS, run_hybrid_extraction
from app.services.extractors.regex_extractors import (
    REGISTRY as REGEX_REGISTRY,
    extract_isbn,
    extract_pages,
    extract_publication_year,
)


SAMPLE_PAGES = [
    (
        1,
        "Bharat ka Itihas\n"
        "Lekhak: Ram Sharma\n"
        "Prakashak: Rajkamal Prakashan\n"
        "Sankshya: 248\n"
        "ISBN: 978-81-234-5678-9\n"
        "Mulya: ₹250",
    ),
    (
        2,
        "Copyright © 2019 Rajkamal Prakashan\n"
        "First published 2019\n"
        "All rights reserved.",
    ),
    (3, "Dedicated to the people of India."),
    (4, "Chapter 1\n\nItihas ke adhyayan ka mahatva..."),
]


def _pages_text(pages) -> str:
    return "\n\n---\n\n".join(t for _, t in pages)


class TestIsbnExtractor:
    def test_finds_isbn13(self):
        text = _pages_text(SAMPLE_PAGES)
        result = extract_isbn(text, SAMPLE_PAGES)
        assert result is not None
        assert result.field_name == "isbn"
        assert "978-81-234-5678-9" in result.value
        assert result.method == "regex"
        assert result.source_page_number == 1

    def test_no_isbn_returns_none(self):
        text = "just some text without isbn"
        assert extract_isbn(text, [(1, text)]) is None


class TestPublicationYearExtractor:
    def test_picks_most_frequent_year(self):
        text = _pages_text(SAMPLE_PAGES)
        result = extract_publication_year(text, SAMPLE_PAGES)
        assert result is not None
        assert result.field_name == "publication_date"
        assert result.value == "2019"

    def test_no_year_returns_none(self):
        text = "no years here at all"
        assert extract_publication_year(text, [(1, text)]) is None


class TestPagesExtractor:
    def test_finds_page_count(self):
        text = _pages_text(SAMPLE_PAGES)
        result = extract_pages(text, SAMPLE_PAGES)
        assert result is not None
        assert result.field_name == "pages"
        assert result.value == "248"


class TestPublisherExtractor:
    def test_finds_known_publisher(self):
        text = _pages_text(SAMPLE_PAGES)
        result = extract_publisher(text, SAMPLE_PAGES)
        assert result is not None
        assert result.field_name == "publisher"
        assert result.value == "Rajkamal Prakashan"
        assert result.confidence == 0.95

    def test_unknown_publisher_returns_none(self):
        text = "Published by Some Obscure Press 2020"
        assert extract_publisher(text, [(1, text)]) is None


class TestLanguageDetector:
    def test_detects_devanagari_as_hindi(self):
        text = "यह एक हिन्दी पुस्तक है जिसमें बहुत सारे शब्द हैं।"
        result = detect_language(text, [(1, text)])
        assert result is not None
        assert result.field_name == "language"
        assert result.value == "Hindi"

    def test_detects_telugu(self):
        text = "ఇది ఒక తెలుగు పుస్తకం చాలా పదాలతో."
        result = detect_language(text, [(1, text)])
        assert result is not None
        assert result.value == "Telugu"

    def test_detects_english(self):
        text = "This is an English book with many words to determine the language properly."
        result = detect_language(text, [(1, text)])
        assert result is not None
        assert result.value == "English"


class TestHybridOrchestrator:
    async def test_runs_cheap_extractors_and_calls_llm_for_gaps(self):
        llm_calls: list[set[str]] = []

        async def fake_llm(gaps: set[str]) -> dict[str, ExtractedField]:
            llm_calls.append(set(gaps))
            return {
                "title": ExtractedField(
                    field_name="title",
                    value="Bharat ka Itihas",
                    confidence=0.6,
                    method="llm",
                ),
                "author": ExtractedField(
                    field_name="author",
                    value="Ram Sharma",
                    confidence=0.6,
                    method="llm",
                ),
            }

        text = _pages_text(SAMPLE_PAGES)
        target_fields = ["title", "author", "isbn", "pages", "publisher", "language", "publication_date"]
        results = await run_hybrid_extraction(
            text, SAMPLE_PAGES, fake_llm, target_fields=target_fields
        )

        # ISBN, year, pages, publisher, language come from cheap extractors.
        assert "isbn" in results
        assert "publication_date" in results
        assert "pages" in results
        assert "publisher" in results
        assert "language" in results

        # LLM was asked only for the gaps.
        assert len(llm_calls) == 1
        asked = llm_calls[0]
        assert "isbn" not in asked
        assert "publisher" not in asked
        assert "title" in asked
        assert "author" in asked

        # All results are present.
        assert "title" in results
        assert "author" in results

    async def test_no_llm_call_when_cheap_extractors_cover_everything(self):
        llm_calls: list[set[str]] = []

        async def fake_llm(gaps: set[str]) -> dict[str, ExtractedField]:
            llm_calls.append(set(gaps))
            return {}

        # target_fields = only fields the cheap layer handles. No LLM call.
        text = _pages_text(SAMPLE_PAGES)
        target_fields = ["isbn", "publisher", "language", "publication_date", "pages"]
        results = await run_hybrid_extraction(
            text, SAMPLE_PAGES, fake_llm, target_fields=target_fields
        )

        # Cheap layer populated everything; LLM was not called.
        assert "isbn" in results
        assert "publisher" in results
        assert "language" in results
        assert "publication_date" in results
        assert "pages" in results
        assert llm_calls == []


class TestRegistry:
    def test_regex_registry_covers_expected_fields(self):
        assert "isbn" in REGEX_REGISTRY
        assert "publication_date" in REGEX_REGISTRY
        assert "pages" in REGEX_REGISTRY

    def test_dict_registry_covers_expected_fields(self):
        assert "publisher" in DICT_REGISTRY
        assert "language" in DICT_REGISTRY

    def test_non_llm_fields_is_union(self):
        assert "isbn" in NON_LLM_FIELDS
        assert "publisher" in NON_LLM_FIELDS
        assert "language" in NON_LLM_FIELDS
        assert "pages" in NON_LLM_FIELDS
        assert "publication_date" in NON_LLM_FIELDS
        # Field the LLM still has to handle.
        assert "title" not in NON_LLM_FIELDS
        assert "dedication" not in NON_LLM_FIELDS
