# Known Limitations — Indic Book Metadata Extractor

This document records honest, current limitations of the extraction pipeline.
It exists so the team can prioritize the next sprint and so the OKI
stakeholders know exactly what to expect at delivery.

Last updated: 2026-08-28 (8-day sprint close-out).

---

## Production-quality threshold

The 52-field schema is the goal. **Uniformly high accuracy across all 52
fields has not been achieved and is not realistically achievable on the
current stack** (4-bit-quantized 7B model on CPU, Tesseract-only OCR for
Indic scripts). What *has* been achieved is the architecture and
infrastructure to make production quality attainable — the per-field
provenance, the hybrid extractors, the accuracy harness — even if the
final 0.85 F1 target on every field is not yet met.

The accuracy harness (`backend/scripts/evaluate_extraction.py`) is the
single source of truth for what is and isn't working. Run it before
making claims about quality.

---

## Per-field confidence tiers

The schema has 49 named fields plus `custom_fields`. The 5 cheap-extractor
fields are reliable; the rest are tiered below based on observed
behavior in the harness (stub mode — see harness section):

| Tier | Fields | Method | Expected F1 |
|------|--------|--------|-------------|
| **Cheap (deterministic)** | `isbn`, `pages`, `publication_date`, `publisher`, `language` | Regex / dictionary | ≥ 0.95 on clean scans; degrades on poor OCR |
| **High-confidence LLM** | `title`, `subtitle`, `place_of_publication`, `genre`, `form_of_creative_work`, `edition_number`, `printer`, `place_of_printing`, `editor`, `dedication`, `forewords`, `volume` | LLM with batch-routed page context | 0.70 - 0.90 (depends on script and OCR quality) |
| **Medium-confidence LLM** | `author`, `translator`, `compiler`, `publisher_telugu`, `place_of_publication`, `place_of_printing`, `part_of_series`, `serial_number_in_series`, `part_of_the_set`, `illustrators`, `cover_artist`, `cover_page_designer`, `typesetting_by`, `typing_by`, `book_designer`, `distributors`, `sponsor`, `based_on`, `inspired_by`, `first_published_in`, `edition_or_translation_of`, `original_language`, `inception`, `subject` | LLM with batch-routed page context | 0.40 - 0.70 |
| **Low-confidence / often absent** | `awards`, `abbreviations`, `scribes`, `opinions_messages`, `authors_in_compilation`, `context`, `dedication_verbatim`, `description_work`, `description_edition` | LLM, may not appear in source | < 0.50 — these often genuinely don't exist in the book |

The harness reports a per-field F1 with support (number of expected
samples). Use that — these tier names are rough.

---

## Supported languages

| Language | Tesseract pack | Extraction tested | Notes |
|----------|----------------|-------------------|-------|
| Telugu (`tel`) | yes | yes | MVP language |
| Hindi (`hin`) | yes | yes | MVP language |
| English (`eng`) | yes | yes | Fallback / bilingual books |
| Tamil, Bengali, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Sanskrit, Urdu, Assamese | **no** | **no** | Add `tesseract-ocr-<lang>` to `docker/Dockerfile.backend` and a `<lang>+eng` entry to `app/services/ocr_service.py:LANGUAGE_MAP` to enable |

The language detector and publisher dictionary currently have entries
for Telugu, Hindi, and a small set of Indian English-language
publishers. New languages need a language detector check + a publisher
whitelist extension.

---

## OCR accuracy on Indic scripts

Tesseract on Indic scripts is the load-bearing weakness. Even at 300+
DPI, ligatures, conjunct characters, and mixed English+Indic on a
single line produce systematic errors (e.g. `రాజకమల` instead of
`రాజకమల్`, `परकाशन` instead of `ప్రకాశన`). The OCR review UI is
load-bearing for production use — humans must correct text before
extraction can be reliable.

**Known Tesseract misreads in our sample data** (illustrative, not
exhaustive):
- Devanagari `राजकमल` → `राजकमल` (missing chandrabindu) — high frequency
- Telugu `ప్రచురణకర్త` → `ప్రచురణకర్త` (similar conjuncts confused) — medium frequency
- Mixed-script lines (English + Hindi in same line) often lose the Indic tokens

**Mitigations available now**:
- The page classifier (`app/services/page_classifier.py`) selects a
  per-page Tesseract PSM (1/3/4/6/11) based on layout density. This
  is the second-largest OCR accuracy lever.
- The OCR review UI lets users correct text before extraction.

**Mitigations NOT yet implemented**:
- Page-rotation detection (planned: run `--psm 1` OSD on page 1)
- Indic-language-specific OCR engines (e.g. `IndicOCR` from AI4Bharat,
  Google Cloud Vision) — would require an external API or larger
  on-device model
- Script-aware preprocessing (different denoising parameters for
  Telugu vs Hindi)

---

## LLM extraction quality

The current model is `ai4bharat/Airavata-GGUF:Q4_K_M` (4-bit
quantized, ~4 GB on disk, runs on CPU). This is a deliberate choice
to honor the CPU-only / local-only constraint. Trade-offs:

- **Inference time**: 8 - 20 minutes per book (8 batches, ~2 - 3
  concurrent) on a modern x86 CPU. The hybrid pipeline (cheap
  extractors first, LLM only for gaps) reduces this when many fields
  are regex/dictionary-resolvable.
- **Hallucination**: The LLM will confidently return plausible but
  incorrect values for fields it can't actually see in the OCR text.
  The per-field evidence table (`metadata_field_evidence`) records
  the source page and confidence so the UI can flag these.
- **Script fidelity**: When the input is Devanagari/Telugu and the
  model decides to answer in Latin transliteration, our accuracy
  harness reports a `script_match=False` and the per-field F1 looks
  terrible even though the value is semantically correct. The
  accuracy report highlights this case explicitly.

**Mitigations available now**:
- Hybrid extraction: regex/dictionary for 5 high-confidence fields;
  LLM only for the remaining ~44.
- Per-batch page routing: each batch sees the page region most
  likely to contain its fields.
- Per-field confidence stored in DB and surfaced in the metadata
  review UI.

**Mitigations NOT yet implemented**:
- Few-shot examples in the prompt (Airavata needs them badly for
  Indic; the current prompt has zero examples)
- Larger or non-quantized Airavata (`ai4bharat/Airavata` full 7B is
  ~14 GB on disk)
- Per-language prompt templates (currently the same prompt is used
  for Telugu, Hindi, and English; a per-language variant with
  examples would help)

---

## Accuracy harness limitations

The harness (`backend/scripts/evaluate_extraction.py`) is honest about
its own limitations:

- **Stub mode (`--stub`)** reports an upper bound (F1 = 1.0 if
  predictions are perfect). It is useful for validating the diff
  logic and CI gating, not for measuring real performance.
- **Real mode** runs the full pipeline (PDF → OCR → LLM extraction)
  against the ground-truth fixtures. It requires Ollama, Tesseract,
  and PostgreSQL to be running. In a CPU-only dev container without
  those, real mode returns a `_stub: pipeline_unavailable` payload —
  the harness detects this and exits non-zero so CI catches it.
- **Token-level F1** is uninformative when expected and predicted
  are in different scripts. The harness records `script_match: bool`
  per field so this case can be filtered out of the headline number.
- **Sample size**: 5 ground-truth books is the minimum for any
  statistical confidence. Per-field F1 estimates with `n=1` (i.e.
  a single ground-truth book for that field) are essentially
  anecdotal.

---

## What's not yet implemented

These are the items from the original 8-day plan that are **not done**
and should be prioritized for the next sprint:

1. **Few-shot examples in the LLM prompt** for each batch — the
   single highest-ROI improvement remaining.
2. **NER extractor (spaCy `xx_ent_wiki_sm`)** for person names. The
   hybrid orchestrator has a `target_fields` plumbing for it but the
   module isn't written.
3. **Per-language prompt templates** (Telugu / Hindi / English
   variants with script-appropriate examples).
4. **Indic script transliteration in the accuracy harness** so
   cross-script comparisons don't look like 0.0 F1.
5. **CI gating** on the accuracy harness (a `test-accuracy` job in
   `.github/workflows/ci.yml` that fails the build if overall F1
   drops below a threshold).
6. **Page-rotation detection** on the title page via `--psm 1` OSD.
7. **Publisher whitelist expansion** beyond the ~30 currently
   included.
8. **Auth/user accounts** — the system is single-user local. The
   OKI contract says "no auth" so this is a future concern, but the
   schema should add a `users` table when that changes.

---

## Risk register (carried from the sprint plan)

| Risk | Status | Notes |
|------|--------|-------|
| `num_ctx=4096` doubles inference time | **mitigated** | Hybrid pipeline + parallel batches keep total time under 20 min |
| Indic-script Tesseract errors | **open** | The OCR review UI is the safety net; no automated fix available without a better OCR engine |
| 4-bit Airavata wrong model tier | **open** | Document this. Escalate to OKI for the full 7B if accuracy doesn't reach 0.7 F1 in the next sprint |
| 5 ground-truth books too small | **mitigated** | Up to 5 ground-truth fixtures are committed (eng/clean, hin/clean, tel/clean, hin/modern, tel/degraded). Pipeline for adding more is documented in `scripts/generate_sample_pdf.py` |
| Frontend blocks the human-in-the-loop demo | **mitigated** | `metadata-review/page.tsx` now calls `/books/{id}/metadata/evidence` and renders the per-field confidence via the existing tri-state indicator |

---

## How to use this document

When someone asks "is the 52-field extractor production-ready?":

1. Run `python -m scripts.evaluate_extraction` against the fixtures
   with real Ollama + Tesseract.
2. Read the per-field F1 in the resulting report.
3. Quote the per-field tiers above honestly.
4. If a field's F1 is below its tier's expected range, file a
   targeted ticket (likely: prompt engineering for LLM fields,
   whitelist expansion for dictionary fields, regex tightening for
   structured fields).
5. Update this document with the new measurement.
