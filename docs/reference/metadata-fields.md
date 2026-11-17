# Metadata Fields

The extraction schema is **49 standard fields plus `custom_fields`** — 50 keys in the stored object.

- Schema: `backend/app/schemas/metadata.py` (`FullMetadata`, `METADATA_BATCHES`)
- Display names: `FIELD_DISPLAY_NAMES`
- Prompt guidance: `backend/app/services/prompt_profiles.py` (`FIELD_GUIDANCE`)

Each field is `string | null`. Dates, page counts and edition numbers are **strings**, not numbers,
because books print them as text ("మొదటి ముద్రణ", "First Edition, 2024").

---

## Batch grouping

Fields are extracted in 8 batches, because a single 49-key prompt on a 4B model degrades badly. Each
batch is a Pydantic model and is schema-validated before storage.

| Batch | Count | Page window used |
| --- | --- | --- |
| `core_identity` | 9 | first 3 |
| `contributors` | 8 | first 3 |
| `publication` | 8 | first 4 + last 3 |
| `content_classification` | 6 | first 3 |
| `edition_series` | 6 | first 4 + last 3 |
| `relationships` | 3 | first 8 + last 3 |
| `ancillary_content` | 7 | first 5 + last 3 |
| `physical_extra` | 2 (+ custom) | all pages |

---

## `core_identity` (9)

| Field | Display name |
| --- | --- |
| `label` | Label (Work and Edition) |
| `author` | Author |
| `description_work` | Description for Work |
| `description_edition` | Description for Edition |
| `original_language` | Original Language |
| `language` | Language |
| `isbn` | ISBN |
| `title` | Title (if subtitle exists) |
| `subtitle` | Subtitle |

`isbn` is also extracted by the regex tier, so the LLM is usually not asked for it.

---

## `contributors` (8)

| Field | Display name |
| --- | --- |
| `translator` | Translator |
| `editor` | Editor |
| `compiler` | Compiler (సంకలనకర్త) |
| `cover_artist` | Cover Artist |
| `cover_page_designer` | Cover Page Designer |
| `typesetting_by` | Type Setting by |
| `typing_by` | Typing (టైపింగ్) |
| `book_designer` | Book Designer |

---

## `publication` (8)

| Field | Display name |
| --- | --- |
| `publication_date` | Publication Date |
| `publisher` | Publisher |
| `publisher_telugu` | Publisher Telugu (ప్రచురణకర్త) |
| `place_of_publication` | Place of Publication |
| `printer` | Printer |
| `place_of_printing` | Place of Printing |
| `distributors` | Distributors (పంపిణీదారులు) |
| `sponsor` | Sponsor |

`publication_date` and `publisher` are also attempted by the cheap tiers (year regex, publisher
dictionary).

Guidance from the prompt profile is explicit that publisher, distributors and sponsor are **three
different roles** and must not be merged.

---

## `content_classification` (6)

| Field | Display name |
| --- | --- |
| `form_of_creative_work` | Form of Creative Work |
| `genre` | Genre |
| `subject` | Subject |
| `inception` | Inception / First Written |
| `context` | Context (సందర్భం) |
| `awards` | Awards (అవార్డులు) |

`inception` is exact-match scored — an approximate year is a wrong answer.

---

## `edition_series` (6)

| Field | Display name |
| --- | --- |
| `volume` | Volume |
| `edition_number` | Edition Number |
| `edition_or_translation_of` | Edition or Translation of |
| `part_of_series` | Part of Series |
| `serial_number_in_series` | Serial Number within Series |
| `part_of_the_set` | Part of the Set |

---

## `relationships` (3)

| Field | Display name |
| --- | --- |
| `based_on` | Based on |
| `inspired_by` | Inspired by |
| `first_published_in` | First Published In (తొలిగా ప్రచురించిన పత్రిక) |

These live on title pages or colophons, which is why this batch gets the widest front window and a
back-matter union.

---

## `ancillary_content` (7)

| Field | Display name |
| --- | --- |
| `dedication` | Dedication (అంకితం) |
| `dedication_verbatim` | Dedication Verbatim |
| `forewords` | Forewords (ముందుమాట(లు)) |
| `abbreviations` | Abbreviations (సంక్షిప్తీకరణ) |
| `authors_in_compilation` | Authors in Compilation (సంకలనంలోని రచయితలు) |
| `opinions_messages` | Opinions / Messages (అభిప్రాయాలు / సందేశాలు) |
| `scribes` | Scribes (లేఖకులు) |

