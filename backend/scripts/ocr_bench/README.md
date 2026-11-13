# OCR engine benchmark harness

Reproducible harness behind [learnings/020](../../../learnings/020-ocr-engine-benchmark.md): compares OCR engines on real Indic scans (page-level CER/WER + wall-time + peak RAM), CPU only.

## Files

| File | Role |
|---|---|
| `build_bundle.py` | Render evenly-sampled verified Telugu pages from `backend/tests/fixtures/ground_truth/tel/*` (PDF + `wikisource_gt.json`) to `/tmp/ocr_bundle` + `manifest.jsonl` |
| `fetch_indicvision_hindi.py` | Pull Hindi rows (page image + verified text) from the IndicVisionBench `ocr` config via the HF datasets-server, into `/tmp/hin_bundle` |
| `bench.py` | Run a page engine (Tesseract / PaddleOCR) over a bundle → CER/WER + s/page + peak RSS |
| `bench_lines.py` | Run the Telugu line model (page → Tesseract line boxes → per-line transcribe) |
| `setup_v2.sh` | venv for PaddleOCR 2.x (CPU) |
| `setup_v3.sh` | venv for the Telugu line model (torch CPU) |
| `node_setup.sh` | Paddle 3.x / PaddleX attempt (kept for the segfault workaround record) |
| `results.json` | Measured summaries + per-page CER/WER |

## Datasets (both CC/verified)
- **Telugu:** our own Wikisource-verified scans (level 3–4) already in the repo GT corpus.
- **Hindi:** IndicVisionBench `ocr` config (real printed pages + verified text), because our Hindi books have no verified page text. Fetch is API-only (no 600 MB parquet).

## Environment (verified on Ubuntu 22.04 / Python 3.10, CPU)
- PaddleOCR 2.x: `paddlepaddle==2.6.2 paddleocr==2.7.3 numpy==1.26.4 opencv-python-headless==4.10.0.84` (numpy 2 / OpenCV 5 break Paddle 2.x; Paddle 3.x segfaults on this CPU — see below).
- Telugu model: `torch` (CPU wheel) `transformers==4.46.3 pillow regex python-Levenshtein pytesseract`; model `harsha-desaraju/telugu-ocr-model` (`trust_remote_code=True`). `transformers` 5.x is incompatible with the model's custom code (`all_tied_weights_keys`).

## Run
```bash
# Telugu bundle (on a machine that has the repo GT + PyMuPDF), then copy to the node
backend/.venv/bin/python backend/scripts/ocr_bench/build_bundle.py 8 3
gcloud compute scp --recurse /tmp/ocr_bundle test-node-3:/tmp/ocr_bundle

# Hindi bundle (network only)
python3 backend/scripts/ocr_bench/fetch_indicvision_hindi.py

# Engines
<venv>/bin/python bench.py --engine tesseract --lang tel --bundle /tmp/ocr_bundle
<venv>/bin/python bench.py --engine paddle    --lang te  --bundle /tmp/ocr_bundle
<venv3>/bin/python bench_lines.py --decode ctc   # Telugu line model
```

## Known restrictions / blockers
- **PaddlePaddle 3.x segfaults** on this CPU (`ConvertPirAttribute2RuntimeAttribute`, PIR/oneDNN) → use 2.6.2.
- **transformers 5.x** incompatible with the Telugu model's custom code → pin 4.46.x.
- **Python 3.14** has no Paddle/Torch wheels → run on Python 3.10/3.11 (node used 3.10).
- **`/tmp` is wiped on node stop/start** → put venvs in `/home` if you need them to persist; downloaded model weights in `/home/agamya/.paddlex` and the HF cache persist.
- **HF gated model:** `bodhan-ai/indic-ocr` (IndicOCR) requires accepting its license / requesting access before weights download.
- IndicVisionBench datasets-server occasionally returns transient HTTP 502; retry.