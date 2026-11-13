# 021 — OCR Engine Operational Requirements & Future Research (Hindi + Telugu)

- **Date:** 2026-11-13
- **Context:** Companion to [learnings/020](020-ocr-engine-benchmark.md). The engine decision is settled (see below); this records the **environment, version, and access requirements** each engine imposes, plus **deferred research**, so the next engineer does not rediscover them.

## Locked decision (evidence in 020)

| Language | Engine | Why |
|---|---|---|
| **Hindi** | **Tesseract 5 (`hin`)** | median CER 0.072 on real printed Hindi, 2.3 s/page, 44 MB |
| **Telugu** | **`harsha-desaraju/telugu-ocr-model`** (+ Tesseract line boxes) | median CER 0.163 vs Tesseract 0.402 — 2.5× better, 3.8 s/page, 0.78 GB |

Rejected: **PaddleOCR** (no accuracy gain, 6–13× slower, 1.3 GB, CPU segfault); **IndicOCR** (gated and not CPU-viable, see below); Surya/EasyOCR (licence / poor Indic).

## Operational requirements matrix (all verified on the CPU benchmark node)

| Engine | Python | Key deps / pins | Device | Access | CPU footprint | Notes |
|---|---|---|---|---|---|---|
| **Tesseract 5** | any (CLI; `pytesseract`) | system `tesseract` + `tesseract-ocr-tel` / `-hin`; `tel` traineddata | CPU native | public | 44–167 MB | no Python-version constraint; fastest option |
| **PaddleOCR** | 3.10–3.11 | `paddlepaddle==2.6.2 paddleocr==2.7.3 numpy==1.26.4 opencv-python-headless==4.10.0.84` | CPU | public | ~1.3 GB | **PaddlePaddle 3.x segfaults** on CPU (`ConvertPirAttribute2RuntimeAttribute`, PIR/oneDNN) → pin 2.6.2; numpy 2 / OpenCV 5 break it |
| **telugu-ocr-model** | ≥3.9 | `torch` (CPU wheel) `transformers==4.46.x pillow regex python-Levenshtein pytesseract` | CPU works (no explicit device needed) | public (MIT) | ~0.78 GB | `trust_remote_code=True`; **transformers 5.x breaks its custom code** (`all_tied_weights_keys`); needs page→line segmentation first |
| **IndicOCR** (bodhan-ai) | **≥3.11** | `torch` `transformers>=5.7` (+ `torchvision`, `accelerate`, `huggingface_hub`) | **must pass `device="cpu"`** (loader defaults to `cuda`) | **HF-gated** (licence + token) | ~3.1 GB | 0.8 B hybrid-attention VLM → CPU-hostile: needs `flash-linear-attention`/`causal_conv1d` kernels or a GPU; **measured >12 min/page, 0 pages done on 4 vCPU → not viable** |

## Environment / infrastructure gotchas

- **Backend app already requires Python ≥3.11** ([backend/pyproject.toml](../backend/pyproject.toml) `requires-python`), so it satisfies IndicOCR's 3.11 floor and the Telugu model's 3.9 floor — the version mismatch was the **node image**, not the app.
- **GCP test nodes** are Ubuntu 22.04 → default `python3.10`. Provision 3.11 with `uv venv --python 3.11` when a package needs it.
- **`/tmp` is wiped on node stop/start** → venvs created under `/tmp` vanish; put them in `/home`. Downloaded weights persist under `/home/agamya/.cache/huggingface` and `/home/agamya/.paddlex`.
- **Python 3.14** (this workstation) has no Paddle/Torch wheels — run engine tests on 3.10/3.11.
- **Gated HF repos** need the licence accepted on the account *and* an HF token at download time; keep the token in a gitignored, mode-600 file (never in the repo), and rotate if ever exposed.
- **Offline production:** all engines need their weights vendored into the image or a mounted volume; HF/PaddlePaddle downloads must not be required at runtime.

## Future research / deferred (not blocking the locked decision)

1. **IndicOCR on a GPU** (or with `flash-linear-attention` + `causal_conv1d`): it is the only Hindi step-change candidate (published ~96 % word-acc). Re-measure only if a GPU is available — do not revisit on CPU.
2. **Telugu accuracy ceiling:** re-run the line model with `decode="joint"` (~9× slower, ~11 % lower AER) and replace Tesseract's line boxes with a purpose-built line detector.
3. **Validate on our own Hindi books:** needs human-transcribed front matter (≥2 books) — the recommended engine (Tesseract) is measured on IndicVisionBench, not our scans.
4. **Licence review before any wider adoption:** Surya weights (OpenRAIL-M, <$5 M revenue), Indic Open Model License "hosting-as-API" condition.
5. **Prod-scale throughput:** confirm the Telugu line pipeline's minutes/book inside the production image; consider ONNX export of the 81 M model for CPU speed and a process-safe lock under Celery.
6. **Reviewer-effort metric** (raises the value of the choice): `ocr_results.corrections` is never written and `GET /api/admin/ocr-corrections` is unimplemented — fix to measure raw→corrected edit rate per engine.

## References

- Decision + numbers: [learnings/020](020-ocr-engine-benchmark.md) · harness: [backend/scripts/ocr_bench/](../backend/scripts/ocr_bench/)
- Current OCR code: [backend/app/services/ocr_service.py](../backend/app/services/ocr_service.py)
- Models: https://huggingface.co/harsha-desaraju/telugu-ocr-model · https://huggingface.co/bodhan-ai/indic-ocr
- Node tracker: [infra/gcp-test-nodes.md](../infra/gcp-test-nodes.md)