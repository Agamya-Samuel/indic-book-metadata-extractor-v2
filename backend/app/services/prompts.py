from __future__ import annotations

from jinja2 import Template

from app.schemas.metadata import (
    METADATA_BATCHES,
    FIELD_DISPLAY_NAMES,
)

LANGUAGE_NAMES: dict[str, str] = {
    "tel": "Telugu",
    "hin": "Hindi",
    "tam": "Tamil",
    "kan": "Kannada",
    "mal": "Malayalam",
    "mar": "Marathi",
    "ben": "Bengali",
    "guj": "Gujarati",
    "pan": "Punjabi",
    "ori": "Odia",
    "eng": "English",
}

SYSTEM_PROMPT_TEMPLATE = Template(
    """You are an expert bibliographic metadata extractor specializing in {{ language_name }} language books.
You will be given OCR-extracted text from scanned book pages. The text may contain OCR errors — use your knowledge of {{ language_name }} to interpret corrupted words.
Extract the requested metadata fields as accurately as possible from the provided text.
If a field cannot be determined from the text, return null for that field.
Always respond with valid JSON matching the exact schema provided. Do not include any text outside the JSON object."""
)

EXTRACTION_PROMPT_TEMPLATE = Template(
    """Extract the following metadata fields from this {{ language_name }} book text.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

OCR Text (from {{ page_count }} pages of a scanned book):
---
{{ ocr_text }}
---

Respond with a JSON object containing exactly these fields. Use null for fields not found in the text.
Do not include any explanation or text outside the JSON object."""
)


def get_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code)


def render_system_prompt(
    language: str,
    override: str | None = None,
) -> str:
    if override:
        return override
    return SYSTEM_PROMPT_TEMPLATE.render(
        language_name=get_language_name(language),
    )


def render_extraction_prompt(
    batch_name: str,
    ocr_text: str,
    language: str,
    page_count: int = 1,
    override: str | None = None,
) -> str:
    if override:
        template = Template(override)
    else:
        template = EXTRACTION_PROMPT_TEMPLATE

    batch_cls = METADATA_BATCHES.get(batch_name)
    if batch_cls is None:
        raise ValueError(f"Unknown batch: {batch_name}")

    fields = []
    for field_name, field_info in batch_cls.model_fields.items():
        if field_name == "custom_fields":
            continue
        fields.append(
            {
                "name": field_name,
                "description": FIELD_DISPLAY_NAMES.get(field_name, field_name),
            }
        )

    return template.render(
        language_name=get_language_name(language),
        fields=fields,
        ocr_text=ocr_text,
        page_count=page_count,
    )


def get_batch_field_names(batch_name: str) -> list[str]:
    batch_cls = METADATA_BATCHES.get(batch_name)
    if batch_cls is None:
        raise ValueError(f"Unknown batch: {batch_name}")
    return [f for f in batch_cls.model_fields if f != "custom_fields"]
