# OCR Setup

How OCR is installed, configured and run in the Indic Book Metadata Extractor.

- **Engines:** Tesseract 5 via `pytesseract` for Hindi/English, plus the Telugu
  line model `harsha-desaraju/telugu-ocr-model` (CPU torch + transformers). The
  line model is the production default for Telugu; Tesseract is the fallback.
- **Not in production:** PaddleOCR exists only in the offline benchmark harness
  (`backend/scripts/ocr_bench/`).
- **Where it runs:** never in the API process. OCR runs in the Celery worker
  (queue `ocr`).

---

## 1. What gets installed

### 1.1 System packages (OS)

Declared in `docker/Dockerfile.backend`:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-osd \
    tesseract-ocr-tel \
    tesseract-ocr-hin \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*
```

| Package | Why |
|---|---|
| `tesseract-ocr` + `-osd` | OCR binary and orientation/script detection |
| `tesseract-ocr-tel` | Telugu (`tel`) language data |
| `tesseract-ocr-hin` | Hindi/Devanagari (`hin`) language data |
| `tesseract-ocr-eng` | English (`eng`) — always combined as `<lang>+eng` |
| `libgl1`, `libglib2.0-0` | OpenCV runtime |
| `poppler-utils` | Installed but **not used**; PDFs are rasterized with PyMuPDF (`fitz`) |

Stock Tesseract models are used — there is no custom model install for Hindi
or English.

### 1.2 Python packages

Declared in `backend/pyproject.toml` and locked in `backend/uv.lock`:

```toml
dependencies = [
    "pymupdf>=1.24",              # PDF rasterization (fitz)
    "pillow>=10.3",               # pytesseract image I/O
    "opencv-python-headless>=4.9",
    "numpy>=1.26",
    "pytesseract>=0.3.10",
    "python-Levenshtein>=0.25",   # CER/WER in eval scripts
    "celery[redis]>=5.4",
    # ...
]

[project.optional-dependencies]
ocr-line = [
    "torch>=2.2",
    "transformers==4.46.*",
]
```

`transformers` is pinned to `4.46.*` on purpose: 5.x breaks the line model's
custom code (`all_tied_weights_keys`). Torch is pinned to CPU-only wheels:

```toml
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cpu" }
```

### 1.3 Telugu line model weights

`docker/Dockerfile.backend` bakes the model into the image only when the
`OCR_LINE=true` build arg is passed:

```dockerfile
ARG OCR_LINE=false
RUN uv sync --no-dev $([ "$OCR_LINE" = "true" ] && echo "--extra ocr-line")
RUN if [ "$OCR_LINE" = "true" ]; then \
      .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('harsha-desaraju/telugu-ocr-model', local_dir='/app/ocr_models/telugu-ocr-model')"; \
    fi
