# OCR Pipeline Performance Optimization Plan

## Context

The OCR pipeline processes scanned Indic-language book PDFs through Tesseract via Celery tasks. The current architecture uses Celery chords with batches of 5 pages, but **pages within each batch are processed sequentially** (`ocr_tasks.py:137-145`). Since Tesseract is CPU-bound and spawns subprocesses, the effective throughput is limited to `worker_concurrency` (4) pages at a time, regardless of batch size.

**Goal**: Maximize OCR throughput by exploiting all available parallelism, separating CPU-bound phases, and tuning Tesseract settings.

## Changes

### 1. Add thread-based parallelism within batch tasks

**File**: `backend/app/tasks/ocr_tasks.py`

Replace the sequential `for` loop in `run_ocr_for_page_batch` with `concurrent.futures.ThreadPoolExecutor`. Since `pytesseract.image_to_data()` spawns a subprocess (releases the GIL), threading provides true parallelism for multiple Tesseract instances within a single Celery worker process.

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

OCR_THREAD_WORKERS: int = 4  # configurable via settings

@celery_app.task(...)
def run_ocr_for_page_batch(self, page_id_strs, book_id_str, language):
    results = [None] * len(page_id_strs)
    
    def process_idx(idx):
        page_id = page_id_strs[idx]
        try:
            return idx, _process_page(page_id, book_id_str, language)
        except Exception as e:
            return idx, {"page_id": page_id, "success": False, "error": str(e)}
    
    with ThreadPoolExecutor(max_workers=OCR_THREAD_WORKERS) as executor:
        futures = [executor.submit(process_idx, i) for i in range(len(page_id_strs))]
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result
    
    return results
```

**Impact**: With `OCR_THREAD_WORKERS=4` and `worker_concurrency=4`, throughput goes from ~4 pages concurrently to ~16 pages concurrently (4 workers × 4 threads). A 20-page book drops from ~5 batch rounds to ~2.

### 2. Make concurrency and batch size configurable

**File**: `backend/app/core/config.py`

Add settings:
```python
ocr_batch_size: int = 5
ocr_thread_workers: int = 4
```

**File**: `backend/app/tasks/ocr_tasks.py`

Replace hardcoded `OCR_BATCH_SIZE = 5` with `settings.ocr_batch_size`.

**File**: `docker-compose.yml`

Pass as environment variables to the worker:
```yaml
- OCR_BATCH_SIZE=${OCR_BATCH_SIZE:-10}
- OCR_THREAD_WORKERS=${OCR_THREAD_WORKERS:-4}
```

Increase default batch size from 5 to 10 (fewer chord tasks, less scheduling overhead). With intra-batch threading, larger batches are now efficient.

Increase default worker concurrency from 4 to match CPU cores (use `--concurrency=8` or `--autoscale=10,4`).

### 3. Separate preprocessing into its own phase

**File**: `backend/app/tasks/ocr_tasks.py`

Add a new task `preprocess_pages_for_book` that runs before OCR. It preprocesses all pages that have a `preprocessing_config` but no `processed_image_path`. This removes CPU-intensive OpenCV operations (deskew, denoise) from the OCR critical path.

```python
@celery_app.task(name="preprocess_pages_for_book")
def preprocess_pages_for_book(job_id_str, book_id_str):
    """Preprocess all pages that need it, then trigger OCR."""
    async def _run():
        async with async_session_factory() as db:
            # Find pages needing preprocessing
            pages = ...  # pages with preprocessing_config and no processed_image_path
            for page in pages:
                preprocessing.run_pipeline(image_path, config, output_path)
                page.processed_image_path = ...
            await db.commit()
    run_async(_run())
    # Chain OCR task
    run_ocr_for_book.delay(job_id_str, book_id_str, language)
```

**File**: `backend/app/api/books.py`

Change the OCR trigger to dispatch `preprocess_pages_for_book` instead of `run_ocr_for_book` directly. The preprocessing task chains into the OCR task.

**Alternative simpler approach**: Keep preprocessing inside `_process_page` but move it to a `ThreadPoolExecutor` or `ProcessPoolExecutor` so it doesn't block the Tesseract call. Since preprocessing is also CPU-bound, use `ProcessPoolExecutor` for preprocessing and `ThreadPoolExecutor` for Tesseract (subprocess-based).

**Recommended approach**: The simplest high-impact change is to run preprocessing **before** the chord — as a single batch task that preprocesses all pages, then triggers the OCR chord. This is cleaner and avoids mixing concerns.

### 4. Optimize Tesseract settings

**File**: `backend/app/services/ocr_service.py`

Change `--oem 3` to `--oem 1` (LSTM neural net only). The default `--oem 3` tries legacy engine first then falls back to LSTM. `--oem 1` skips the legacy attempt, which is faster for languages with LSTM models (Telugu, Hindi, English all have LSTM models in Tesseract 4+).

```python
config="--psm 6 --oem 1",  # was --oem 3
```

Add DPI-aware Tesseract configuration: if the image was rendered at a known DPI, pass `--dpi N` to Tesseract for better accuracy/speed tradeoff.

### 5. Add per-page progress tracking

**File**: `backend/app/tasks/ocr_tasks.py`

Add a progress callback to `run_ocr_for_page_batch` that updates the Job record after each page completes. The existing `ocr-status` endpoint already supports per-page status (it queries `OcrResult` records), so progress tracking is mainly for the job progress bar.

```python
def _update_progress(job_id_str, completed_pages, total_pages):
    async def _do():
        async with async_session_factory() as db:
            job = ...  # load job
            job.progress = round((completed_pages / total_pages) * 100, 1)
            await db.commit()
    run_async(_do())
