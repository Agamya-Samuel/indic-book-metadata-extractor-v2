# Metadata Fields Reference (49 fields)

Reference for the **49 predefined bibliographic fields** the pipeline extracts from a book PDF.

- **Source of truth:** [`backend/app/schemas/metadata.py`](../backend/app/schemas/metadata.py) — `FullMetadata`, `METADATA_BATCHES`, `ALL_METADATA_FIELDS`, `FIELD_WIKIDATA`, `FIELD_DISPLAY_NAMES`.
- **Used by:** the extraction prompt ([`prompts.py`](../backend/app/services/prompts.py)), the LLM batches ([`llm_service.py`](../backend/app/services/llm_service.py)), the metadata review UI, the CSV export, and the ground-truth scaffolds under [`backend/tests/fixtures/ground_truth/`](../backend/tests/fixtures/ground_truth).

## Summary

| Property | Value |
|---|---|
| Predefined fields | **49** (plus one optional `custom_fields` container, excluded from the count) |
| Batches | **8** (`core_identity`, `contributors`, `publication`, `content_classification`, `edition_series`, `relationships`, `ancillary_content`, `physical_extra`) |
| Data type | **every field is `str \| None`, default `None`** — no enums, no per-field validation |
| Wikidata-mapped | **22 of 49** carry a Wikidata property (P-ID); 27 do not |
| Multi-entity fields | values may contain several entities; treat as sets when scoring (see below) |
| Storage | one JSONB column + individual indexed columns; CSV export mirrors the 49 keys |

> The "52 fields" wording that appears in older passages of [`indic_book_metadata_extractor.md`](indic_book_metadata_extractor.md) is stale — that document's own numbered table stops at 49.

## The 49 fields, by batch

### 1. `core_identity` (9)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 1 | `label` | Label (Work and Edition) | `str \| None` | — |
| 2 | `author` | Author | `str \| None` | P50 |
| 3 | `description_work` | Description for Work | `str \| None` | — |
| 4 | `description_edition` | Description for Edition | `str \| None` | — |
| 5 | `original_language` | Original Language | `str \| None` | P364 |
| 6 | `language` | Language | `str \| None` | P407 |
| 7 | `isbn` | ISBN | `str \| None` | — |
| 8 | `title` | Title (if subtitle exists) | `str \| None` | — |
| 9 | `subtitle` | Subtitle | `str \| None` | — |

### 2. `contributors` (8)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 10 | `translator` | Translator | `str \| None` | P655 |
| 11 | `editor` | Editor | `str \| None` | P98 |
| 12 | `compiler` | Compiler (సంకలనకర్త) | `str \| None` | — |
| 13 | `cover_artist` | Cover Artist | `str \| None` | P736 |
| 14 | `cover_page_designer` | Cover Page Designer | `str \| None` | — |
| 15 | `typesetting_by` | Type Setting by | `str \| None` | — |
| 16 | `typing_by` | Typing (టైపింగ్) | `str \| None` | — |
| 17 | `book_designer` | Book Designer | `str \| None` | — |

### 3. `publication` (8)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 18 | `publication_date` | Publication Date | `str \| None` | P577 |
| 19 | `publisher` | Publisher | `str \| None` | P123 |
| 20 | `publisher_telugu` | Publisher Telugu (ప్రచురణకర్త) | `str \| None` | — |
| 21 | `place_of_publication` | Place of Publication | `str \| None` | P291 |
| 22 | `printer` | Printer | `str \| None` | P872 |
| 23 | `place_of_printing` | Place of Printing | `str \| None` | P2919 |
| 24 | `distributors` | Distributors (పంపిణీదారులు) | `str \| None` | — |
| 25 | `sponsor` | Sponsor | `str \| None` | P859 |

### 4. `content_classification` (6)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 26 | `form_of_creative_work` | Form of Creative Work | `str \| None` | P7937 |
| 27 | `genre` | Genre | `str \| None` | P136 |
| 28 | `subject` | Subject | `str \| None` | P921 |
| 29 | `inception` | Inception / First Written | `str \| None` | P571 |
| 30 | `context` | Context (సందర్భం) | `str \| None` | — |
| 31 | `awards` | Awards (అవార్డులు) | `str \| None` | — |

### 5. `edition_series` (6)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 32 | `volume` | Volume | `str \| None` | P478 |
| 33 | `edition_number` | Edition Number | `str \| None` | P393 |
| 34 | `edition_or_translation_of` | Edition or Translation of | `str \| None` | P629 |
| 35 | `part_of_series` | Part of Series | `str \| None` | — |
| 36 | `serial_number_in_series` | Serial Number within Series | `str \| None` | — |
| 37 | `part_of_the_set` | Part of the Set | `str \| None` | — |

### 6. `relationships` (3)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 38 | `based_on` | Based on | `str \| None` | P144 |
| 39 | `inspired_by` | Inspired by | `str \| None` | P941 |
| 40 | `first_published_in` | First Published In (తొలిగా ప్రచురించిన పత్రిక) | `str \| None` | — |