```

The weights (~310 MB) are **never downloaded at runtime**. Production sets
`HF_HUB_OFFLINE=1` to guarantee this.

---

## 2. Local development setup

### Linux

```bash
sudo apt install -y tesseract-ocr tesseract-ocr-tel tesseract-ocr-hin tesseract-ocr-eng
```

### macOS (Homebrew)

```bash
brew install tesseract-lang        # includes tel/hin/eng
```

### Python

```bash
cd backend
uv sync                            # base deps, Tesseract only
# optional: Telugu line engine
uv sync --extra ocr-line
```

### Without Docker

1. `.env` (or environment): `TESSERACT_CMD=tesseract`
   (this is the dev default — Tesseract, no line model).
2. Start Postgres + Redis, run migrations (`alembic upgrade head`).
3. Run the Celery worker against the `ocr` queue:

   ```bash
   uv run celery -A app.tasks.celery_app worker --loglevel=info -Q ocr,default
   ```

Note: `OCR_TEL_ENGINE=line_model` in dev is pointless unless you also have
torch/transformers and the weights locally — each page will fall back to
Tesseract and record `page.ocr_error`.

---

## 3. Docker setup

### 3.1 Dev (`docker-compose.yml`)

| Service | Role |
|---|---|
| `backend` | FastAPI; creates OCR jobs, never runs OCR itself |
| `worker-ocr` | Celery worker, `-Q ocr,default`, `--concurrency=1` |
| `worker-llm` | Celery worker, `-Q llm` |
| `flower` | Task monitor at `:5555` |

`worker-ocr` builds `Dockerfile.backend` **without** `OCR_LINE`, so dev has no
line model. Relevant env:

```yaml
OCR_BATCH_SIZE: ${OCR_BATCH_SIZE:-10}
OCR_THREAD_WORKERS: ${OCR_THREAD_WORKERS:-4}
OCR_RENDER_DPI: ${OCR_RENDER_DPI:-300}
```

### 3.2 Staging / Production (`docker-compose.staging.yml`, `docker-compose.production.yml`)

A single `worker` handles `ocr,llm,default`, with the line model baked in:

```yaml
worker:
  image: app-jb5tjz-worker
  build:
    context: ./backend
    dockerfile: ../docker/Dockerfile.backend
    args:
      OCR_LINE: "true"
  command: ["uv", "run", "celery", "-A", "app.tasks.celery_app", "worker",
            "--loglevel=info", "--concurrency=1", "-Q", "ocr,llm,default"]
  environment:
    TESSERACT_CMD: tesseract
    OCR_TEL_ENGINE: ${OCR_TEL_ENGINE:-line_model}
    OCR_LINE_MODEL_NAME: /app/ocr_models/telugu-ocr-model
    HF_HUB_OFFLINE: "1"
    OCR_BATCH_SIZE: ${OCR_BATCH_SIZE:-10}
    OCR_THREAD_WORKERS: ${OCR_THREAD_WORKERS:-4}
    OCR_RENDER_DPI: ${OCR_RENDER_DPI:-300}
