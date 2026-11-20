# 036 — pgvector Semantic Search: Why It Was Provisioned, What It Would Cost, and Why It Was Removed

- **Date:** 2026-11-20
- **Study context:** `README.md`, `AGENTS.md`, `CHANGELOG.md` and `todos/015` §3 item 10 all said
  "pgvector semantic search is not yet implemented". This record answers the two questions that claim
  raises — *why* it was never built, and *what it would cost* if it were — and documents the decision
  to remove the dead schema rather than leave it reserved.
- **Status:** Decision **applied**. Code, schema, dependency and images changed; see §6.
- **Decision owner:** user (asked for the analysis and the removal).

## Summary

The `embeddings` table was never a half-finished feature. It was **provisioned as future
infrastructure in the initial schema and never given a study, an embedding model, or a single
caller**. Implementing it is affordable in CPU but tight in RAM: **+0.5–1.5 GB RSS and <0.1 % of
per-book CPU** for a MiniLM/e5-class 768-dim model, against a measured **3.0 GiB** of headroom on a
host that already peaks at 7713 MiB with `gemma4:e4b` resident. The schema was removed as dead code.

## Key findings

### 1. Why it was never implemented

| Question | Evidence |
|---|---|
| Was it ever a committed feature? | No. `docs/history/tech-stack-2026-06.md:144` lists pgvector as "for **future** semantic/similarity search"; `CHANGELOG.md:110` (0.1.0) says "for **future** semantic search". |
| Does a plan or PoC exist? | No. `plans/006` §out-of-scope and `plans/008` §out-of-scope both list "pgvector search" as explicitly deferred. No `plans/`, `poc/` or `learnings/` entry before this one. |
| Is there an embedding source? | No. `backend/pyproject.toml` had no `sentence-transformers`/embed model; compose preloads only `gemma4:e4b` with `OLLAMA_MAX_LOADED_MODELS=1`, so a second Ollama model would evict the extractor. The `768` dimension was arbitrary and unvalidated against any model. |
| Is there a producer or consumer? | No. Only `backend/app/models/embedding.py` + the import in `models/__init__.py`. Nothing wrote a row, no route queried one, no UI used one. Verified by `rg -n "Embedding\|embeddings" backend/app` returning the model alone. |
| Did anything need it? | No. Search is `pg_trgm` server-side + Fuse.js client-side (`README.md:100`), which already covers exact/fuzzy field lookup. |

`AGENTS.md` §1 requires feasibility → PoC → documentation before implementation. None of those steps
happened, so the code was dead on arrival — not abandoned mid-build.

### 2. What implementing it would cost on this host

Host (measured in [`015`](015-service-inventory-and-gating.md) and
[`024`](024-host-network-and-gemma-resource-reality.md)): **4 vCPU / 15.62 GiB / no swap**.
At extraction peak: **7713 MiB anon, 3070 MiB available**, with `gemma4:e4b` at ~6.7 GB idle /
~7.9 GB extracting and `mem_limit: 9g`.

Three implementation shapes were sized:

| Shape | Added RAM (RSS) | Added CPU | Fits 16 GB? |
|---|---|---|---|
| **A.** Ollama embed model (nomic / bge-m3) | +0.6–2.4 GB — **and** `OLLAMA_MAX_LOADED_MODELS=1` means every query evicts `gemma4` (30–60 s reload each way, per `015` §recommendation 4) | 20–300 ms per text | **No.** Needs `9g`→`12g`; a ~17–18 GB host |
| **B.** sentence-transformers in the worker | +0.5 GB (distiluse-768) · +1.1 GB (e5-base-768) · +2.4 GB (bge-m3-1024) | 7–100 ms per book | **Yes**, lazily loaded; e5-base consumes nearly all headroom |
| **C.** TEI sidecar (CPU) | +0.5–0.8 GB (MiniLM) · +2–3 GB (bge-m3) | same as B | Yes for MiniLM; bge-m3 only with the export stack gated |

Notes behind the numbers:

- The worker is the right host for **B**: the `OCR_LINE=true` image already bakes CPU `torch` +
  `transformers` (`docker/Dockerfile.backend:29-34`, `backend/pyproject.toml` `ocr-line` extra), so
  the marginal cost is the model weights, not the runtime. The backend is the wrong host — it would
  block the event loop.
- **A** is the worst option despite being the least code: a single-model Ollama makes semantic search
  and extraction fight over one residency slot.
- `768` dims matches distiluse/e5-base, so **B** needs no migration. `bge-m3` is 1024 dims → a column
  migration plus ~33 % index growth.

### 3. Fixed cost, independent of the shape

- One vector per book: 768 × 4 B = **3 KB** raw, ~3.1 KB with the pgvector heap header.
- 1k books ≈ 3 MB · 10k ≈ 31 MB · 100k ≈ 310 MB.
- HNSW (`vector_cosine_ops`, m=16, ef_construction=64) ≈ 1.5–2× the table: ~50 MB at 10k, ~600 MB at
  100k. Build on 4 vCPU: seconds at 10k, 2–5 min at 100k.
- Query: **<10 ms at 10k**, 10–30 ms at 100k (`ef_search` 40). `shared_buffers` is the default 128 MB,
  so a 100k-row index is partly disk-backed — acceptable, since it is a few hundred MB on a 16 GB host.
