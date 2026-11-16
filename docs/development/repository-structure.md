# Repository Structure

Where things live and why. Paths are relative to the repository root.

---

## Top level

```text
.
├── backend/                  FastAPI app, Celery tasks, migrations, tests, eval scripts
├── frontend/                 Next.js 16 App Router application
├── docker/                   Dockerfiles, entrypoints, service config, helper scripts
├── docs/                     ← this documentation (current truth)
├── plans/                    Proposals and ADRs, written before work
├── learnings/                Findings and measurements, written after work
├── todos/                    Long-running task handoffs
├── poc/                      Proof-of-concept artefacts
├── probes/ ├── probing/      (if present) exploratory experiments
├── fixtures/                 Test and evaluation data
├── infra/                    Host/infrastructure notes
├── reference/                External reference material (gitignored host notes)
├── scripts/                  Repository-level scripts (deploy helpers)
├── docker-compose.yml                 Development stack
├── docker-compose.production.yml      Production stack (Dokploy)
├── docker-compose.staging.yml         Staging stack
├── Makefile                  Supported task entry point
├── DEPLOY.md                 Pointer to docs/operations/deployment.md
├── AGENTS.md                 Agent workflow conventions
└── README.md                 Project overview
```

---

## `backend/`

```text
backend/
├── app/
│   ├── main.py               App, middleware, lifespan, health, error handlers
│   ├── api/                  HTTP layer (routers, deps)
│   ├── core/                 Config, DB, security, Redis, media tokens, logging
│   ├── models/               SQLAlchemy ORM
│   ├── schemas/              Pydantic request/response + LLM batch models
│   ├── services/             Business logic (OCR, LLM, preprocessing, stages, auth…)
│   │   ├── extractors/       Regex and dictionary tiers + hybrid orchestrator
│   │   └── dictionaries/     Language word lists
│   └── tasks/                Celery tasks, lock, cancellation, async bridges
├── alembic/versions/         20 migrations, applied in order
├── tests/
│   ├── unit/                 Pure and mocked tests
│   ├── integration/          Database/task integration
│   └── fixtures/             Samples and ground truth
├── scripts/                  Evaluation, enrichment and E2E run scripts
├── prompt_eval/              Prompt experiment bundles, masks, few-shot files
├── reports/                  Generated benchmark and profile artefacts
├── pyproject.toml            Dependencies + tool config (ruff, pytest)
└── uv.lock                   Locked dependency graph
```

Generated artefacts under `reports/` and `prompt_eval/` are evidence, not source. They are committed
so results are reproducible, but they are not imported by the application.

---

## `frontend/`

```text
frontend/
├── src/
│   ├── app/                  App Router routes (see application/frontend.md)
│   ├── components/           shared/, book/, ocr/, metadata/, admin/, auth/, notifications/
│   ├── hooks/                use-sse, use-job-polling, use-book-status, use-ocr-corpus…
│   ├── lib/                  api.ts, workflow-state.ts, pagination, error handling
│   ├── stores/               Zustand book store
│   └── types/                Ambient type declarations
├── tests/                    components/, hooks/, lib/, pages/, stores/
├── public/                   Static assets
├── next.config.ts            Standalone output, security headers, New Relic externals
├── vitest.config.ts          Unit test config
└── package.json              Scripts: dev, build, lint, test, test:e2e
```

---

## `docker/`

```text
docker/
├── Dockerfile.backend        Backend image (worker adds OCR_LINE build arg)
├── Dockerfile.frontend       Next.js standalone image
├── scripts/
│   ├── backend-entrypoint.sh Runs migrations, then uvicorn
│   └── backup-db.sh          pg_dump with retention
├── ollama-entrypoint.sh      Preloads the configured model
├── Modelfile.phi4-mini       Rollback model definition
├── postgres/init_extensions.sql
├── mysql/init_wikibase.sql
├── wikibase/                 Dockerfile, LocalSettings overrides, create-properties.sh
└── openrefine/Dockerfile
```

---

## Records and conventions

| Folder | Naming | Rule |
| --- | --- | --- |
| `plans/` | `XXX-description.md` | Written **before** work; includes success criteria |
| `learnings/` | `XXX-description.md` | Written **after** work; includes measurements |
| `todos/` | `XXX-description.md` | Handoff notes for long-running work |
| `poc/` | `XXX-poc-description.md` | Validated approaches only |
| `fixtures/` | `XXX-fixtures-description.md` | Test/eval data and ground truth |

Three-digit sequential numbering per folder. Numbers are allocated by date, not index — gaps and
duplicates exist and are left alone because renumbering would break cross-references. Index in
[decisions](../architecture/decisions.md).

---

## What owns what

| Concern | Single home |
| --- | --- |
| Current behaviour | `docs/` |
| Why a decision was made | `plans/` |
| What the measurement showed | `learnings/` |
| Runtime configuration | `backend/app/core/config.py` |
| API surface | `backend/app/api/` |
| Field schema | `backend/app/schemas/metadata.py` |
| Prompts | `backend/app/services/prompt_profiles.py` |
| Service topology | `docker-compose.production.yml` |
| Workflow step mapping | `frontend/src/lib/workflow-state.ts` |

---

## Files that look authoritative but are not

| Path | Why |
| --- | --- |
| `docs/*.md` (flat files predating this tree) | Superseded by `docs/architecture|application|processing|…`. Kept until migrated; see [migration note](../README.md#legacy-files) |
| `docs/implementation_plan.md` | Historical plan, not current state |
| `learnings/015` | Predates the `gemma4:e4b` switch |
| `learnings/014` | References removed routes `/library` and `/bulk-operations` |
| `backend/reports/*` | Generated evidence; not inputs |