```

The model lives **only inside the worker image** — no `ocr_models` volume is
mounted. The `backend` service sets `OCR_TEL_ENGINE=tesseract` (it doesn't OCR).

`--concurrency=1` is required: the line model is loaded once per process behind
a `threading.Lock` (`backend/app/services/ocr_line_model.py`).

---

## 4. Configuration reference

All settings live in `backend/app/core/config.py` (`Settings`, env prefix
`OCR_*` unless noted).

| Setting | Default | Meaning |
|---|---|---|
| `TESSERACT_CMD` | `tesseract` | Path to the binary |
| `TESSERACT_OEM` | `1` | Tesseract engine mode (1 = LSTM) |
| `TESSERACT_TESSDATA_DIR` | `""` | Tessdata directory passed as `--tessdata-dir`; must contain every language the OCR path loads (e.g. `hin` + `eng`) |
| `OCR_RENDER_DPI` | `300` | PDF rasterization + `--dpi` passed to Tesseract |
| `OCR_BATCH_SIZE` | `10` | Pages per batch |
| `OCR_THREAD_WORKERS` | `4` | Thread workers for page batches |
| `OCR_TEL_ENGINE` | `tesseract` (dev) / `line_model` (staging+prod) | Telugu engine selector |
| `OCR_LINE_MODEL_NAME` | `harsha-desaraju/telugu-ocr-model` | HF id or local path; production defaults to `/app/storage/models/telugu-ocr-ft` |
| `OCR_LINE_MODEL_FALLBACK_NAME` | `/app/ocr_models/telugu-ocr-model` | Baked base checkpoint used when the fine-tuned path is absent |
| `OCR_LINE_MODEL_DECODE` | `ctc` | Decoding strategy |
| `OCR_LINE_MODEL_CONFIDENCE` | `50.0` | Synthetic confidence stored per line |
| `OCR_SCRIPT_ROUTING` | `true` | Re-run Latin-dominated line-model pages through Tesseract and keep the better-coverage result |
| `OCR_USE_DICTIONARY` | `""` | Comma-separated langs, e.g. `hin,tel` (Tier 4) |
| `OCR_POSTPROCESS` | `true` | NFC/danda/ZWJ normalization (Tier 5) |
| `OCR_LOW_CONF_RETRY` | `true` | Re-OCR words below threshold at `--psm 8` |
| `OCR_LOW_CONF_THRESHOLD` | `40` | Confidence below which retry fires |
| `OCR_BINARIZATION` | `sauvola` | `sauvola`/`otsu`/`adaptive`/`none` |
| `OCR_DENOISE_STRENGTH` | `7` | Non-local-means strength |
| `OCR_UPSCALE_DPI` | `300` | Target DPI for upscaling |

Per-page preprocessing is also configurable (stored on `Page.preprocessing_config`,
schema in `backend/app/schemas/page.py`): `binarization`, `sauvola_window`
(default 25), `sauvola_k` (0.2), `deskew`, `denoise`, `upscale_to_300dpi`,
`remove_borders`, `rotation`, `rotation_angle`.

---

## 5. How a page is OCR'd

Pipeline source files:

| File | Responsibility |
|---|---|
| `backend/app/tasks/page_tasks.py` | `render_pages_for_book` — PDF → PNG at `OCR_RENDER_DPI` via PyMuPDF |
| `backend/app/tasks/ocr_tasks.py` | Celery `preprocess_pages_for_book` → `run_ocr_for_book` |
| `backend/app/services/preprocessing.py` | OpenCV pipeline (grayscale, binarize, deskew, borders, upscale) |
| `backend/app/services/page_classifier.py` | Picks the Tesseract `--psm` |
| `backend/app/services/ocr_service.py` | Tesseract pass + low-confidence retry |
| `backend/app/services/ocr_line_model.py` | Telugu line model |
| `backend/app/services/ocr_postprocess.py` | Text normalization |
| `backend/app/services/ocr_dictionaries.py` | `--user-words` / `--user-patterns` files |

### 5.1 Preprocessing

`run_pipeline()` order (`preprocessing.py`):

coarse rotate → upscale to 300 DPI if the source is below it (cubic) →
grayscale → brightness/contrast → denoise (optional) → binarization
(otsu / adaptive / sauvola) → deskew → fine rotate (±15°) → remove borders →
write.

`source_dpi` is the DPI the page was rendered at and defaults to
`OCR_RENDER_DPI`, so a page already rendered at 300 DPI is **not** rescaled.
(It used to assume a 200-DPI source and upscale every page 1.5×; that raised
median CER from 0.285 to 0.365 on 18 Telugu pages — see `learnings/027`.)

Defaults (`DEFAULT_PREPROCESSING_CONFIG`):

- `binarization: None` and `denoise: False` — Sauvola + denoise erode the
  shiro-rekha and measurably hurt Indic scripts.
- `grayscale`, `deskew`, `remove_borders` are on but are **inert** on 300-DPI
  library scans: deskew only fires above 0.5°, border removal only when the
  border exceeds 30 % of a dimension, and grayscale does not change what
  Tesseract recognises. Measured on 18 pages, they changed nothing.

Note: `run_pipeline` is executed for any page whose `preprocessing_config` is
set, and `page_tasks` attaches the default config at render time — so the
"only binarization/denoise are off" description above is the accurate one, not
"preprocessing is off by default".

### 5.2 PSM selection

`classify_page()` runs a cheap connected-components analysis on a 400px
downsample:

- Many text components → `--psm 3` (`AUTO`, label `default_auto`)
- Sparse (`< 40` components and density `< 0.08`) → `--psm 4`
  (`SINGLE_COLUMN`, label `sparse_colophon_or_blank`)
- Failure → `--psm 6` (`UNIFORM_BLOCK`, label `classifier_failed`)

`--psm 11` is deliberately avoided for whole pages — it reads borders as Latin
rubble and drops matras.

### 5.3 Tesseract invocation

Language map (`ocr_service.LANGUAGE_MAP`):

```python
{"tel": "tel+eng", "hin": "hin+eng", "eng": "eng"}
```

Config string built by `_build_config`:

```text
--psm <3|4|6> --oem 1 --dpi 300 [--user-words "<path>"] [--user-patterns "<path>"]
```

`--user-words` / `--user-patterns` are added when `OCR_USE_DICTIONARY` is set
and dictionary files exist for the language. Word boxes come from
`pytesseract.image_to_data(... Output.DICT)`; words with `conf < 0` or empty
text are dropped. Average confidence is the mean word confidence.

Low-confidence retry (`retry_low_confidence_words`): each word below
`OCR_LOW_CONF_THRESHOLD` is cropped and re-OCR'd with:

```text
--psm 8 --oem 1 --dpi 300
```

The retry replaces the text only if it differs, and sets
`confidence = max(old, threshold)` and `retried = true`.

### 5.4 Telugu line model

When `OCR_TEL_ENGINE=line_model` and language is `tel`,
`ocr_line_model.run_line_ocr()`:

1. Segments lines with Tesseract (`--psm 6`, `lang=tel`), grouping word boxes
   by `(block_num, par_num, line_num)`.
2. Crops each line, calls `model.transcribe(crops, tokenizer, decode=...)`.
3. Emits one `word` per line, `confidence = OCR_LINE_MODEL_CONFIDENCE` (50.0),
   `engine = "line_model"`.

Word-level retry is skipped for the line model (its boxes are line-level).
Any exception falls back to Tesseract for that page and records
`engine_fallback_reason`, surfaced as:
`page.ocr_error = "Telugu line OCR fell back to Tesseract: <reason>"`.

### 5.5 Post-processing

`normalize_text()` (`ocr_postprocess.py`):

1. NFC normalization (`nfc_normalize`)
2. Danda cleanup: `|| → ॥`, then `| → ।` (`danda_normalize`)
3. Strip ZWJ `\u200d` / ZWNJ `\u200c` (`strip_spurious_zwj/zwnj`)

Applied only when `OCR_POSTPROCESS=true`. Known caveat: the danda cleanup
currently runs for every language, including `eng`.

`process_page_image()` is the single production pass and returns `words`,
`raw_text`, `cleaned_text`, `corrections`. It is shared by the worker and the
evaluation corpus builder, so frozen eval text matches production.

### 5.6 Persistence and handoff

`run_ocr_for_book` writes an `OcrResult` per page:
`raw_text`, `bounding_boxes={"words": [...]}`, `confidence`,
`language_detected`, `cleaned_text`, `corrections={"rules": [...]}`.

Job completion advances the book to `OCR_COMPLETE`; `POST /api/extraction/...`
refuses to start LLM extraction unless OCR text exists.

---

## 6. Triggering OCR

| Endpoint | Purpose |
|---|---|
| `POST /api/books/{book_id}/run-ocr` | Start OCR (book must be `PAGES_SELECTED`) |
| `GET /api/books/{book_id}/ocr-status` | Per-page OCR state, complete/pending counts |
| `GET /api/books/{book_id}/pages?include_ocr=1` | OCR text per page |
| `GET /api/pages/{page_id}/ocr` | Raw text, word boxes, confidence |
| `PUT /api/pages/{page_id}/ocr` | Save `corrected_text` (row-locked) |
| `PUT /api/pages/{page_id}/preprocessing` | Re-run preprocessing for a page |
| `POST /api/pages/{page_id}/preprocessing/preview` | Preview binarization |

Frontend: `ocr-review` (bounding-box canvas + corrections), `ocr-processing`
(progress), `preprocessing` (binarization/deskew controls).

---

## 7. Verification and evaluation

```bash
# Unit tests
cd backend && uv run pytest tests/unit/test_ocr_service.py \
  tests/unit/test_ocr_engine_dispatch.py tests/unit/test_ocr_line_model.py \
  tests/unit/test_page_classifier.py tests/unit/test_preprocessing.py

