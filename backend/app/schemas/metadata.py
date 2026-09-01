from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CoreIdentityBatch(BaseModel):
    label: str | None = Field(default=None, description="Label (Work and Edition)")
    author: str | None = Field(default=None, description="Author")
    description_work: str | None = Field(default=None, description="Description for Work")
    description_edition: str | None = Field(default=None, description="Description for Edition")
    original_language: str | None = Field(default=None, description="Original Language")
    language: str | None = Field(default=None, description="Language")
    isbn: str | None = Field(default=None, description="ISBN")
    title: str | None = Field(default=None, description="Title (if subtitle exists)")
    subtitle: str | None = Field(default=None, description="Subtitle")


class ContributorsBatch(BaseModel):
    translator: str | None = Field(default=None, description="Translator")
    editor: str | None = Field(default=None, description="Editor")
    compiler: str | None = Field(default=None, description="Compiler (సంకలనకర్త)")
    cover_artist: str | None = Field(default=None, description="Cover Artist")
    cover_page_designer: str | None = Field(default=None, description="Cover Page Designer")
    typesetting_by: str | None = Field(default=None, description="Type Setting by")
    typing_by: str | None = Field(default=None, description="Typing (టైపింగ్)")
    book_designer: str | None = Field(default=None, description="Book Designer")


class PublicationBatch(BaseModel):
    publication_date: str | None = Field(default=None, description="Publication Date")
    publisher: str | None = Field(default=None, description="Publisher")
    publisher_telugu: str | None = Field(default=None, description="Publisher Telugu (ప్రచురణకర్త)")
    place_of_publication: str | None = Field(default=None, description="Place of Publication")
    printer: str | None = Field(default=None, description="Printer")
    place_of_printing: str | None = Field(default=None, description="Place of Printing")
    distributors: str | None = Field(default=None, description="Distributors (పంపిణీదారులు)")
    sponsor: str | None = Field(default=None, description="Sponsor")


class ContentClassificationBatch(BaseModel):
    form_of_creative_work: str | None = Field(default=None, description="Form of Creative Work")
    genre: str | None = Field(default=None, description="Genre")
    subject: str | None = Field(default=None, description="Subject")
    inception: str | None = Field(default=None, description="Inception / First Written")
    context: str | None = Field(default=None, description="Context (సందర్భం)")
    awards: str | None = Field(default=None, description="Awards (అవార్డులు)")


class EditionSeriesBatch(BaseModel):
    volume: str | None = Field(default=None, description="Volume")
    edition_number: str | None = Field(default=None, description="Edition Number")
    edition_or_translation_of: str | None = Field(default=None, description="Edition or Translation of")
    part_of_series: str | None = Field(default=None, description="Part of Series")
    serial_number_in_series: str | None = Field(default=None, description="Serial Number within Series")
    part_of_the_set: str | None = Field(default=None, description="Part of the Set")


class RelationshipsBatch(BaseModel):
    based_on: str | None = Field(default=None, description="Based on")
    inspired_by: str | None = Field(default=None, description="Inspired by")
    first_published_in: str | None = Field(default=None, description="First Published In (తొలిగా ప్రచురించిన పత్రిక)")


class AncillaryContentBatch(BaseModel):
    dedication: str | None = Field(default=None, description="Dedication (అంకితం)")
    dedication_verbatim: str | None = Field(default=None, description="Dedication Verbatim")
    forewords: str | None = Field(default=None, description="Forewords (ముందుమాట(లు))")
    abbreviations: str | None = Field(default=None, description="Abbreviations (సంక్షిప్తీకరణ)")
    authors_in_compilation: str | None = Field(default=None, description="Authors in Compilation (సంకలనంలోని రచయితలు)")
    opinions_messages: str | None = Field(default=None, description="Opinions / Messages (అభిప్రాయాలు / సందేశాలు)")
    scribes: str | None = Field(default=None, description="Scribes (లేఖకులు)")


