# Glossary

Project vocabulary. Where a term has a precise meaning in the code, that meaning wins.

---

## Domain

**Indic** — languages written in Brahmic scripts. Here, supported in practice: Telugu (`tel`), Hindi
(`hin`), and English (`eng`).

**Book** — one uploaded PDF and everything derived from it. A `books` row plus pages, OCR, jobs and
metadata.

**Page** — one rendered PDF page. `page_number` is 1-based and refers to the PDF, not the printed
page number in the book.

**Front matter / back matter** — title page, copyright, dedication, foreword (front); colophon,
printer's note, back cover (back). These, not body text, carry inventorable metadata.

**Body page** — heuristically, a page with over 1,200 characters, over 14 non-empty lines, and no
bibliographic cue words. Used to stop the front/back windows from swallowing the whole book.

**Colophon** — the trailing page stating printer, print run, and sometimes dates. Reached by the
batch router's back-matter slices.

**Danda** — `।` (Devanagari/Telugu full stop) and `॥` (double danda). OCR often emits ASCII `|`.

**Shiro-rekha** — the horizontal headstroke joining Devanagari and Telugu letters. Binarization and
denoising can erode it, which is why both are off by default.

**Script routing** — re-running OCR with a different engine or language model when the first result's
script mix is wrong for the expected language.

**Line model** — the fine-tuned Telugu OCR model that reads whole text lines rather than words.

**Coverage** — `word_count / detected_lines`. A rough signal that OCR dropped lines.

---

## Pipeline

**Stage** — one of six backend steps: `upload`, `page_selection`, `ocr`, `llm_extraction`,
`human_review`, `completion`. Recorded per attempt in `book_stage_status`.

**Attempt** — a numbered run of a stage. Re-running a stage creates a new attempt; history is never
rewritten.

**Workflow step** — one of the seven UI steps. Adds `preprocessing` (a per-page setting, not a stage)
and splits OCR/review. Derived by `workflow-state.ts`.

**Job** — a durable `jobs` row representing one dispatch of background work. The source of truth for
progress and terminal state.

**Task** — a Celery task. Several jobs may map to the same task name; one job is one task invocation.

**Superseded** — a job for which a newer job of the same type exists for the same book. A superseded
task must not write results.

**Reaped** — a `running` job marked failed by the reaper because no progress was seen within
`STALE_JOB_MINUTES`.

**Pipeline lock** — the single global Redis lock (`pipeline:single-book`) that allows only one book
through the pipeline at a time.

**Preprocessing** — the OpenCV chain (rotate, upscale, grayscale, denoise, binarize, deskew, crop)
applied per page before OCR.

**Normalisation** — post-OCR text cleanup: NFC, danda repair, ZWJ/ZWNJ removal.

---

## Extraction

**Batch** — one of 8 field groups (`core_identity`, `contributors`, `publication`,
`content_classification`, `edition_series`, `relationships`, `ancillary_content`, `physical_extra`),
each a validated Pydantic model.

**Tier** — a stage of the hybrid extractor. Tier 1 regex, tier 2 dictionary, tier 3 LLM.

**Profile** — a named prompt pair (`V00`–`V12`). `V00` is production.

**Evidence** — the provenance row for one populated field: value, confidence, method, source page,
snippet.

**Mask** — evaluation classification of a ground-truth field: `visible`, `absent`, `unroutable`,
`not_in_scan`, `script_mismatch`.

**Presence score** — "did the model fill the field at all".

**Value score** — "is the value correct". Not the same thing; both are reported.

**Hallucination** — a non-null prediction where the text and ground truth have nothing.

---

## Infrastructure

**Core service** — required for the pipeline: postgres, redis, ollama, backend, worker, frontend.

**Core-adjacent** — `backup`. Tiny, and the only automated database backup.

**Non-essential service** — optional: wikibase, wikibase-jobrunner, wikibase-init, quickstatements,
mysql, elasticsearch, openrefine, flower.

**Compose profile** — Compose's native mechanism for conditionally including services. Verified to
work here, **not yet applied** to the production compose file.

**Dokploy** — the PaaS that runs the compose file and injects environment variables.

**Single-origin** — serving the frontend at `/` and the API at `/api` on the same host, which is what
makes cookie sessions and CSRF work.

**Media token** — a signed, resource-scoped, short-lived token that lets `<img>` fetch a page image
without a session cookie.

---

## Records

**Plan** (`plans/`) — intent, written before work.

**Learning** (`learnings/`) — evidence, written after work.

**`docs/`** — current truth. When a plan, a learning and the code disagree, trust the code and update
`docs/`.