# CER/WER against the Wikisource ground truth
TESSDATA_PREFIX=/tmp/tessdata uv run python -m scripts.eval_ocr \
  --limit 3 --pages 4 --preprocess none --dpi 300

# Benchmarks (Tesseract / PaddleOCR / line model)
cd backend && python -m scripts.ocr_bench.bench

# Preprocessing effect, Tesseract path (learnings/027)
HF_HUB_OFFLINE=1 TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast \
  .venv/bin/python scripts/ocr_bench/bench_preprocess.py --books 8 --pages 3

# Preprocessing effect, Telugu line model (learnings/028; needs torch + cached weights)
HF_HUB_OFFLINE=1 TESSDATA_PREFIX=/tmp/ocr-eval/tessdata_fast \
  ~/.cache/ocr-line-venv/bin/python scripts/ocr_bench/bench_lines_preprocess.py --books 8 --pages 3
```

Makefile helpers:

```bash
make logs-worker-ocr     # tail OCR worker logs
make rebuild             # rebuild images without cache + restart
make migrate             # alembic upgrade head (needed after OCR migrations)
```

Accuracy reference (`learnings/020`, `docs/known-issues.md`):

| Engine | Language | Median CER | Median WER | s/page |
|---|---|---|---|---|
| Tesseract 5 | `tel` | 0.402 | 0.989 | 2.0 |
| PaddleOCR PP-OCRv4 | `te` | 0.511 | 0.974 | 13.0 |
| `telugu-ocr-model` (CTC) | `tel` | **0.163** | 0.600 | 3.8 |
| Tesseract 5 | `hin` | **0.072** | 0.25 | 2.3 |

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `TesseractNotFoundError` | Binary missing or `TESSERACT_CMD` wrong. Install `tesseract-ocr` or set the path. |
| `Failed loading language 'tel'` | `tesseract-ocr-tel` not installed; `tessdata_dir` doesn't contain `tel.traineddata`. |
| Telugu pages all have `ocr_error: "line OCR fell back..."` | `OCR_TEL_ENGINE=line_model` but no torch/transformers/weights (common in dev). Build with `OCR_LINE=true` or set `OCR_TEL_ENGINE=tesseract`. |
| Worker OOM / slow first page | Line model loading (779 MB). Keep `--concurrency=1`; don't raise it. |
| Accuracy poor on body pages | Check `OCR_RENDER_DPI` (300), disable auto-preprocessing, verify the PSM label in logs. |
| Danda `।` inserted into English text | Fixed: `_danda_cleanup` is skipped when `language == "eng"` (regression test in `test_ocr_postprocess.py`). |
| Dictionaries ignored | `OCR_USE_DICTIONARY` must list the language (`hin,tel`); dictionary files must exist in `backend/app/services/dictionaries/`. |

### Adding a language

1. Add `tesseract-ocr-<lang>` to `docker/Dockerfile.backend`.
2. Add `<lang>: "<lang>+eng"` to `LANGUAGE_MAP` in `ocr_service.py`.
3. Add `<lang>.words` / `<lang>.patterns` to `backend/app/services/dictionaries/` if using dictionaries.
4. Rebuild (`make rebuild`).

---

## 9. Related docs

- `docs/ocr-postdeploy-runbook.md` — migration + post-deploy checklist
- `docs/ocr-training.md` — fine-tuning a Tesseract LSTM model (Tier 3)
- `docs/known-limitations.md` — supported languages, accuracy caveats
- `learnings/020-ocr-engine-benchmark.md` — engine selection decision
- `learnings/021-ocr-engine-operational-requirements.md` — runtime requirements matrix
- `plans/017-telugu-ocr-engine-integration.md` — line-model integration plan
- `docs/tech_stack.md` — stack overview
