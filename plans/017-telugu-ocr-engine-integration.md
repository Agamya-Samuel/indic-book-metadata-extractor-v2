# 017 — Telugu OCR Engine Integration (planned)

Status: **implemented and baked into the worker image (2026-11-15)** — production
defaults to `line_model`; verify CER on one Telugu book after the deploy.
Owner: next OCR sprint.

## Implementation (2026-11-15)

- `Settings.ocr_tel_engine` (`OCR_TEL_ENGINE`, default `tesseract`), plus
  `ocr_line_model_name`, `ocr_line_model_decode`, and a conservative
  `ocr_line_model_confidence` for the unscored line output.
- New `backend/app/services/ocr_line_model.py`: lazy `AutoModel`/`AutoTokenizer`
  load (`trust_remote_code=True`, process-wide lock), Tesseract `--psm 6` line
  boxes, batched `model.transcribe`, and the same return contract as `run_ocr`
  (`engine: "line_model"`, one line-level `word` entry per box).
- `ocr_service.run_ocr` dispatches **Telugu only** when the flag is
  `line_model`; Hindi/English never touch the model. Any load/inference error
  falls through to Tesseract for that page and records
  `engine_fallback_reason`.
- `ocr_tasks` skips `retry_low_confidence_words` for non-Tesseract output (it
  would overwrite the model) and records a fallback in `pages.ocr_error`.
- Tests use a fake model; the real weights/torch path is **not** exercised here
  (no `torch`, no HF cache in this environment). Default config reproduces
  today's behaviour exactly.
- **Packaging (done):** the worker image builds with `OCR_LINE=true`, installing
  CPU `torch` (2.15.0+cpu) + `transformers` 4.46.3 via the `ocr-line` extra and
  baking the **310 MB** weights into `/app/ocr_models/telugu-ocr-model`
  (`HF_HUB_OFFLINE=1` at runtime). Production compose defaults
  `OCR_TEL_ENGINE=line_model`. The old 1.7 GB/40–60 KB/s blocker is obsolete: the
  measured egress is PyPI ~32 MB/s, HF ~1.1 MB/s ([learnings/024](../learnings/024-host-network-and-gemma-resource-reality.md)).

## Why

Tesseract on Telugu is the pipeline's dominant error. On the verified scans the
median character error rate is ~0.40 ([learnings/020](../learnings/020-ocr-engine-benchmark.md)).
A Telugu-specific line model, `harsha-desaraju/telugu-ocr-model`, more than
halves it (median CER ~0.16) and is the chosen engine. It is not wired into
`backend/app/services/ocr_service.py` yet, so every Telugu book still pays the
Tesseract error rate.

## Measured basis

- Benchmark: [learnings/020](../learnings/020-ocr-engine-benchmark.md),
  [learnings/021](../learnings/021-ocr-engine-operational-requirements.md).
- Harness: `backend/scripts/ocr_bench/bench_lines.py` (line detection →
  per-line model → CER/WER against the bundle references).
- Hindi stays on Tesseract (median CER ~0.07); IndicOCR is gated and not
  CPU-viable.

## Blocker

The model needs `torch` + `transformers` (multi-GB) and its weights fetched
from Hugging Face. The production host's egress to Fastly/PyPI is ~40–60 KB/s
([deploy-host-egress]), so neither an image build nor a first-boot download is
practical. A GCP Mumbai node fetches the same endpoints at ~12 MB/s and is the
right place to build and benchmark, but the artifact still has to be baked into
the production image or mounted as a volume.

## Integration design

1. **Engine registry in `ocr_service.py`.** Keep Tesseract as the default
   engine; add `TELUGU_OCR_ENGINE=tesseract|hf-line`. `tel+eng` pages use the
   selected engine; Hindi/English never do.
2. **Line detection.** Reuse the OpenCV/Tesseract box grouping from
   `bench_lines.py`; crop each line, run the model, and store per-line boxes so
   `bounding_boxes`/the review canvas keep working.
3. **Fallback.** Any model load/inference error for a page falls back to
   Tesseract for that page and records the reason in `pages.ocr_error`; a
   missing model must not fail the book.
4. **Confidence.** The model does not emit Tesseract confidences; map a
   conservative per-page confidence (or null) and keep the UI's low-confidence
   hint honest.
5. **Packaging.** Bake the weights (with checksum and licence) into a dedicated
   image/tag or mount a read-only volume; add a startup check that reports the
   engine and model path. Do not download at runtime.
6. **Performance.** Line models are per-line calls; batch lines per page and
   keep the single-book lock. Measure page time against Tesseract on the same
   node.

## Success criteria

- Telugu median CER ≤ 0.20 on the current 71-book ground-truth corpus.
- Hindi/English CER unchanged (engine untouched).
- A missing/broken model degrades to Tesseract without failing the book.
- Median Telugu page time recorded; no more than ~3× the Tesseract page time on
  the same 4-vCPU node.
- OCR review still shows line boxes and saved corrections still win over raw
  text.

## Next steps

1. Build the model image on a free GCP node; record download size, load time,
   and per-page time in the infra tracker.
2. Run `bench_lines.py` on the Telugu GT split; compare with the existing
   benchmark numbers.
3. Implement the registry + fallback behind `TELUGU_OCR_ENGINE`.
4. Deploy with the volume/image artifact, run one Telugu book end to end on
   production, and update `docs/known-issues.md` with the new measurement.