# Ground Truth vs. Metadata Fields (49-field conformance & coverage)

Comparison of the corpus in `backend/tests/fixtures/ground_truth/` against [`docs/metadata-fields.md`](metadata-fields.md) (source: `app/schemas/metadata.py`). Regenerate with `uv run python -m scripts.gt_coverage_report`.

## Conformance

- Books **71** · canonical fields **49**.
- Every book's `expected_metadata`, `field_status` and `field_source` hold **exactly** the 49 keys (0 missing, 0 extra; `scripts/apply_field_schema.py --check`).
- Status: `verified`=71.

## Coverage

- **844** non-null values; **39/49** fields populated.
- Empty in every book (10): `cover_artist`, `cover_page_designer`, `typing_by`, `book_designer`, `part_of_the_set`, `illustrators`, `awards`, `first_published_in`, `abbreviations`, `scribes`.

## Per-field

| # | Field | Batch | Wikidata | Telugu | Hindi | Total | Source(s) |
|---|---|---|---|---|---|---|---|
| 1 | `author` | core_identity | P50 | 36 | 32 | 68 | unmapped:44, openrouter_transliteration:24 |
| 2 | `description_edition` | core_identity | — | 4 | 6 | 10 | node_llm_extraction:10 |
| 3 | `description_work` | core_identity | — | 30 | 33 | 63 | unmapped:63 |
| 4 | `isbn` | core_identity | — | 2 | 0 | 2 | node_llm_extraction:2 |
| 5 | `label` | core_identity | — | 36 | 27 | 63 | unmapped:24, derived:20, wikisource_index:12, openrouter_transliteration:4, internet_archive:3 |
| 6 | `language` | core_identity | P407 | 36 | 35 | 71 | unmapped:71 |
| 7 | `original_language` | core_identity | P364 | 36 | 35 | 71 | unmapped:71 |
| 8 | `subtitle` | core_identity | — | 12 | 8 | 20 | node_llm_extraction:20 |
| 9 | `title` | core_identity | — | 36 | 27 | 63 | unmapped:44, wikisource_index:12, openrouter_transliteration:4, internet_archive:3 |
| 10 | `book_designer` | contributors | — | 0 | 0 | 0 | — |
| 11 | `compiler` | contributors | — | 0 | 3 | 3 | node_llm_extraction:3 |
| 12 | `cover_artist` | contributors | P736 | 0 | 0 | 0 | — |
| 13 | `cover_page_designer` | contributors | — | 0 | 0 | 0 | — |
| 14 | `editor` | contributors | P98 | 2 | 1 | 3 | unmapped:2, node_llm_extraction:1 |
| 15 | `translator` | contributors | P655 | 1 | 3 | 4 | node_llm_extraction:4 |
| 16 | `typesetting_by` | contributors | — | 1 | 0 | 1 | node_llm_extraction:1 |
| 17 | `typing_by` | contributors | — | 0 | 0 | 0 | — |
| 18 | `distributors` | publication | — | 5 | 1 | 6 | node_llm_extraction:6 |
| 19 | `place_of_printing` | publication | P2919 | 23 | 10 | 33 | node_llm_extraction:33 |
| 20 | `place_of_publication` | publication | P291 | 19 | 0 | 19 | unmapped:13, wikisource_index:6 |
| 21 | `printer` | publication | P872 | 20 | 11 | 31 | node_llm_extraction:31 |
| 22 | `publication_date` | publication | P577 | 36 | 12 | 48 | unmapped:17, internet_archive:16, wikisource_index:15 |
| 23 | `publisher` | publication | P123 | 21 | 12 | 33 | internet_archive:19, unmapped:12, wikisource_index:2 |
| 24 | `publisher_telugu` | publication | — | 11 | 0 | 11 | node_llm_extraction:11 |
| 25 | `sponsor` | publication | P859 | 3 | 2 | 5 | node_llm_extraction:3, internet_archive:2 |
| 26 | `awards` | content_classification | — | 0 | 0 | 0 | — |
| 27 | `context` | content_classification | — | 1 | 1 | 2 | node_llm_extraction:2 |
| 28 | `form_of_creative_work` | content_classification | P7937 | 29 | 0 | 29 | unmapped:21, wikisource_index:8 |
| 29 | `genre` | content_classification | P136 | 18 | 10 | 28 | node_llm_extraction:17, commons_category:11 |
| 30 | `inception` | content_classification | P571 | 18 | 3 | 21 | node_llm_extraction:21 |
| 31 | `subject` | content_classification | P921 | 26 | 22 | 48 | internet_archive:29, node_llm_extraction:19 |
| 32 | `edition_number` | edition_series | P393 | 2 | 6 | 8 | node_llm_extraction:8 |
| 33 | `edition_or_translation_of` | edition_series | P629 | 1 | 2 | 3 | node_llm_extraction:3 |
| 34 | `part_of_series` | edition_series | — | 4 | 1 | 5 | node_llm_extraction:5 |
| 35 | `part_of_the_set` | edition_series | — | 0 | 0 | 0 | — |
| 36 | `serial_number_in_series` | edition_series | — | 3 | 1 | 4 | node_llm_extraction:4 |
| 37 | `volume` | edition_series | P478 | 1 | 2 | 3 | node_llm_extraction:2, unmapped:1 |
| 38 | `based_on` | relationships | P144 | 0 | 2 | 2 | node_llm_extraction:2 |
| 39 | `first_published_in` | relationships | — | 0 | 0 | 0 | — |
| 40 | `inspired_by` | relationships | P941 | 0 | 1 | 1 | node_llm_extraction:1 |
| 41 | `abbreviations` | ancillary_content | — | 0 | 0 | 0 | — |
| 42 | `authors_in_compilation` | ancillary_content | — | 12 | 9 | 21 | node_llm_extraction:21 |
| 43 | `dedication` | ancillary_content | — | 2 | 2 | 4 | node_llm_extraction:4 |
| 44 | `dedication_verbatim` | ancillary_content | — | 2 | 2 | 4 | node_llm_extraction:4 |
| 45 | `forewords` | ancillary_content | — | 3 | 2 | 5 | node_llm_extraction:5 |
| 46 | `opinions_messages` | ancillary_content | — | 0 | 1 | 1 | node_llm_extraction:1 |
| 47 | `scribes` | ancillary_content | — | 0 | 0 | 0 | — |
| 48 | `illustrators` | physical_extra | — | 0 | 0 | 0 | — |
| 49 | `pages` | physical_extra | P1104 | 16 | 11 | 27 | internet_archive:27 |

