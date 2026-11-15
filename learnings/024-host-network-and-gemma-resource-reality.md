# 024 — Host network recovery and gemma4 resource reality

- **Date:** 2026-11-15
- **Study context:** Re-checking the public-release ingress/egress blockers before
  switching production to `gemma4:e4b` and shipping the Telugu line-OCR artifact.
- **Summary:** The oki host's **egress is fixed** (PyPI ~32 MB/s, Hugging Face
  ~1.1–2.3 MB/s, Docker pulls work), so the registry/artifact workaround is not
  needed. The **ingress bypass is still open**. `gemma4:e4b` is **6.6 GB / 7.5B**
  (not the 1.8 GiB assumed in plans/012) and loads at **6.71 GiB**, so its memory
  cap was raised to **9 GB** after the extraction measured a 7.9 GiB peak. The
  Telugu OCR model is **310 MB**, not 1.7 GB.

## Key findings (measured on 2026-11-15)

### 1. Egress — fixed

Measured from `oki` with 3 MB range requests:

| Endpoint | Result |
|---|---|
| PyPI / files.pythonhosted.org (Fastly) | **32.1 MB/s**, HTTP 206 |
| speed.cloudflare.com | **20.3 MB/s** |
| huggingface.co (model weight) | **1.1–2.3 MB/s**, HTTP 206 |
| `docker pull alpine:3.20` | completed, digest verified |
| `download.pytorch.org/whl/cpu` | HTTP 200 |
| registry-1.docker.io / ghcr.io / registry.cn-hangzhou.aliyuncs.com | HTTP 401 (normal auth challenge) |
| registry.ollama.ai manifests (`gemma4:e4b`, `gemma3n:e4b`) | HTTP 200 |

The old ~40–60 KB/s figure in plans/017 / known-issues is stale. A container
registry is no longer required to ship artifacts; a direct pull works. Aliyun's
ISO mirror range request timed out after a 302, but that path is not needed.

### 2. Ingress — still open

- `curl --resolve indic-book-metadata-extractor.agamya.us.kg:443:<origin-ip>`
  → **HTTP 200** on `/` and `/api/health` (real Host header, no Cloudflare).
- Public DNS path also 200 and carries `cf-ray`, so Cloudflare is in front, but
  the origin is reachable around it.
- `<origin-ip>:3000` (Dokploy) and `:8080/api/overview` (Traefik API) both
  return 200; the raw IP with no Host returns 404 only because Traefik has no
  catch-all router.
- Closing ingress to Cloudflare ranges (or a Cloudflare Tunnel) remains an
  operator action.

### 3. gemma4:e4b is much larger than planned

- Pulled `gemma4:e4b`: **6.6 GB** on disk, **7.5B parameters**, Q4_K_M,
  131k context, capabilities include `thinking` with default `true`.
- Native `/api/chat` with `think:false` returns valid JSON (verified:
  `{"ok": true}` in 29 s including a 27 s cold load).
- Loaded residency on the host: **6.71 GiB idle**, and **7.907 GiB peak during
  a real 8-batch extraction** — too close to the old cap. Ollama's cap was
  raised first to 8 GB, then to **9 GB** after the end-to-end run.
- Host has 15.6 GiB total with no swap; production + staging cannot both load
  gemma4 simultaneously on this box. By decision, **only production runs on
  oki; staging runs on a separate server.**

### 4. Telugu OCR artifact is smaller than documented

- `harsha-desaraju/telugu-ocr-model` weight file: **310 MB** (`model.safetensors`),
  plus small custom-code/tokenizer files. The 1.7 GB figure included an image
  guess, not the model.
- `torch` resolves to **2.15.0+cpu** through the explicit PyTorch CPU index;
  `transformers` 4.46.3. A worker-only image build can bake the extra + weights.

## Recommendation

- Do **not** build a registry bypass for egress; it is no longer a blocker.
- Remove the Debian/PyPI mirror workaround from `docker/Dockerfile.backend`;
  the host now reaches `deb.debian.org` (43 MB/s HTTPS, 6.7 MB/s HTTP) and PyPI
  (47 MB/s) directly. Reverted 2026-11-15.
- Keep the worker-only OCR build (`OCR_LINE=true`) so backend/flower stay small.
- Raise the Ollama cap to 9 GB and keep `phi4-mini` as the rollback model.
- Treat ingress as the only remaining launch-blocking network action.

## Next steps

1. Deploy the gemma switch (`OLLAMA_PRELOAD_MODEL=gemma4:e4b`,
   `LLM_NATIVE_ENDPOINT=true`, default model `gemma4:e4b`).
2. Bake the OCR extra + 310 MB weights into the worker; verify
   `OCR_TEL_ENGINE=line_model` end to end on one Telugu book.
3. Close origin ingress / add the Cloudflare edge rules (operator).
4. Update `docs/known-issues.md`, plans/012 and plans/017 with these numbers.

## References

- `plans/011-launch-readiness.md`, `plans/012-llm-service-native-endpoint.md`,
  `plans/017-telugu-ocr-engine-integration.md`
- `docker-compose.production.yml`, `docker/Dockerfile.backend`
- `backend/app/services/llm_service.py`, `backend/app/services/ocr_line_model.py`