### 7. `ancillary_content` (7)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 41 | `dedication` | Dedication (అంకితం) | `str \| None` | — |
| 42 | `dedication_verbatim` | Dedication Verbatim | `str \| None` | — |
| 43 | `forewords` | Forewords (ముందుమాట(లు)) | `str \| None` | — |
| 44 | `abbreviations` | Abbreviations (సంక్షిప్తీకరణ) | `str \| None` | — |
| 45 | `authors_in_compilation` | Authors in Compilation (సంకలనంలోని రచయితలు) | `str \| None` | — |
| 46 | `opinions_messages` | Opinions / Messages (అభిప్రాయాలు / సందేశాలు) | `str \| None` | — |
| 47 | `scribes` | Scribes (లేఖకులు) | `str \| None` | — |

### 8. `physical_extra` (2)

| # | Field key | Display name | Type | Wikidata |
|---|---|---|---|---|
| 48 | `pages` | Pages | `str \| None` | P1104 |
| 49 | `illustrators` | Illustrators (పుస్తకంలో బొమ్మలు వేసిన చిత్రకారులు) | `str \| None` | — |

> `custom_fields` (`dict | None`) is an optional user-added container in this same batch. It is **not** one of the 49 and is excluded from the count and from scoring.

## Wikidata mapping

22 fields map to a Wikidata property; 27 do not.

| Field | P-ID | Field | P-ID |
|---|---|---|---|
| `author` | P50 | `volume` | P478 |
| `translator` | P655 | `edition_number` | P393 |
| `editor` | P98 | `publication_date` | P577 |
| `inception` | P571 | `publisher` | P123 |
| `form_of_creative_work` | P7937 | `place_of_publication` | P291 |
| `genre` | P136 | `printer` | P872 |
| `subject` | P921 | `place_of_printing` | P2919 |
| `original_language` | P364 | `language` | P407 |
| `edition_or_translation_of` | P629 | `cover_artist` | P736 |
| `based_on` | P144 | `pages` | P1104 |
| `inspired_by` | P941 | `sponsor` | P859 |

Unmapped (27): `label`, `description_work`, `description_edition`, `compiler`, `cover_page_designer`, `typesetting_by`, `typing_by`, `book_designer`, `publisher_telugu`, `distributors`, `context`, `awards`, `part_of_series`, `serial_number_in_series`, `part_of_the_set`, `first_published_in`, `dedication`, `dedication_verbatim`, `forewords`, `abbreviations`, `authors_in_compilation`, `opinions_messages`, `scribes`, `isbn`, `title`, `subtitle`, `illustrators`.

## Data types & constraints

- **All 49 fields are `str | None`** with default `None`. There are no enums, ranges, or per-field validators — a value is free-form text in whatever script the source uses (typically Telugu/Hindi, sometimes transliterated Latin, sometimes a number like a year or page count).
- **Absent vs. unknown** are not distinguished in the stored value (both are `null`). The ground-truth scaffolds carry this distinction separately in a per-field `field_status` / `verification` block.
- **Multi-entity fields:** values may list several entities in one string — `author`, `editor`, `translator`, `compiler`, `illustrators`, `cover_artist`, `distributors`, `authors_in_compilation`, `forewords`, `opinions_messages`, `scribes`. Score them as sets.
- **Wikidata P-IDs** are used for the bulk-export path (Wikibase / QuickStatements), not for validation.

## Where the fields are produced and consumed

| Stage | Artefact |
|---|---|
| Extraction prompt | [`backend/app/services/prompts.py`](../backend/app/services/prompts.py) (`EXTRACTION_PROMPT_TEMPLATE`, `FIELD_DISPLAY_NAMES`) |
| Batched LLM calls | [`backend/app/services/llm_service.py`](../backend/app/services/llm_service.py) (`METADATA_BATCHES`, hybrid tiering) |
| Ground truth | [`backend/tests/fixtures/ground_truth/`](../backend/tests/fixtures/ground_truth) — `expected_metadata.json` (all 49 keys), `manifest.jsonl` |
| Evaluation | [`backend/scripts/evaluate_extraction.py`](../backend/scripts/evaluate_extraction.py) + [`backend/app/services/extraction_validator.py`](../backend/app/services/extraction_validator.py) |
| Ground-truth coverage today | [learnings/019](019-gt-corpus-enrichment.md) — 37 of 49 fields populated across the 49-book corpus |

## See also

- [learnings/001](001-ground-truth-dataset-feasibility.md) — field-by-field schema analysis and evaluation metrics/split.
- [docs/wikidata-workflow.md](wikidata-workflow.md) · [docs/wikibase-reference.md](wikibase-reference.md) — the P-ID export path.
- [docs/indic_book_metadata_extractor.md](indic_book_metadata_extractor.md) — product spec (its field table also lists the 49).
