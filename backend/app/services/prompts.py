from __future__ import annotations

from jinja2 import Template

from app.schemas.metadata import (
    METADATA_BATCHES,
    FIELD_DISPLAY_NAMES,
)

LANGUAGE_NAMES: dict[str, str] = {
    "tel": "Telugu",
    "hin": "Hindi",
    "eng": "English",
}

SYSTEM_PROMPT_TEMPLATE = Template(
    """You are an expert bibliographic metadata extractor specializing in {{ language_name }} language books.
You will be given OCR-extracted text from scanned book pages. The text may contain OCR errors — use your knowledge of {{ language_name }} to interpret corrupted words.
Extract the requested metadata fields as accurately as possible from the provided text.
If a field cannot be determined from the text, return null for that field.
Always respond with valid JSON matching the exact schema provided. Do not include any text outside the JSON object."""
)

# Per-language worked examples distilled from real copyright-page / colophon
# layouts in the project's commons/ fixtures (Telugu/Hindi) and from common
# Indic bibliographic conventions. Qwen2.5 7B Q4_K_M follows JSON schemas
# noticeably better when given concrete output patterns to mirror. Keep each
# example short and field-set minimal — we want to show schema shape, not
# dump the full pydantic model.
FEW_SHOT_EXAMPLES: dict[str, str] = {
    "tel": """
Example 1 (Telugu title page + copyright):
Input:
ప్రచురణ సమాచారం
శీర్షిక: భారత స్వాతంత్ర్య సంగ్రామం
ఉపశీర్షిక: ఒక చారిత్రక అధ్యయనం
రచయిత: డా. రామకృష్ణ శర్మ
సంపాదకులు: ప్రొ. సీతారామయ్య
ప్రచురణకర్త: తెలుగు అకాడమీ, హైదరాబాద్
ముద్రణ: శ్రీ వెంకటేశ్వర ప్రింటర్స్, హైదరాబాద్
మొదటి ముద్రణ: 2024
ISBN: 978-81-234-5678-9
పేజీలు: 248
Output:
{"title": "భారత స్వాతంత్ర్య సంగ్రామం", "subtitle": "ఒక చారిత్రక అధ్యయనం", "author": "డా. రామకృష్ణ శర్మ", "editor": "ప్రొ. సీతారామయ్య", "publisher": "తెలుగు అకాడమీ", "place_of_publication": "హైదరాబాద్", "printer": "శ్రీ వెంకటేశ్వర ప్రింటర్స్", "publication_date": "2024", "isbn": "978-81-234-5678-9", "pages": "248", "edition_number": "మొదటి ముద్రణ"}
""",
    "hin": """
Example 1 (Hindi title page + copyright):
Input:
प्रकाशन सूचना
शीर्षक: आधुनिक भारत का इतिहास
उपशीर्षक: स्वतंत्रता से आज तक
लेखक: डॉ. रमेश चंद्र शर्मा
संपादक: प्रो. सुरेश मिश्रा
प्रकाशक: राजकमल प्रकाशन, नई दिल्ली
मुद्रक: नेशनल प्रिंटिंग प्रेस, नोएडा
तीसरा संस्करण: 2023
ISBN: 978-81-267-1234-5
पृष्ठ संख्या: 320
Output:
{"title": "आधुनिक भारत का इतिहास", "subtitle": "स्वतंत्रता से आज तक", "author": "डॉ. रमेश चंद्र शर्मा", "editor": "प्रो. सुरेश मिश्रा", "publisher": "राजकमल प्रकाशन", "place_of_publication": "नई दिल्ली", "printer": "नेशनल प्रिंटिंग प्रेस", "place_of_printing": "नोएडा", "publication_date": "2023", "isbn": "978-81-267-1234-5", "pages": "320", "edition_number": "तीसरा संस्करण"}
""",
    "eng": """
Example 1 (English title page + copyright):
Input:
Publication Information
Title: The History of Modern India
Subtitle: From Independence to the Present Day
Author: Dr. Ramesh Chandra Sharma
Editor: Prof. Suresh Mishra
Publisher: National Book Trust, New Delhi
Printer: National Printing Press, Noida
First Edition: 2024
ISBN: 978-81-234-5678-9
Pages: 280
Output:
{"title": "The History of Modern India", "subtitle": "From Independence to the Present Day", "author": "Dr. Ramesh Chandra Sharma", "editor": "Prof. Suresh Mishra", "publisher": "National Book Trust", "place_of_publication": "New Delhi", "printer": "National Printing Press", "place_of_printing": "Noida", "publication_date": "2024", "isbn": "978-81-234-5678-9", "pages": "280", "edition_number": "First Edition"}
""",
}


EXTRACTION_PROMPT_TEMPLATE = Template(
    """Extract the following metadata fields from this {{ language_name }} book text.

Fields to extract:
{% for field in fields %}
- {{ field.name }}: {{ field.description }}
{% endfor %}

{% if few_shot_examples %}{{ few_shot_examples }}
{% endif %}
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
    include_few_shot: bool = True,
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

    few_shot = FEW_SHOT_EXAMPLES.get(language, "") if include_few_shot else ""

    return template.render(
        language_name=get_language_name(language),
        fields=fields,
        ocr_text=ocr_text,
        page_count=page_count,
        few_shot_examples=few_shot,
    )


def get_batch_field_names(batch_name: str) -> list[str]:
    batch_cls = METADATA_BATCHES.get(batch_name)
    if batch_cls is None:
        raise ValueError(f"Unknown batch: {batch_name}")
    return [f for f in batch_cls.model_fields if f != "custom_fields"]
