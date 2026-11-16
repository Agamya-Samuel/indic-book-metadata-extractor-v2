# Repository Structure

Where things live and why. Paths are relative to the repository root.

---

## Top level

```text
.
├── backend/                  FastAPI app, Celery tasks, migrations, scripts
├── frontend/                 Next.js 16 App Router application
├── docker/                   Dockerfiles, entrypoints, service config
├── docs/                     Technical documentation (current truth)
├── datasets/                 Evaluation and test data (inputs)
├── benchmarks/               Measured outputs and reports
├── learnings/                Evidence written after work
├── plans/                    Proposals written before work
├── todos/                    Execution checklists
├── poc/                      Proof-of-concept artefacts
├── infra/                    Infrastructure notes (host details gitignored)
├── scripts/                  Repository-level tooling (deployment)
├── reference/                External reference, gitignored
├── docker-compose.yml                 Development stack
├── docker-compose.production.yml      Production stack (Dokploy)
├── docker-compose.staging.yml         Staging stack
├── Makefile                  Supported task entry point
├── README.md                 Project overview and docs pointer
├── CHANGELOG.md              Version history (currently stale)
└── AGENTS.md                 Agent workflow conventions
```

---

## `docs/`

```text
docs/
├── README.md                 Index and navigation
├── architecture/             Topology, integrations, decisions index
├── application/              Frontend, backend, auth, data model
├── processing/               Pipeline, pages, preprocessing, OCR, extraction, jobs
├── development/              Setup, configuration, structure, contributing
├── operations/               Deployment, runbook, monitoring, backup, Wikibase
├── testing/                  Strategy, commands, evaluation, results/
├── reference/                API, metadata fields, glossary
├── user-guide.md             End-user walkthrough
├── known-limitations.md      Limits, gaps, platform notes
└── history/                  Archived documents — past state, not current
```

`docs/history/` is the only place where documents describing a superseded state are allowed. See
[its README](../history/README.md).

---

## `datasets/` and `benchmarks/`

Data and results are separated from source code and from each other.

```text
datasets/                     inputs
├── ground-truth/{hin,tel}/   Per-book expected metadata and Wikisource text
├── samples/{eng,hin,tel,bilingual}/
├── evaluation/{corpus,masks,fewshot}/, manifest.json
└── README.md

benchmarks/                   outputs
├── reports/                  gt-eval, ocr-*, llm-config-*, pipeline profiles
├── prompt-eval/              Prompt variant reports
└── README.md
```

PDFs are gitignored in both sample and ground-truth directories; only the small JSON scaffolds are
committed. Generated evaluation bundles are gitignored too. See
[datasets/README.md](../../datasets/README.md).

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
│   └── fixtures/             Only what the suite reads; datasets live at the root
├── scripts/                  ~50 evaluation, enrichment and E2E modules
├── pyproject.toml            Dependencies + tool config (ruff, pytest)
└── uv.lock                   Locked dependency graph
```

`backend/scripts/` is intentionally **not** reorganised. Modules are imported as
`scripts.prompt_eval.*` and invoked as `python -m scripts.<name>` from `backend/`, and a unit test
imports `scripts.evaluate_extraction`. Moving them would touch ~50 entry points for organisational
tidiness only.

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

## `scripts/` (repository level)

```text
scripts/
└── deploy/dokploy-deploy.sh
```

Only repository-level tooling lives here. Application-adjacent tooling lives in
`backend/scripts/`.

---

## Records and conventions

| Folder | Naming | Rule |
| --- | --- | --- |
| `plans/` | `XXX-description.md` | Written **before** work; includes success criteria |
| `learnings/` | `XXX-description.md` | Written **after** work; includes measurements |
| `todos/` | `XXX-description.md` | Handoff notes for long-running work |
| `poc/` | `XXX-poc-description.md` | Validated approaches only |

Three-digit sequential numbering per folder. Numbers are allocated by date, not index — gaps and
duplicate `011` entries exist and are left alone because renumbering would break cross-references.
Index in [decisions](../architecture/decisions.md).

---

## What owns what

| Concern | Single home |
| --- | --- |
| Current behaviour | `docs/` |
| Why a decision was made | `plans/` |
| What the measurement showed | `learnings/` |
| Evaluation inputs | `datasets/` |
| Benchmark outputs | `benchmarks/` |
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
| `docs/history/*` | Archived; describes a past state |
| `CHANGELOG.md` | Last entry is `[0.1.0] — 2026-05-29`; not maintained since |
| `learnings/015` | Predates the `gemma4:e4b` switch |
| `learnings/014` | References removed routes `/library` and `/bulk-operations` |
| `benchmarks/reports/*` | Generated evidence; not inputs |
