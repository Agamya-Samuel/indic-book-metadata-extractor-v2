# Ground Truth vs. Metadata Fields (49-field conformance & coverage)

Comparison of the corpus in `backend/tests/fixtures/ground_truth/` against [`docs/metadata-fields.md`](metadata-fields.md) (source: `app/schemas/metadata.py`). Regenerate with `uv run python -m scripts.gt_coverage_report`.

## Conformance

- Books **49** · canonical fields **49**.
- Every book's `expected_metadata`, `field_status` and `field_source` hold **exactly** the 49 keys (0 missing, 0 extra; `scripts/apply_field_schema.py --check`).
- Status: `verified`=8, `prefilled_llm_unverified`=41.

## Coverage

- **636** non-null values; **37/49** fields populated.
- Empty in every book (12): `inspired_by`, `cover_artist`, `cover_page_designer`, `typing_by`, `book_designer`, `part_of_the_set`, `illustrators`, `awards`, `first_published_in`, `abbreviations`, `opinions_messages`, `scribes`.

## Per-field

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
| 22 | `publication_date` | publication | P577 | 30 | 8 | 38 | unmapped:17, internet_archive:12, wikisource_index:9 |
| 23 | `publisher` | publication | P123 | 19 | 8 | 27 | internet_archive:14, unmapped:12, wikisource_index:1 |
| 24 | `publisher_telugu` | publication | — | 8 | 0 | 8 | node_llm_extraction:8 |
| 25 | `sponsor` | publication | P859 | 3 | 2 | 5 | node_llm_extraction:3, internet_archive:2 |
| 26 | `awards` | content_classification | — | 0 | 0 | 0 | — |
| 27 | `context` | content_classification | — | 0 | 1 | 1 | node_llm_extraction:1 |
| 28 | `form_of_creative_work` | content_classification | P7937 | 26 | 0 | 26 | unmapped:21, wikisource_index:5 |
| 29 | `genre` | content_classification | P136 | 13 | 10 | 23 | node_llm_extraction:13, commons_category:10 |
| 30 | `inception` | content_classification | P571 | 16 | 3 | 19 | node_llm_extraction:19 |
| 31 | `subject` | content_classification | P921 | 22 | 15 | 37 | internet_archive:22, node_llm_extraction:15 |
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
| 49 | `pages` | physical_extra | P1104 | 14 | 8 | 22 | internet_archive:22 |

## Per-book

