# 015 — Service Inventory, Memory Profile and Non-Essential Gating (oki)

- **Date:** 2026-11-11
- **Study context:** Original objective — the host is resource-constrained and OCR + LLM extraction are CPU/RAM heavy. Identify every service, classify essential vs non-essential for the core OCR pipeline, evaluate a flag-based gating approach, and recommend how to reduce consumption without losing the optional functionality.
- **Status:** Profile and gating mechanism **measured and verified**. Gating **not yet implemented**. Raw data: [`backend/reports/pipeline-profile-oki.json`](../backend/reports/pipeline-profile-oki.json).

## Summary

On the production host (4 vCPU / 15.62 GiB / **no swap**), the non-essential services idle at **2522 MiB — 16% of RAM** — and can be gated behind `COMPOSE_PROFILES` with **no restructuring**, because nothing in the core pipeline depends on them. A core-only stack runs at **1422 MiB**. Under real load the pipeline peaks at **7713 MiB anon with the model resident (min available 3070 MiB)**, so RAM is not the binding constraint: **extraction wall-clock is** (81% of per-book time vs OCR's 19%).

## Key findings

### 1. Service inventory (15 services, 3 groups)

| Group | Services |
|---|---|
| **Core** | `postgres`, `redis`, `ollama`, `backend`, `worker`, `frontend` |
| **Core-adjacent (keep on)** | `backup` — daily `pg_dump`, 7-day retention; idle sleep loop, ~12 MiB, and the **only** automated backup of `pgdata` |
| **Non-essential** | `wikibase`, `wikibase-jobrunner`, `wikibase-init`, `quickstatements`, `mysql`, `elasticsearch`, `openrefine`, `flower` |

`redis` is essential, not optional: it is the Celery broker, result backend, SSE pub/sub transport and rate limiter. Tesseract is **not a service** — it is apt-installed in the backend/worker image and spawned as a subprocess per page, so there is no OCR service to start or stop.

### 2. Measured idle memory (MiB)

| | Total | Breakdown |
|---|---|---|
| Non-essential | **2522** | openrefine 1084 · elasticsearch 900 · wikibase 170 · mysql 139 · wikibase-jobrunner 131 · flower 54 · quickstatements 43 |
| Core | 1184 | worker 648 · backend 161 · ollama 155 · frontend 129 · postgres 64 · redis 14 · backup 12 |
| Dokploy platform | 706 | dokploy 506 · traefik 119 · dokploy-postgres 64 · dokploy-redis 17 |

`openrefine` and `elasticsearch` alone are 1984 MiB — 79% of the non-essential total. Ollama idles at 155 MiB because the model is **unloaded**; an idle snapshot understates peak badly (see §5).

### 3. Gating analysis — the mechanism

- **Compose has no conditional service inclusion via a boolean.** There is no `if: ${ENABLE_X}`. The native mechanisms are `profiles:` (already used here for `monitoring`) or overlay files. The proposed `ENABLE_OPENREFINE`/`ENABLE_WIKIBASE` booleans would need a wrapper translating them into `--profile`/`-f`, and that convention would have to hold on every deploy path.
- **`COMPOSE_PROFILES` works, verified end to end.** Tested directly: with `COMPOSE_PROFILES=wikibase` in the project `.env`, both core and optional services are included; with it empty, only core. No wrapper needed. Dokploy writes its Environment tab into that same `.env` (it already injects `COMPOSE_PROJECT_NAME` and `DOCKER_CONFIG` there), so the setting reaches the Compose process.
- **Gating is structurally safe.** Starting only the core services by name works with **no compose edit**, because nothing core depends on an optional service. `depends_on` only ever points inward.
- **Runtime flags cannot drive the UI.** `frontend/src/app/bulk-operations/page.tsx` is `"use client"`, so `NEXT_PUBLIC_OPENREFINE_URL` / `NEXT_PUBLIC_WIKIBASE_URL` are **inlined at build time**. A runtime flag will not hide the links; that needs a rebuild or a backend-served capabilities endpoint. Production currently bakes a live `NEXT_PUBLIC_OPENREFINE_URL`.
- **Disabling is not deleting.** Volumes (`mysql_data_v3`, `elasticsearch_data`, `wikibase_config_v3`, `openrefine_data`) persist, and `wikibase-init` re-creates properties on next start, so services come back empty rather than broken. `down -v` must never be used.
- **Per-environment volume names differ** (`mysql_data` dev vs `mysql_data_v3` prod), so volume work must enumerate first and confirm per item.

### 4. There is almost no code coupling to the optional services

- `backend/app/services/openrefine_service.py` is **dead code** — never imported anywhere.
- The Wikibase export (`/api/bulk/export-wikibase`) generates the QuickStatements TSV **locally** and never contacts Wikibase.
- `/health` checks only postgres, redis and ollama.
- The property-mapping wiring is **already broken**: `docker/wikibase/create-properties.sh` writes `/config/property-mapping.json` into the `wikibase_config` volume, while the backend reads `/app/storage/property-mapping.json` from `storage_data` — different volumes, so `_load_property_mapping()` always falls back to hardcoded Wikidata P-IDs.

Consequence: disabling the optional services breaks no pipeline path. The user loses the OpenRefine link-out and the hosted QuickStatements target.

### 5. Host-level limits at measurement time, and what changed since

- At measurement: **no `mem_limit`, `cpus` or `deploy.resources` anywhere**; `SwapTotal: 0`; `Committed_AS` 16.6 GB against 16.4 GB physical — already overcommitted with no safety valve. At the extraction peak only 3070 MiB remained available.
- Still true now: `frontend` and `backup` have **no** memory limit.
- **Since then (2026-11-11), parallel work added** `mem_limit: "6g"` plus `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_NUM_THREADS=3`, `OLLAMA_CONTEXT_LENGTH=4096`, and moved the preloaded model to `phi4-mini`. So the LLM resource arm is largely addressed; the gating item is **not**.

### 6. A measurement artifact worth recording

Two runs showed host "used" spiking to 11733–12440 MiB while containers summed to only 1.6–1.8 GB. Re-measured with 1-second `/proc/meminfo` **category** sampling across the same phases (1720 samples): `anon` never exceeded **7713 MiB**, and no sample had `anon>9 GB`, `cached>9 GB` or `shmem>1 GB`. The spike was an artifact of the coarse instrument — aggregate `free -m` "used" read via subprocess at 2–4 s intervals cannot separate AnonPages / Cached / Shmem / Slab. **Aggregate `used` is not sufficient instrumentation for this question.**

### 7. Phase split — where the time actually goes

One 30-page Telugu book, sequential pages: **OCR 568.4 s (18.9%)** vs **extraction ~2434 s (81.1%)**. Per-page OCR ranges **3 s to 86 s**, and the slowest 4 pages consume **54%** of OCR wall-clock. Worker peak CPU was 335%, i.e. Tesseract's OpenMP already uses ~3.35 of 4 cores for a single page — so page-parallelism is not the free win it first appears.

## Recommendation

1. **Implement gating via `COMPOSE_PROFILES`** (`wikibase`, `openrefine`, `monitoring`), default empty → core-only. Saves **~2.5 GiB per environment** with no restructuring. Set the variable in Dokploy's Environment tab, and make the frontend links consistent with it (rebuild, or serve capabilities from the backend).
2. **Keep `backup` ungated.** Cutting it saves ~12 MiB and removes the only automated database backup — a bad trade. `backup_data` protects core data and must survive any non-essential volume deletion.
3. **Add memory limits to `frontend` and `backup`** (or all services) so no single service can balloon, and consider swap: with `Committed_AS` above physical RAM and zero swap, an OOM is abrupt.
4. **Do not gate OCR or LLM against each other.** They already alternate by construction — OCR completes all pages, then extraction runs — so they never contend. Unloading the model during OCR would cost ~30–60 s reload per book for no benefit at this host size.

## Next steps

1. Implement the profiles + Dokploy env; verify a core-only deploy and that enabling a profile restores the service.
2. Enumerate and delete the non-essential volumes on a confirmed list (volumes only, definitions stay gated).
3. Add limits for `frontend`/`backup`; decide on swap.
4. Re-measure idle after gating to confirm the ~2.5 GiB reclaim.
5. Owner: dev, with the user owning the host-size decision (this analysis holds at 16 GB; a smaller target would change the model-residency answer).

## References

- Raw profile: [`backend/reports/pipeline-profile-oki.json`](../backend/reports/pipeline-profile-oki.json)
- Related: [011](011-deployment-exposure-and-single-origin.md) (exposure/domains) · [013](013-verified-shortlist-and-ocr.md) (Ollama 6 GiB cap) · [016](016-pipeline-non-functional-at-head.md) (the defects found while measuring)
- Compose: [`docker-compose.production.yml`](../docker-compose.production.yml) · [`docker/ollama-entrypoint.sh`](../docker/ollama-entrypoint.sh)
- Host access: `reference/dokploy` (gitignored)