class PhysicalExtraBatch(BaseModel):
    pages: str | None = Field(default=None, description="Pages")
    illustrators: str | None = Field(default=None, description="Illustrators (పుస్తకంలో బొమ్మలు వేసిన చిత్రకారులు)")
    custom_fields: dict | None = Field(default=None, description="User-added custom fields")


class FullMetadata(BaseModel):
    label: str | None = None
    author: str | None = None
    description_work: str | None = None
    description_edition: str | None = None
    translator: str | None = None
    editor: str | None = None
    compiler: str | None = None
    inception: str | None = None
    form_of_creative_work: str | None = None
    genre: str | None = None
    subject: str | None = None
    original_language: str | None = None
    edition_or_translation_of: str | None = None
    based_on: str | None = None
    inspired_by: str | None = None
    volume: str | None = None
    edition_number: str | None = None
    publication_date: str | None = None
    publisher: str | None = None
    place_of_publication: str | None = None
    printer: str | None = None
    place_of_printing: str | None = None
    language: str | None = None
    cover_artist: str | None = None
    cover_page_designer: str | None = None
    typesetting_by: str | None = None
    typing_by: str | None = None
    book_designer: str | None = None
    distributors: str | None = None
    pages: str | None = None
    dedication: str | None = None
    dedication_verbatim: str | None = None
    part_of_series: str | None = None
    serial_number_in_series: str | None = None
    part_of_the_set: str | None = None
    illustrators: str | None = None
    isbn: str | None = None
    title: str | None = None
    subtitle: str | None = None
    awards: str | None = None
    context: str | None = None
    publisher_telugu: str | None = None
    sponsor: str | None = None
    first_published_in: str | None = None
    forewords: str | None = None
    abbreviations: str | None = None
    authors_in_compilation: str | None = None
    opinions_messages: str | None = None
    scribes: str | None = None
    custom_fields: dict | None = None


METADATA_BATCHES: dict[str, type[BaseModel]] = {
    "core_identity": CoreIdentityBatch,
    "contributors": ContributorsBatch,
    "publication": PublicationBatch,
    "content_classification": ContentClassificationBatch,
    "edition_series": EditionSeriesBatch,
    "relationships": RelationshipsBatch,
    "ancillary_content": AncillaryContentBatch,
    "physical_extra": PhysicalExtraBatch,
}

BATCH_FIELD_ORDER = [
    "core_identity",
    "contributors",
    "publication",
    "content_classification",
    "edition_series",
    "relationships",
    "ancillary_content",
    "physical_extra",
]

FIELD_WIKIDATA = {
    "label": None,
    "author": "P50",
    "description_work": None,
    "description_edition": None,
    "translator": "P655",
    "editor": "P98",
    "compiler": None,
    "inception": "P571",
    "form_of_creative_work": "P7937",
    "genre": "P136",
    "subject": "P921",
    "original_language": "P364",
    "edition_or_translation_of": "P629",
    "based_on": "P144",
    "inspired_by": "P941",
    "volume": "P478",
    "edition_number": "P393",
    "publication_date": "P577",
    "publisher": "P123",
    "place_of_publication": "P291",
    "printer": "P872",
    "place_of_printing": "P2919",
    "language": "P407",
    "cover_artist": "P736",
    "cover_page_designer": None,
    "typesetting_by": None,
    "typing_by": None,
    "book_designer": None,
    "distributors": None,
    "pages": "P1104",
    "dedication": None,
    "dedication_verbatim": None,
    "part_of_series": None,
    "serial_number_in_series": None,
    "part_of_the_set": None,
    "illustrators": None,
    "isbn": None,
    "title": None,
    "subtitle": None,
    "awards": None,
    "context": None,
    "publisher_telugu": None,
    "sponsor": "P859",
    "first_published_in": None,
    "forewords": None,
    "abbreviations": None,
    "authors_in_compilation": None,
    "opinions_messages": None,
    "scribes": None,
}