| Book | Lang | Filled / 49 | Status |
|---|---|---|---|
| 2015.263752.Sadhu-Aur | hin | 18 | prefilled_llm_unverified |
| Muntakhabat-i-hindi_Vol._1_Ed._5th_IA_in.ernet.dli.2015.94432 | hin | 17 | prefilled_llm_unverified |
| Biography_of_Freedom_fighter_Mahadev_Mishra | hin | 15 | prefilled_llm_unverified |
| Gandhi_-_Dakshin_Afrika_Ke_Satyagraha_Hindi | hin | 14 | prefilled_llm_unverified |
| 5व_जल_सम_म_लन_9-12_नवम_बर_05 | hin | 13 | prefilled_llm_unverified |
| Gandhi_-_Delhi_Diary_Hindi | hin | 13 | prefilled_llm_unverified |
| Hindi_Ke_Musalman_Kavi_-_Ganga_Prasad_Singh | hin | 13 | prefilled_llm_unverified |
| Hindi_Sahitya_ka_Itihas_by_Acharya_Ramchandra_Shukla | hin | 13 | prefilled_llm_unverified |
| Prabhu-Padhare | hin | 12 | prefilled_llm_unverified |
| 19140101_Priyapravaas_Hindi_PDF | hin | 11 | prefilled_llm_unverified |
| Bhakta_Mala_of_Nabhadas_Ayodhya_Edition_1905 | hin | 11 | prefilled_llm_unverified |
| Lūka_racita_susamācāra_aura_Preritoṃkī_kriyāoṃkā_vṛttānta._IA_lukaracitasusama00unse | hin | 11 | prefilled_llm_unverified |
| 1913_Ummed_Singh_Charitra_Hindi_PDF | hin | 10 | verified |
| Bharatiya_Sampatti_Shastra | hin | 10 | prefilled_llm_unverified |
| Śiva_parīkshā._IA_sivapariksha00unse | hin | 10 | verified |
| Shri_Chandravali_-_Bharatendu_Harishchandra_-_1933 | hin | 7 | prefilled_llm_unverified |
| Antarrashtriya_Gyankosh | hin | 6 | prefilled_llm_unverified |
| Dayanand_Granthmala_Bhag_1_1925 | hin | 6 | verified |
| Godan_-_Premchand_-_Hindi_Novel | hin | 5 | prefilled_llm_unverified |
| 1857_మ_స_ల_ల | tel | 24 | prefilled_llm_unverified |
| 2015.373190.Athma-Charitramu | tel | 21 | prefilled_llm_unverified |
| 1917_Prataparudreeyamu_Ratnapanasahitam_Telugu_PDF | tel | 19 | prefilled_llm_unverified |
| 1927_shhadchakravartulayindrajaalapukathalu_Telugu_PDF | tel | 19 | prefilled_llm_unverified |
| A_Collection_of_Telugu_Proverbs_translat_1 | tel | 18 | prefilled_llm_unverified |
| 1895_SarpaVishayaSarvasvaSangrahamu_Telugu_PDF | tel | 17 | prefilled_llm_unverified |
| 2030020025431_-_chitra_leikhanamu | tel | 16 | prefilled_llm_unverified |
| 10879telugukaavy034400mbp | tel | 15 | prefilled_llm_unverified |
| 19220101_BrahmaVidya_Telugu_Pdf | tel | 15 | prefilled_llm_unverified |
| 10031upanishhats033596mbp | tel | 14 | prefilled_llm_unverified |
| 10049upanyaasans033612mbp | tel | 14 | prefilled_llm_unverified |
| 19280101_AngleyaVaidyaRahasyamu_Telugu_PDF | tel | 14 | prefilled_llm_unverified |
| 19330101_AndhrashabdaChinthamani_Telugu_pdf | tel | 14 | prefilled_llm_unverified |
| 2015.372978.Andhra-Kavithva | tel | 14 | prefilled_llm_unverified |
| 19280101_Vasanthakumari_Telugu | tel | 13 | prefilled_llm_unverified |
| 19300101_ShivarathriMahathmyamu_Telugu | tel | 13 | prefilled_llm_unverified |
| 2015.328360.Andhra-Mahaniyulu | tel | 13 | prefilled_llm_unverified |
| Aanandhanga_Undalante_VBS_JVV | tel | 13 | prefilled_llm_unverified |
| Abalaa_sachcharitra_ratnamaala_Dvitiiya_Sanputa | tel | 13 | prefilled_llm_unverified |
| 19220101_SriSugunaMani_Telugu_PDF | tel | 12 | prefilled_llm_unverified |
| 19230101_SangeetagoloBakavali_Telugu_PDF | tel | 12 | verified |
| 19240101_ChandrakantaNatakamu_Telugu_PDF | tel | 12 | prefilled_llm_unverified |
| 19250101_AndhranamaSangrahamuAndhraNamasheshamu_Telugu | tel | 12 | prefilled_llm_unverified |
| 19380101_Savitri_Natakamu_Telugu_PDF | tel | 12 | verified |
| A_Collection_of_Telugu_Proverbs | tel | 12 | prefilled_llm_unverified |
| .Kalidasa-Charitra_by_chilakamarthi_lakshminarasimham | tel | 11 | verified |
| 19230101_LavaKusa_Telugu_PDF | tel | 11 | prefilled_llm_unverified |
| Abalaa_sachcharitra_ratnamaala | tel | 10 | prefilled_llm_unverified |
| 19270101_PranaDanamu_Telugu_Pdf | tel | 9 | verified |
| 19280101_JyothishyaVidyaPrakashika_Telugu | tel | 9 | verified |

Source key: `unmapped` = value present but `field_source` unset; `node_llm_extraction` = unverified model prefill (see `learnings/019`); catalog sources as named.
