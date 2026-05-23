from __future__ import annotations

import pytest

from app.schemas.metadata import (
    METADATA_BATCHES,
    BATCH_FIELD_ORDER,
    FIELD_DISPLAY_NAMES,
    FIELD_TO_BATCH,
    FIELD_WIKIDATA,
    FullMetadata,
)
from app.services.prompts import (
    get_batch_field_names,
    get_language_name,
    render_extraction_prompt,
    render_system_prompt,
)


class TestGetLanguageName:
    def test_telugu(self):
        assert get_language_name("tel") == "Telugu"

    def test_hindi(self):
        assert get_language_name("hin") == "Hindi"

    def test_english(self):
        assert get_language_name("eng") == "English"

    def test_unknown(self):
        assert get_language_name("xyz") == "xyz"


class TestRenderSystemPrompt:
    def test_telugu(self):
        result = render_system_prompt("tel")
        assert "Telugu" in result
        assert "metadata" in result.lower()

    def test_hindi(self):
        result = render_system_prompt("hin")
        assert "Hindi" in result

    def test_override(self):
        result = render_system_prompt("tel", override="Custom system prompt")
        assert result == "Custom system prompt"


class TestRenderExtractionPrompt:
    def test_core_identity(self):
        result = render_extraction_prompt(
            batch_name="core_identity",
            ocr_text="sample OCR text",
            language="tel",
        )
        assert "sample OCR text" in result
        assert "Telugu" in result
        assert "title" in result.lower() or "Title" in result
        assert "author" in result.lower() or "Author" in result

    def test_override_template(self):
        result = render_extraction_prompt(
            batch_name="core_identity",
            ocr_text="OCR",
            language="tel",
            override="Custom {{ language_name }} template with {{ ocr_text }}",
        )
        assert "Custom Telugu" in result
        assert "OCR" in result

    def test_unknown_batch_raises(self):
        with pytest.raises(ValueError, match="Unknown batch"):
            render_extraction_prompt(
                batch_name="nonexistent",
                ocr_text="text",
                language="tel",
            )

    def test_page_count_in_prompt(self):
        result = render_extraction_prompt(
            batch_name="publication",
            ocr_text="text",
            language="tel",
            page_count=5,
        )
        assert "5 pages" in result

    def test_publication_batch(self):
        result = render_extraction_prompt(
            batch_name="publication",
            ocr_text="pub text",
            language="hin",
        )
        assert "Hindi" in result
        assert "publisher" in result.lower() or "Publisher" in result


class TestGetBatchFieldNames:
    def test_core_identity(self):
        names = get_batch_field_names("core_identity")
        assert "title" in names
        assert "author" in names
        assert "isbn" in names

    def test_excludes_custom_fields(self):
        names = get_batch_field_names("physical_extra")
        assert "custom_fields" not in names

    def test_unknown_batch_raises(self):
        with pytest.raises(ValueError, match="Unknown batch"):
            get_batch_field_names("nonexistent")
