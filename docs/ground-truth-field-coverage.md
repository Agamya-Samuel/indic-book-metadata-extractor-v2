# Ground Truth vs. Metadata Fields (49-field conformance & coverage)

Comparison of the ground-truth corpus in `backend/tests/fixtures/ground_truth/` against the canonical 49 fields defined in [`docs/metadata-fields.md`](metadata-fields.md) (source: `backend/app/schemas/metadata.py`).

## Conformance (schema match)

- Books: **49** · canonical fields: **49**
- Every book's `expected_metadata`, `field_status` and `field_source` contain **exactly** the 49 canonical keys — **0 missing, 0 extra** across all books (verified by `scripts/apply_field_schema.py --check`).
- Verification status: `verified`=8, `prefilled_llm_unverified`=41.
- So the field spec is already applied; the remaining question is **coverage**, below.

## Coverage summary

- **623** non-null field values across the corpus.
- **37 of 49** fields carry data in at least one book.
- **12** fields are empty in every book: `inspired_by`, `cover_artist`, `cover_page_designer`, `typing_by`, `book_designer`, `part_of_the_set`, `illustrators`, `awards`, `first_published_in`, `abbreviations`, `opinions_messages`, `scribes`.

## Per-field coverage

| # | Field | Batch | Wikidata | Telugu | Hindi | Total | Source(s) |
|---|---|---|---|---|---|---|---|
| 1 | `author` | core_identity | P50 | 30 | 17 | 47 | unmapped:47 |
| 2 | `description_edition` | core_identity | — | 3 | 5 | 8 | node_llm_extraction:8 |
| 3 | `description_work` | core_identity | — | 24 | 18 | 42 | unmapped:42 |
| 4 | `isbn` | core_identity | — | 2 | 0 | 2 | node_llm_extraction:2 |
| 5 | `label` | core_identity | — | 30 | 12 | 42 | derived:20, unmapped:11, wikisource_index:7, internet_archive:4 |
| 6 | `language` | core_identity | P407 | 30 | 19 | 49 | unmapped:49 |
| 7 | `original_language` | core_identity | P364 | 30 | 19 | 49 | unmapped:49 |
| 8 | `subtitle` | core_identity | — | 8 | 7 | 15 | node_llm_extraction:15 |
| 9 | `title` | core_identity | — | 30 | 12 | 42 | unmapped:31, wikisource_index:7, internet_archive:4 |
| 10 | `book_designer` | contributors | — | 0 | 0 | 0 | — |
| 11 | `compiler` | contributors | — | 0 | 2 | 2 | node_llm_extraction:2 |
| 12 | `cover_artist` | contributors | P736 | 0 | 0 | 0 | — |
| 13 | `cover_page_designer` | contributors | — | 0 | 0 | 0 | — |
| 14 | `editor` | contributors | P98 | 2 | 0 | 2 | unmapped:2 |
| 15 | `translator` | contributors | P655 | 0 | 2 | 2 | node_llm_extraction:2 |
| 16 | `typesetting_by` | contributors | — | 1 | 0 | 1 | node_llm_extraction:1 |
| 17 | `typing_by` | contributors | — | 0 | 0 | 0 | — |
| 18 | `distributors` | publication | — | 4 | 1 | 5 | node_llm_extraction:5 |
| 19 | `place_of_printing` | publication | P2919 | 19 | 10 | 29 | node_llm_extraction:29 |
| 20 | `place_of_publication` | publication | P291 | 16 | 0 | 16 | unmapped:13, wikisource_index:3 |
| 21 | `printer` | publication | P872 | 15 | 11 | 26 | node_llm_extraction:26 |
| 22 | `publication_date` | publication | P577 | 30 | 5 | 35 | unmapped:17, internet_archive:9, wikisource_index:9 |
| 23 | `publisher` | publication | P123 | 19 | 5 | 24 | unmapped:12, internet_archive:11, wikisource_index:1 |
| 24 | `publisher_telugu` | publication | — | 8 | 0 | 8 | node_llm_extraction:8 |
| 25 | `sponsor` | publication | P859 | 3 | 0 | 3 | node_llm_extraction:3 |
| 26 | `awards` | content_classification | — | 0 | 0 | 0 | — |
| 27 | `context` | content_classification | — | 0 | 1 | 1 | node_llm_extraction:1 |
| 28 | `form_of_creative_work` | content_classification | P7937 | 26 | 0 | 26 | unmapped:21, wikisource_index:5 |
| 29 | `genre` | content_classification | P136 | 13 | 10 | 23 | node_llm_extraction:13, commons_category:10 |
| 30 | `inception` | content_classification | P571 | 16 | 3 | 19 | node_llm_extraction:19 |
| 31 | `subject` | content_classification | P921 | 22 | 13 | 35 | internet_archive:20, node_llm_extraction:15 |
| 32 | `edition_number` | edition_series | P393 | 2 | 6 | 8 | node_llm_extraction:8 |
| 33 | `edition_or_translation_of` | edition_series | P629 | 1 | 1 | 2 | node_llm_extraction:2 |
| 34 | `part_of_series` | edition_series | — | 3 | 1 | 4 | node_llm_extraction:4 |
| 35 | `part_of_the_set` | edition_series | — | 0 | 0 | 0 | — |
| 36 | `serial_number_in_series` | edition_series | — | 3 | 1 | 4 | node_llm_extraction:4 |
| 37 | `volume` | edition_series | P478 | 1 | 2 | 3 | node_llm_extraction:2, unmapped:1 |
| 38 | `based_on` | relationships | P144 | 0 | 1 | 1 | node_llm_extraction:1 |
| 39 | `first_published_in` | relationships | — | 0 | 0 | 0 | — |
| 40 | `inspired_by` | relationships | P941 | 0 | 0 | 0 | — |
| 41 | `abbreviations` | ancillary_content | — | 0 | 0 | 0 | — |
| 42 | `authors_in_compilation` | ancillary_content | — | 11 | 9 | 20 | node_llm_extraction:20 |
| 43 | `dedication` | ancillary_content | — | 2 | 2 | 4 | node_llm_extraction:4 |
| 44 | `dedication_verbatim` | ancillary_content | — | 2 | 2 | 4 | node_llm_extraction:4 |
| 45 | `forewords` | ancillary_content | — | 1 | 0 | 1 | node_llm_extraction:1 |
| 46 | `opinions_messages` | ancillary_content | — | 0 | 0 | 0 | — |
| 47 | `scribes` | ancillary_content | — | 0 | 0 | 0 | — |
| 48 | `illustrators` | physical_extra | — | 0 | 0 | 0 | — |
| 49 | `pages` | physical_extra | P1104 | 14 | 5 | 19 | internet_archive:19 |

Source key: `unmapped` = value present but `field_source` unset (catalog/seed); `node_llm_extraction` = model prefill from the scan (unverified — see [learnings/019](../learnings/019-gt-corpus-enrichment.md)); `wikisource_index` / `internet_archive` / `commons_category` = catalog enrichment.

## Notes

- The 12 empty fields are genuinely rare or only present on pages not fetched (cover designers, typesetters, scribes, awards, …); they are not a schema gap.
- Values sourced `node_llm_extraction` are **prefill, not verified truth**. The scoring harness excludes them per-field, so prefilled books still score their verified core (`scripts/evaluate_extraction.py` → `ignored_fields`).
- `author`/`title`/`language` show `unmapped` because their `field_source` was never set by the fetch scaffold; the values themselves are catalog/seed sourced.