FIELD_DISPLAY_NAMES = {
    "label": "Label (Work and Edition)",
    "author": "Author",
    "description_work": "Description for Work",
    "description_edition": "Description for Edition",
    "translator": "Translator",
    "editor": "Editor",
    "compiler": "Compiler (సంకలనకర్త)",
    "inception": "Inception / First Written",
    "form_of_creative_work": "Form of Creative Work",
    "genre": "Genre",
    "subject": "Subject",
    "original_language": "Original Language",
    "edition_or_translation_of": "Edition or Translation of",
    "based_on": "Based on",
    "inspired_by": "Inspired by",
    "volume": "Volume",
    "edition_number": "Edition Number",
    "publication_date": "Publication Date",
    "publisher": "Publisher",
    "place_of_publication": "Place of Publication",
    "printer": "Printer",
    "place_of_printing": "Place of Printing",
    "language": "Language",
    "cover_artist": "Cover Artist",
    "cover_page_designer": "Cover Page Designer",
    "typesetting_by": "Type Setting by",
    "typing_by": "Typing (టైపింగ్)",
    "book_designer": "Book Designer",
    "distributors": "Distributors (పంపిణీదారులు)",
    "pages": "Pages",
    "dedication": "Dedication (అంకితం)",
    "dedication_verbatim": "Dedication Verbatim",
    "part_of_series": "Part of Series",
    "serial_number_in_series": "Serial Number within Series",
    "part_of_the_set": "Part of the Set",
    "illustrators": "Illustrators (పుస్తకంలో బొమ్మలు వేసిన చిత్రకారులు)",
    "isbn": "ISBN",
    "title": "Title (if subtitle exists)",
    "subtitle": "Subtitle",
    "awards": "Awards (అవార్డులు)",
    "context": "Context (సందర్భం)",
    "publisher_telugu": "Publisher Telugu (ప్రచురణకర్త)",
    "sponsor": "Sponsor",
    "first_published_in": "First Published In (తొలిగా ప్రచురించిన పత్రిక)",
    "forewords": "Forewords (ముందుమాట(లు))",
    "abbreviations": "Abbreviations (సంక్షిప్తీకరణ)",
    "authors_in_compilation": "Authors in Compilation (సంకలనంలోని రచయితలు)",
    "opinions_messages": "Opinions / Messages (అభిప్రాయాలు / సందేశాలు)",
    "scribes": "Scribes (లేఖకులు)",
}


def _field_batch_map() -> dict[str, str]:
    mapping = {}
    for batch_name, batch_cls in METADATA_BATCHES.items():
        for field_name in batch_cls.model_fields:
            if field_name != "custom_fields":
                mapping[field_name] = batch_name
    return mapping


FIELD_TO_BATCH: dict[str, str] = _field_batch_map()


class MetadataFieldDefinition(BaseModel):
    field_name: str
    display_name: str
    wikidata_property: str | None
    batch_group: str


ALL_METADATA_FIELDS: list[MetadataFieldDefinition] = [
    MetadataFieldDefinition(
        field_name=fn,
        display_name=FIELD_DISPLAY_NAMES.get(fn, fn),
        wikidata_property=FIELD_WIKIDATA.get(fn),
        batch_group=FIELD_TO_BATCH.get(fn, "physical_extra"),
    )
    for fn in FullMetadata.model_fields
    if fn != "custom_fields"
]


class ExtractionRequest(BaseModel):
    model: str = "qwen2.5"
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=256, le=8192)
    custom_system_prompt: str | None = None
    custom_extraction_prompt: str | None = None


class ExtractionResponse(BaseModel):
    job_id: uuid.UUID
    book_id: uuid.UUID
    status: str
    total_batches: int


class MetadataResponse(BaseModel):
    book_id: uuid.UUID
    fields: dict
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class MetadataUpdateRequest(BaseModel):
    fields: dict


class LlmRunResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    model: str
    prompt_template: str | None
    batch_config: dict | None
    raw_response: str | None
    parsed_fields: dict | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ModelInfo(BaseModel):
    name: str
    size_gb: float | None = None
    parameter_count: str | None = None