```

Call this after each page completes in the threaded batch, using a thread-safe counter (`threading.Lock` + counter variable).

### 6. Make render DPI configurable

**File**: `backend/app/core/config.py`

Add `ocr_render_dpi: int = 300`. Allow tuning down to 200-250 for speed at acceptable accuracy loss.

**File**: `backend/app/services/pdf_service.py`

Use the config value instead of hardcoded `dpi=300`.

**File**: `backend/app/api/books.py`

Use `settings.ocr_render_dpi` in `select_pages()`.

### 7. Separate OCR and LLM worker queues

**File**: `docker-compose.yml`

Add a second worker container dedicated to LLM tasks, so OCR workers aren't blocked by LLM tasks competing for the same processes:

```yaml
worker-ocr:
  command: celery ... worker --concurrency=8 -Q ocr,default
  
worker-llm:
  command: celery ... worker --concurrency=2 -Q llm
```

This prevents LLM tasks (which are I/O-bound waiting on Ollama) from consuming OCR worker processes.

## Files to modify

| File | Change |
|------|--------|
| `backend/app/core/config.py` | Add `ocr_batch_size`, `ocr_thread_workers`, `ocr_render_dpi` settings |
| `backend/app/tasks/ocr_tasks.py` | ThreadPoolExecutor in batch task, configurable batch size, progress tracking, separate preprocessing task |
| `backend/app/services/ocr_service.py` | Change `--oem 3` to `--oem 1`, add optional `--dpi` parameter |
| `backend/app/services/pdf_service.py` | Use configurable DPI |
| `backend/app/api/books.py` | Use configurable DPI, dispatch preprocessing task before OCR |
| `docker-compose.yml` | Split worker into OCR + LLM workers, increase concurrency, add env vars |
| `docker/Dockerfile.worker` | Update default concurrency |

## Expected speedup

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| 20-page book, 4 cores | ~5 batch rounds × sequential = ~20s | ~2 batch rounds × 4 threads = ~5s | ~4× |
| 50-page book, 8 cores | ~10 rounds × sequential = ~50s | ~3 rounds × 4 threads = ~8s | ~6× |
| Preprocessing + OCR | Mixed in same task | Preprocessing phase finishes first, OCR runs unblocked | ~1.5× for pages with preprocessing |

## Validation

1. Run existing unit tests: `cd backend && python -m pytest tests/unit/test_ocr_service.py tests/unit/test_preprocessing.py`
2. Run integration tests: `python -m pytest tests/integration/`
3. Manual test with `scripts/test_ocr_pipeline.py` on a sample image to verify Tesseract `--oem 1` produces equivalent quality
4. Run `scripts/test_ocr_accuracy.py` to compare accuracy before/after OEM change
5. Verify progress tracking updates via `GET /api/books/{id}/ocr-status` during an active OCR job

## Risks

- **Tesseract `--oem 1` accuracy**: LSTM-only mode may produce slightly different results for some scripts. Mitigated by running accuracy tests before/after.
- **Thread safety of `_process_page`**: Each thread creates its own DB session via `async_session_factory` inside `run_async`. Since `run_async` uses a per-process event loop and threads share the process, we need to ensure each thread gets its own event loop or use `asyncio.run()` per thread instead of the shared loop. **This is the main risk** — the `run_async` utility uses a persistent loop per process, which is not thread-safe. Each thread must use its own loop.
- **Memory**: Running 4 Tesseract subprocesses per worker process × 8 workers = 32 concurrent Tesseract processes. Each loads language models (~100MB). Monitor memory usage.

## Thread-safe async strategy

The `run_async` utility in `async_utils.py` maintains a single persistent event loop per worker process. This is **not thread-safe** — multiple threads calling `loop.run_until_complete()` simultaneously will corrupt the loop state.

**Solution**: For the threaded batch task, create a new event loop per thread:

```python
import asyncio

def _process_page_threadsafe(page_id_str, book_id_str, language):
    """Thread-safe version: creates its own event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_process_page_async(page_id_str, book_id_str, language))
    finally:
        loop.close()
```

Refactor `_process_page` into an async function `_process_page_async` and provide both `run_async`-based (for single-page task) and `asyncio.new_event_loop`-based (for threaded batch) wrappers.
