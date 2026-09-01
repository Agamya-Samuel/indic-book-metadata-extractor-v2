# OCR Training & Fine-tuning

This document covers the **Tier 3** LSTM fine-tuning pipeline: how to harvest
user-corrected OCR data, generate synthetic training pages, train a new model,
and deploy it without breaking production.

## When to fine-tune

Fine-tune a model when:

- A specific language has noticeably worse `avg_confidence` than the others in
  the OCR Review step (look for it in the Library page).
- You've collected 500+ user-corrected lines for that language from the OCR
  Review UI.
- A new font / publisher's typeface dominates your new acquisitions.

Don't fine-tune if your goal is "general-purpose accuracy on Hindi books
already in the corpus" — first try the Tier 1 preprocessing, which captures
most of the win.

## 1. Harvest corrections

The OCR Review UI records every user edit. The exporter lives at
`GET /api/admin/ocr-corrections?language=hin` and returns a TSV of
`(image_path, bbox, wrong_text, right_text)` rows.

```bash
curl -u admin:password \
  'http://localhost:8000/api/admin/ocr-corrections?language=hin' \
  -o /app/storage/training_data/hin/corrections.tsv
```

## 2. Build the training corpus

Combine the harvested corrections with a general-domain corpus (Wikipedia dump
for that language works well). Deduplicate by `right_text` to avoid training on
thousands of identical lines.

```bash
cat /app/storage/training_data/hin/corrections.tsv \
    /app/storage/training_data/hin/wikipedia.tsv \
  | awk -F'\t' '!seen[$4]++' \
  > /app/storage/training_data/hin/corpus.txt
```

Split 90/10 into train/test:

```bash
shuf corpus.txt > corpus.shuffled
total=$(wc -l < corpus.shuffled)
split=$(echo "$total * 0.9 / 1" | bc)
head -n "$split" corpus.shuffled > training_text.txt
tail -n +$((split + 1)) corpus.shuffled > test.tsv
```

`training_text.txt` is the manifest expected by `tesstrain.sh` (an image path
followed by ground truth, tab-separated).

## 3. Render synthetic pages

```bash
uv run python scripts/generate_training_data.py \
    --corpus /app/storage/training_data/hin/training_text.txt \
    --output-dir /app/storage/training_data/hin \
    --fonts "Noto Sans Devanagari" "Mangal" "Lohit Devanagari"
```

This writes one PNG per line plus a manifest.

## 4. Train (fine-tune)

Build the trainer image once:

```bash
docker build -f docker/Dockerfile.trainer -t indic-trainer .
```

Then run the fine-tune:

```bash
docker run --rm \
  -v /app/storage:/app/storage \
  indic-trainer \
  bash scripts/train_tesseract_lstm.sh \
    --lang hin \
    --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
    --output-dir /app/storage/models/hin_v2 \
    --training-dir /app/storage/training_data/hin \
    --fonts "Noto Sans Devanagari" "Mangal" \
    --epochs 200
```

This produces `/app/storage/models/hin_v2/hin.traineddata`.

## 5. Evaluate against the base model

```bash
docker run --rm \
  -v /app/storage:/app/storage \
  indic-trainer \
  uv run python scripts/eval_model.py \
    --model /app/storage/models/hin_v2/hin.traineddata \
    --base-model /usr/share/tesseract-ocr/5/tessdata/hin.traineddata \
    --test-list /app/storage/training_data/hin/test.tsv \
    --lang hin \
    --max-cer-degradation 2.0
```

Exits non-zero if the new model is more than 2 CER points worse than the base.
**Never deploy a model that fails this check.**

## 6. Deploy

Symlink the new model into the worker container's mount point and set:

```bash
OCR_CUSTOM_MODEL_DIR=/app/storage/models/hin_v2
```

Then update `OCR_MODEL_OVERRIDE` (or extend `LANGUAGE_MAP`) so the service
picks the new file. Roll out by enabling for one book first; once confidence
deltas look healthy in Flower logs, expand to all books.

## Performance tuning

| Knob | Effect |
|------|--------|
| `--epochs 200 → 400` | More passes; diminishing returns above ~300 for fine-tunes. |
| `--fonts` (more fonts) | Wider coverage of glyph variations; doubles training time per added font. |
| `--maxpages 1000 → 5000` | More training images; CPU-time grows linearly. |
| `--continue_from <lstm>` | Resume from the latest checkpoint if training was killed. |

## Measuring impact

After deploying a model, compare `avg_confidence` distributions in the Library
page for books processed before vs. after. The expected delta is +5 to +15
points on the target language; if you don't see at least +3, the fine-tune
didn't generalize — likely too little data or too narrow a font set.

Log a row to `docs/ocr-training.md` under "Tuning history" with the measured
delta so the next operator knows what to expect.