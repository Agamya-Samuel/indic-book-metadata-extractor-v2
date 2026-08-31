# Post-Deploy Runbook — OCR Accuracy Improvements

Steps to take **after** the OCR accuracy plan is committed and deployed. Covers
operational tasks, calibration, and the optional Tier 3 fine-tuning track.

## 1. Must do (operational, not code)

### 1.1 Run the Alembic migration

Migration `008_ocr_postprocess_columns.py` adds the `cleaned_text` and
`corrections` columns to `ocr_results`. If you forget this, OCR tasks will
crash on the new code path because the column doesn't exist yet.

```bash
alembic upgrade head
```

### 1.2 Rebuild the backend Docker image

The new `Dockerfile.backend` clones the `indic-ocr/tessdata` repository at
build time. Without a rebuild, Tesseract will still use the old stock
`tesseract-ocr-tel/hin` packs and you'll see no Tier 2 improvement.

```bash
make rebuild
```

### 1.3 Enable Tier 1 defaults gradually

`OCR_AUTO_PREPROCESS=true` is on by default, which means every new book gets
Sauvola binarization + denoise + 300 DPI upscale + border strip.

- Watch the first 5–10 books processed post-deploy.
- Compare `avg_confidence` in the Library page against the pre-deploy baseline.
- If a particular book type regresses, that single user can set
  `preprocessing_config: {"auto_preprocess": false}` per page to fall back
  to the old pipeline.

---

## 2. Should do (no code, but needed for the gains to materialize)

### 2.1 Populate dictionary wordlists

The placeholder dictionary files are just comments — Tesseract treats an empty
`user-words.txt` as a no-op constraint. To actually see Tier 4 benefits, the
operator must populate real wordlists.

```bash
# In the worker container, populate from AI4Bharat or Wikipedia frequency lists
python -c "import urllib.request; urllib.request.urlretrieve(
    'https://.../hin_50k.txt',
    'app/services/dictionaries/hin.words'
)"
```

Then enable in `.env`:

```env
OCR_USE_DICTIONARY=hin,tel
```

See `docs/ocr-training.md` for the full operator playbook.

### 2.2 Pin TESSDATA_REF for reproducibility

The build clones `indic-ocr/tessdata` at `master` by default. Pin to a commit
SHA in `docker/Dockerfile.backend` for reproducible builds:

```dockerfile
ARG TESSDATA_REF=<commit-sha>
```

Or, alternatively, set `OCR_TESSDATA_DIR` on the host to point at a managed
tessdata location, so the swap doesn't require an image rebuild.

---

## 3. Tier 3 — LSTM fine-tuning (entirely manual, off the hot path)

This is **not** part of the deploy. Run only when:

- A specific language shows measurably worse confidence than the others in
  the Library page, **AND**
- You've accumulated 500+ user-corrected lines in the OCR Review UI for that
  language.

Full steps are in `docs/ocr-training.md`. Summary:

### 3.1 Export corrections

The export endpoint does not exist yet. Without it, operators have to
hand-roll the export from the `OcrResult.corrections` JSONB column.

> **Gap**: `GET /api/admin/ocr-corrections?language=hin` needs to be added
> before this workflow is usable end-to-end.

### 3.2 Build the corpus

```bash
cat /app/storage/training_data/hin/corrections.tsv \
    /app/storage/training_data/hin/wikipedia.tsv \
  | awk -F'\t' '!seen[$4]++' \
  > /app/storage/training_data/hin/corpus.txt
```

Split 90/10 into train/test.

### 3.3 Render synthetic pages

```bash
uv run python scripts/generate_training_data.py \
    --corpus /app/storage/training_data/hin/training_text.txt \
    --output-dir /app/storage/training_data/hin \
    --fonts "Noto Sans Devanagari" "Mangal" "Lohit Devanagari"
```

### 3.4 Train

```bash
docker build -f docker/Dockerfile.trainer -t indic-trainer .
docker run --rm -v /app/storage:/app/storage indic-trainer \
  bash scripts/train_tesseract_lstm.sh \
    --lang hin \
    --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
    --output-dir /app/storage/models/hin_v2 \
    --training-dir /app/storage/training_data/hin \
    --fonts "Noto Sans Devanagari" "Mangal" \
    --epochs 200
```

### 3.5 Eval-gate

```bash
docker run --rm -v /app/storage:/app/storage indic-trainer \
  uv run python scripts/eval_model.py \
    --model /app/storage/models/hin_v2/hin.traineddata \
    --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
    --test-list /app/storage/training_data/hin/test.tsv \
    --lang hin \
    --max-cer-degradation 2.0
```

Exits non-zero if the new model is more than 2 CER points worse than base.
**Do not deploy a model that fails this check.**

### 3.6 Promote

Symlink the new model into the worker container's mount point and set:

```bash
OCR_CUSTOM_MODEL_DIR=/app/storage/models/hin_v2
```

Then update `OCR_MODEL_OVERRIDE` (or extend `LANGUAGE_MAP`) so the service
picks the new file. Roll out by enabling for one book first; once confidence
deltas look healthy in Flower logs, expand to all books.

---

## 4. Tier 5 calibration

The post-process rules (anusvara collapse, danda cleanup, ZWJ stripping,
low-conf retry) have conservative defaults. After the first 20–30 books,
check the following.

### 4.1 Check `OcrResult.corrections` in the DB

If `danda_normalize` is firing on English text, the rule is too eager and
should be scoped to Indic scripts only. Currently it runs for every
language, which is wrong for `eng` books.

### 4.2 Tune the low-conf threshold

`OCR_LOW_CONF_THRESHOLD=40` is the default. Adjust based on observed
behavior:

- If worker logs show too many `--psm 8` retries without quality
  improvement, bump to **50**.
- If the OCR Review UI shows lots of low-conf words, drop to **30**.

---

## 5. Order of operations (concrete)

```bash
# 1. Apply DB migration                              # ~10 seconds
alembic upgrade head

# 2. Rebuild image (first build downloads tessdata)  # ~10 min first time
make rebuild

# 3. Start all services                              # ~60 seconds
make up

# 4. Smoke test — one Telugu + one Hindi book
#    (upload through the UI)

# 5. Inspect OCR Review page
#    Confirm: processed_image_path populated          # Tier 1 ran
#    Confirm: cleaned_text differs from raw_text      # Tier 5 ran

# 6. Compare avg_confidence vs pre-deploy baseline
#    Expect: +5 to +15 point improvement

# 7. Enable OCR_USE_DICTIONARY
#    (after populating real wordlists, see 2.1)

# 8. Wait for 500+ corrections per language to accumulate

# 9. Train Tier 3 model                              # only if needed
#    (full steps in docs/ocr-training.md)
```

---

## 6. Summary

| Step | When | Effort |
|------|------|--------|
| `alembic upgrade head` | Immediately after deploy | Seconds |
| `make rebuild` | Immediately after deploy | ~10 min first time |
| Smoke test 1–2 books | Same day | Minutes |
| Watch confidence deltas | First week | Passive |
| Populate wordlists + enable `OCR_USE_DICTIONARY` | When wordlists are ready | Hours |
| Tier 3 fine-tuning | Only if a language regresses | Days |

The immediate post-deploy work is steps 1–6. Medium-term work is populating
real wordlists. Tier 3 fine-tuning is conditional, not a deploy blocker.

---

## Related documents

- `docs/ocr-training.md` — full Tier 3 training operator playbook
- `home/agamya/.commandcode/plans/indic-ocr-accuracy-improvements.md` —
  the plan this runbook implements