- Chunking per section instead of one row per book multiplies storage 5–10×.
- **Backfill CPU:** 10k books ≈ 1–3 min (distiluse) · 5–17 min (e5-base) · 20–60 min (bge-m3) single
  process; divide by 2–4 when parallelised. Per book this is **<0.1 %** of the ~2400 s extraction cost
  (`015` §7), i.e. irrelevant next to OCR.

### 4. The binding constraint is RAM, not CPU

At 3.0 GiB of measured headroom:

- **A** does not fit without dropping the export stack or raising host RAM.
- **B** with MiniLM/distiluse fits; **B** with e5-base fits only if run while no extraction is queued.
- **B** with bge-m3 fits only if `wikibase`/`openrefine`/`elasticsearch` are gated first — and gating
  reclaims ~2.5 GiB (`015` §2), almost exactly bge-m3's cost.

### 5. Recommendation

If semantic search is ever wanted: **768-dim multilingual (distiluse or e5-base), lazy-loaded in the
worker, one vector per book, HNSW, backfill as a maintenance job.** Cost: **+0.5–1.4 GB RAM and
minutes of CPU in total**. Prefer `bge-m3` only after `COMPOSE_PROFILES` gating lands and the host is
confirmed at ≥20 GB, and only for the Indic-quality gain. Do not implement it via Ollama.

## 6. What was removed (applied 2026-11-20)

The user confirmed the project is pre-release and the database can be dropped, so the removal was made
complete rather than leaving reserved schema:

| Change | File |
|---|---|
| Model deleted | `backend/app/models/embedding.py` (removed) |
| Import + `__all__` entry removed | `backend/app/models/__init__.py` |
| `pgvector>=0.3` dropped, lock regenerated | `backend/pyproject.toml`, `backend/uv.lock` (`uv lock --offline`) |
| `001` rewritten: no `Vector` import, no `CREATE EXTENSION vector`, no `embeddings` table, no drop in `downgrade` | `backend/alembic/versions/001_initial_schema.py` |
| New revision drops table + extension (`IF EXISTS`, no-op on fresh DBs) | `backend/alembic/versions/022_drop_embeddings.py` |
| `vector` removed, `pg_trgm` kept | `docker/postgres/init_extensions.sql` |
| Image `pgvector/pgvector:pg16` → `postgres:16-bookworm` | `docker-compose.yml`, `docker-compose.staging.yml`, `docker-compose.production.yml`, `.github/workflows/ci.yml` |
| Docs updated | `README.md`, `AGENTS.md`, `CHANGELOG.md`, `todos/015`, `docs/architecture/*`, `docs/application/data-model.md`, `docs/operations/deployment.md`, `docs/development/*` |

`pg_trgm` is **kept** — it is created by migrations `004`/`006` and powers library search. `docs/history/`
was left untouched as archived material.

### Note on the Postgres image tag (found in review, 2026-11-20)

The first pass of this change used the floating `postgres:16` tag. That is a **deploy hazard on an
existing volume**: `pgvector/pgvector:pg16` is Debian 12 / glibc **2.36**, while `postgres:16` now
resolves to Debian 13 / glibc **2.41**. Verified from the local images — both ship PostgreSQL **16.16**,
so no `pg_upgrade` is needed, but every pre-existing database records `datcollversion` 2.36. Starting
such a volume on the trixie image logs `collation version mismatch` for each database, and
`CREATE DATABASE` then fails with `ERROR: template database "template1" has a collation version
mismatch` — reproduced end to end. That breaks the restore drill (`docs/operations/backup-and-recovery.md`
uses `createdb`).

Fix: pin `postgres:16-bookworm` everywhere. It is the same PG 16.16 on the same glibc as the old image,
so the swap is byte-for-byte safe for existing `pgdata`. The alternative — moving to trixie — requires
`ALTER DATABASE ... REFRESH COLLATION VERSION` on every database including `template1`.

### Note on migration 001

`001` was edited even though `AGENTS.md` and `data-model.md` say never to edit an applied migration.
This is safe here specifically because `022` still runs on existing databases and issues
`DROP TABLE IF EXISTS embeddings` / `DROP EXTENSION IF EXISTS vector`, so **every** database — fresh or
long-lived — converges on the same schema at HEAD. The rule exists to stop fresh and existing databases
diverging; that invariant is preserved.

## 7. Next steps

1. None required. The gap is closed as **won't do**.
2. If semantic search is revived, write a `plans/0xx` with a PoC that measures recall on the frozen
   ground-truth corpus before any schema change.
3. If the host is ever resized, re-check §2 against the new `free -m` rather than these numbers.

## References

- [`015`](015-service-inventory-and-gating.md) — host inventory, memory profile, gating headroom
- [`024`](024-host-network-and-gemma-resource-reality.md) — `gemma4:e4b` residency (6.6 GB / 7.9 GiB peak)
- [`027`](027-default-preprocessing-upscale-benchmark.md) / [`029`](029-ocr-language-routing-and-font-benchmarks.md) — per-book OCR cost baseline
- `todos/015-documented-but-unimplemented.md` §3 item 10 (the gap this closes)
- `docs/application/data-model.md` — current schema and migration list