## Per-book

| Book | Lang | Filled / 49 | Status |
|---|---|---|---|
| 2015.263752.Sadhu-Aur | hin | 21 | verified |
| Muntakhabat-i-hindi_Vol._1_Ed._5th_IA_in.ernet.dli.2015.94432 | hin | 17 | verified |
| 5व_जल_सम_म_लन_9-12_नवम_बर_05 | hin | 16 | verified |
| Biography_of_Freedom_fighter_Mahadev_Mishra | hin | 16 | verified |
| Gandhi_-_Delhi_Diary_Hindi | hin | 15 | verified |
| Gandhi_-_Dakshin_Afrika_Ke_Satyagraha_Hindi | hin | 14 | verified |
| Hindi_Ke_Musalman_Kavi_-_Ganga_Prasad_Singh | hin | 13 | verified |
| Hindi_Sahitya_ka_Itihas_by_Acharya_Ramchandra_Shukla | hin | 13 | verified |
| Prabhu-Padhare | hin | 13 | verified |
| 19140101_Priyapravaas_Hindi_PDF | hin | 11 | verified |
| Bhakta_Mala_of_Nabhadas_Ayodhya_Edition_1905 | hin | 11 | verified |
| Lūka_racita_susamācāra_aura_Preritoṃkī_kriyāoṃkā_vṛttānta._IA_lukaracitasusama00unse | hin | 11 | verified |
| 1913_Ummed_Singh_Charitra_Hindi_PDF | hin | 10 | verified |
| Bharatiya_Sampatti_Shastra | hin | 10 | verified |
| Thalua_Club_-_Babu_Gulabrai | hin | 10 | verified |
| Śiva_parīkshā._IA_sivapariksha00unse | hin | 10 | verified |
| अय_ध_य_क_इत_ह_स | hin | 10 | verified |
| आल_हखण_ड | hin | 10 | verified |
| Antarrashtriya_Gyankosh | hin | 8 | verified |
| Veer_Punjabi_-_Bhimsen_Vidyalankar | hin | 8 | verified |
| अह_स_Ahimsa_by_M._K._Gandhi | hin | 8 | verified |
| Shri_Chandravali_-_Bharatendu_Harishchandra_-_1933 | hin | 7 | verified |
| इ_श_अल_ल_ह_ख_न_-_र_न_क_तक_क_कह_न | hin | 7 | verified |
| Dayanand_Granthmala_Bhag_1_1925 | hin | 6 | verified |
| Srimad_Bhagavad_Gita_Bhavartha_Translation_by_Gadadhar_Singh_1896 | hin | 6 | verified |
| Tulsichaura-Hindi | hin | 6 | verified |
| अर_वल_क_आ_स | hin | 6 | verified |
| अरवर_नद_क_प_नर_जन_म_क_कथ | hin | 6 | verified |
| आप_और_म_-_क_र_ब_र_म | hin | 6 | verified |
| क_श_क_भ | hin | 6 | verified |
| कव_त_क_म_द | hin | 6 | verified |
| Godan_-_Premchand_-_Hindi_Novel | hin | 5 | verified |
| आह_र_तत_त_व | hin | 5 | verified |
| कर_त_तव_य_श_स_त_र | hin | 5 | verified |
| Yeh_Gali_Bikau_Nahin-Hindi | hin | 4 | verified |
| 1857_మ_స_ల_ల | tel | 24 | verified |
| 2015.373190.Athma-Charitramu | tel | 21 | verified |
| 10879telugukaavy034400mbp | tel | 19 | verified |
| 1917_Prataparudreeyamu_Ratnapanasahitam_Telugu_PDF | tel | 19 | verified |
| 1927_shhadchakravartulayindrajaalapukathalu_Telugu_PDF | tel | 19 | verified |
| 1895_SarpaVishayaSarvasvaSangrahamu_Telugu_PDF | tel | 18 | verified |
| A_Collection_of_Telugu_Proverbs | tel | 18 | verified |
| A_Collection_of_Telugu_Proverbs_translat_1 | tel | 18 | verified |
| 19220101_BrahmaVidya_Telugu_Pdf | tel | 17 | verified |
| 19380101_Savitri_Natakamu_Telugu_PDF | tel | 17 | verified |
| 2030020025431_-_chitra_leikhanamu | tel | 17 | verified |
| 19280101_AngleyaVaidyaRahasyamu_Telugu_PDF | tel | 16 | verified |
| Aanandhanga_Undalante_VBS_JVV | tel | 15 | verified |
| Abalaa_sachcharitra_ratnamaala | tel | 15 | verified |
| Abalaa_sachcharitra_ratnamaala_Dvitiiya_Sanputa | tel | 15 | verified |
| 10031upanishhats033596mbp | tel | 14 | verified |
| 10049upanyaasans033612mbp | tel | 14 | verified |
| 19330101_AndhrashabdaChinthamani_Telugu_pdf | tel | 14 | verified |
| 2015.328360.Andhra-Mahaniyulu | tel | 14 | verified |
| 2015.372978.Andhra-Kavithva | tel | 14 | verified |
| 19220101_SriSugunaMani_Telugu_PDF | tel | 13 | verified |
| 19240101_ChandrakantaNatakamu_Telugu_PDF | tel | 13 | verified |
| 19280101_Vasanthakumari_Telugu | tel | 13 | verified |
| 19300101_ShivarathriMahathmyamu_Telugu | tel | 13 | verified |
| ADIDAMU-SURAKAVI | tel | 13 | verified |
| 19230101_SangeetagoloBakavali_Telugu_PDF | tel | 12 | verified |
| 19250101_AndhranamaSangrahamuAndhraNamasheshamu_Telugu | tel | 12 | verified |
| .Kalidasa-Charitra_by_chilakamarthi_lakshminarasimham | tel | 11 | verified |
| 19230101_LavaKusa_Telugu_PDF | tel | 11 | verified |
| Akkanna_Maadannala_Charitra_Vedamu_Venkataraya_Sastri | tel | 10 | verified |
| 19270101_PranaDanamu_Telugu_Pdf | tel | 9 | verified |
| 19280101_JyothishyaVidyaPrakashika_Telugu | tel | 9 | verified |
| Acharya_SV_Jogarao_Sahitya_Varivasya_by_Velamala_Simmanna | tel | 9 | verified |
| Adhunikarajyanga025633mbp | tel | 8 | verified |
| Abraham_Lincoln_Telugu | tel | 7 | verified |
| Aliya_Rama_Rayalu | tel | 7 | verified |

Source key: `unmapped` = value present but `field_source` unset; `node_llm_extraction` = unverified model prefill (see `learnings/019`); catalog sources as named.
