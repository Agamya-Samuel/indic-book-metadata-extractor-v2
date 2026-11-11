# 004 — PoC: Telugu Wikisource as OCR ground truth (milestone 1 of plans/003)

- **Date:** 2026-11-11
- **Status:** Validated — Telugu GT available; Hindi GT not available from Wikisource
- **Serves:** [plans/003-ocr-engine-evaluation.md](../plans/003-ocr-engine-evaluation.md) milestone 1 (corpus + GT alignment), success criterion 2
- **Artifacts:** `backend/scripts/fetch_wikisource_gt.py`, `backend/tests/fixtures/ground_truth/{tel}/<slug>/wikisource_gt.json`

## Question

Can page-level OCR ground truth be built for real Commons scans **without hand
transcription**, so that CER/WER can be measured on the actual books in the
corpus? Specifically: does the local `original.pdf` correspond page-for-page to
the Wikisource `Page:` records that hold human-verified text?

## Method

`fetch_wikisource_gt.py` does five things per book:

1. Resolves the target wiki's `Index:`/`Page:` namespace IDs from `siteinfo`.
2. Verifies file identity: SHA1 of the local PDF vs the Commons `imageinfo` SHA1.
3. Locates the book's `Index:` page by searching the target wiki.
4. Enumerates `Page:` records and reads each page's proofreading level from
   `pageprops`.
5. Downloads text for verified pages (level 3–4) only, cleaning ProofreadPage
   markup.

```bash
cd backend
uv run python -m scripts.fetch_wikisource_gt \
    --book-dir tests/fixtures/ground_truth/tel/2015.373190.Athma-Charitramu --max-text 40
```

## Results

| Book | PDF pages | `Page:` records | Levels | Verified | Texts fetched | SHA1 |
|---|---|---|---|---|---|---|
| `tel/2015.373190.Athma-Charitramu` | 691 | 691 | 0=18, 3=4, 4=669 | **673** | 39 | match |
| `tel/2015.328360.Andhra-Mahaniyulu` | 90 | 90 | 0=5, 1=1, 3=52, 4=32 | **84** | 40 | match |

**757 verified pages** across two books, with **100% page-record coverage** in both
(691/691 and 90/90). Every fetched page carries its level, its Wikisource title
and its text; two pages' worth of text extraction problems were eliminated to
zero flagged `markup_residue` by the rendered-text fallback (below).

## Alignment validation (the point of the milestone)

Three independent checks, all passing:

1. **Byte identity.** Local PDF SHA1 equals the Commons file SHA1 exactly
   (`500985ba…` for Athma, `17afe51c…` for Andhra). Since `Page:<file>/<n>` is by
   construction page *n* of that file, positional alignment follows — this is the
   load-bearing check, and it is why SHA1 is verified rather than assumed.
2. **Complete coverage.** Every PDF page has a `Page:` record. A gap here would
   mean the numbering is offset; there is none.
3. **Visual spot checks.** Rendering at the aligned page number and comparing
   against the fetched text:

   - Athma p.3 (title page) — GT reproduces `ఆంధ్రగ్రంథమాల : 22 / AUTOBIOGRAPHY: /
     R. Venkata Sivudu, M. A., L. T., / GUNTUR / ఆత్మచరిత్రము. / గ్రంథకర్త: … /
     ఆంధ్ర పత్రికా ముద్రాలయము : మద్రాసు / 1933`.
   - Athma p.7 (verse) — GT reproduces the verse line-for-line, including the `♦`
     caesura marks.
   - Andhra p.20 (body) — GT text begins precisely at the scan's first line, and
     correctly **excludes** the running header `విశ్వనాథుని చరిత్రము 17`.

## Findings that change the harness

1. **Verified ≠ has text.** Athma p.9 is level 4 (validated) but is a full-page
   image (`{{Css image crop}}`); after cleaning it yields no text and is skipped.
   Page sampling must filter on *text present*, not level alone.
2. **Running headers/footers are excluded** (they live in `<noinclude>`), which is
   correct for body text and important for scoring: a header would otherwise be
   counted as dozens of OCR errors per page.
3. **Overlaid stamps are absent from GT.** Athma's title pages carry a
   "Donated in Memory of Late Sri P N V Rao" stamp that no transcriber recorded.
   Any engine that reads the stamp is *penalised* for text the GT lacks. This
   inflates metadata-page CER for every engine equally, so it does not bias the
   comparison — but the absolute numbers must be reported with this caveat.
4. **Duplicate scans exist.** Athma pp.3 and 5 are the same page scanned twice,
   with identical GT. Harmless for CER, but they are not independent samples and
   must be de-duplicated when reporting per-page distributions.
5. **Front matter needs rendered text, not wikitext.** Contents pages
   (Athma pp.31–37) are assembled from `{{dotted TOC page listing|…}}` whose
   arguments are *not* the visible text. Wikitext cleaning produced either raw
   template markup or, worse, wikilink targets that are not on the scan
   (`ఆత్మచరిత్రము/ప్రథమభాగము : …`). Rendering the page and stripping tags yields the
   real text (`1. బాల్యము 1`, `18. నూతన దృక్పథం 67`), with the ProofreadPage status
   banner removed by its CSS class and dotted leaders collapsed.
6. **Corrections to the earlier desk numbers.** Counts taken from Index-page HTML
   were inflated by double-counting (the pagelist is rendered twice). The
   authoritative `pageprops` counts are 673 and 84 verified pages, not 812 and 86
   — i.e. **757**, not 898.

## Two API traps worth recording

- **Namespace IDs are per-wiki.** Telugu uses Index=106/Page=104; Hindi uses
  Index=252/Page=250. The documented 102/104 defaults silently return author and
  mainspace pages.
- **The proofreading level lives under `proofread_page_quality_level`**, not the
  documented `proofread-page-quality`. Filtering `ppprop` on the documented name
  returns no props at all, which reads as "no page is proofread" — the exact
  failure mode that would have discarded the whole corpus.

## Limits

- Telugu only; the Hindi side is unchanged and still needs the hand-transcribed
  metadata scope described in plans/003.
- 40 pages per book are fetched by default (`--max-text`), not all verified pages;
  raising it is a CLI flag, not a code change.
- No OCR has been run yet — this milestone proves the *ground truth*, not engine
  accuracy.
- Text is NFC-normalised only; Indic normalisation choices (ZWJ, akshara
  segmentation) belong to the harness.

## Next

Milestone 2: harness (PDF → render @300 DPI → engine → CER/WER + RSS/time),
scoring against `wikisource_gt.json`, excluding `markup_residue` pages and
filtering page types (title / contents / body) so that the metadata-region
number in decision 4a is separable from body-text accuracy.