`dedication` and `dedication_verbatim` are deliberately separate: one is the normalised dedication, the
other is the text exactly as printed, including the names in it.

---

## `physical_extra` (2 + custom)

| Field | Display name |
| --- | --- |
| `pages` | Pages |
| `illustrators` | Illustrators (పుస్తకంలో బొమ్మలు వేసిన చిత్రకారులు) |
| `custom_fields` | User-added custom fields (object, not a string) |

`pages` is also extracted by the regex tier.

`custom_fields` is the **only** key preserved across a re-run. Every standard field is replaced, so a
value the new run could not find becomes `null` rather than keeping a stale one.

---

## Presence semantics

| Value | Meaning |
| --- | --- |
| `null` | The book does not state this, or it could not be read |
| `""` | Treated as absent by the evaluator — do not emit |
| `"N/A"`, `"unknown"` | Treated as absent; never emit placeholders |

An all-null batch is a valid answer and does not fail the job. Failing to distinguish "absent" from
"failed" was an earlier defect; see [`learnings/016`](../../learnings/016-pipeline-non-functional-at-head.md).

---

## Provenance

Every populated field should have a `metadata_field_evidence` row:

| Column | Meaning |
| --- | --- |
| `value` | The extracted value |
| `confidence` | 0–1 |
| `extraction_method` | `regex` \| `dictionary` \| `ner` \| `llm` \| `human` |
| `source_page_number` | Page the value came from |
| `source_text_snippet` | The OCR text that supports it |
| `source_bbox` | Optional box for highlighting |

The UI surfaces a "review needed" hint below `LOW_CONFIDENCE_THRESHOLD` (default `0.55`).

> `ner` is listed for completeness; no NER tier is implemented.

---

## Wikidata mapping

34 of the 49 fields map to a Wikidata property; 15 have no equivalent. The mapping is `FIELD_WIKIDATA`
in `backend/app/schemas/metadata.py` and is what `POST /api/bulk/export-wikibase` uses to build
QuickStatements. The property catalogue created by `wikibase-init` is
[`docker/wikibase/properties.json`](../../docker/wikibase/properties.json).

| Field | P-ID | Field | P-ID |
| --- | --- | --- | --- |
| `author` | P50 | `volume` | P478 |
| `translator` | P655 | `edition_number` | P393 |
| `editor` | P98 | `publication_date` | P577 |
| `compiler` | P98 | `publisher` | P123 |
| `inception` | P571 | `place_of_publication` | P291 |
| `form_of_creative_work` | P7937 | `printer` | P872 |
| `genre` | P136 | `distributors` | P750 |
| `subject` | P921 | `sponsor` | P859 |
| `awards` | P166 | `pages` | P1104 |
| `original_language` | P407 | `dedication` | P825 |
| `language` | P407 | `part_of_series` | P179 |
| `edition_or_translation_of` | P629 | `serial_number_in_series` | P1545 |
| `based_on` | P144 | `part_of_the_set` | P361 |
| `inspired_by` | P941 | `isbn` | P212 |
| `cover_artist` | P736 | `title` | P1476 |
| `illustrators` | P110 | `subtitle` | P1680 |
| `first_published_in` | P1433 | `forewords` | P2679 |

Notes:

- `compiler` shares P98 with `editor`; Wikidata treats "compiled by" as an alias of editor.
- `original_language` and `language` both use P407. P364 is deprecated for written works.
- `isbn` routes to P212 for 13-digit values and P957 for 10-digit values.
- `title` and `subtitle` are monolingual text; exports use the book's language tag (`te`, `hi`, `en`).
- `pages` is a quantity; time fields use Wikidata time precision.

**Unmapped (15):** `label`, `description_work`, `description_edition`, `place_of_printing`,
`cover_page_designer`, `typesetting_by`, `typing_by`, `book_designer`, `publisher_telugu`,
`dedication_verbatim`, `context`, `abbreviations`, `authors_in_compilation`, `opinions_messages`,
`scribes`. These are either entity labels/descriptions rather than claims, or roles and free text with
no dedicated Wikidata property.

Local property IDs differ from Wikidata's because Wikibase assigns them sequentially (`P1`, `P2`, …).
`create-properties.sh` writes `property-mapping.json`, and the backend resolves Wikidata P-IDs to the
local IDs when generating exports.

## Related

- Extraction mechanics: [extraction](../processing/extraction.md)
- Storage shape: [data-model](../application/data-model.md)
- Scoring rules: [evaluation](../testing/evaluation.md)
