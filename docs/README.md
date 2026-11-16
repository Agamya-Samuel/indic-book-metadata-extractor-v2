# Technical Documentation

This directory is the primary technical reference for the Indic Book Metadata Extractor. It documents
the system as implemented on `main`, not an aspirational design.

## Start here

| If you want to… | Read |
| --- | --- |
| Understand what the system does | [Project overview](../README.md) |
| Understand how the pieces fit together | [System architecture](architecture/system-architecture.md) |
| Know which services are required | [Integrations and service groups](architecture/integrations.md) |
| Run the stack locally | [Local development](development/local-development.md) |
| Understand the pipeline | [Processing pipeline](processing/pipeline-overview.md) |
| Call the HTTP API | [API reference](reference/api.md) |
| Deploy it | [Deployment](operations/deployment.md) |
| Fix something at 2am | [Runbook](operations/runbook.md) |

## Documentation map

```text
docs/
├── README.md                        ← you are here (index + inventory)
├── architecture/
│   ├── system-architecture.md       topology, request path, data model, pipeline
│   ├── integrations.md              external services, service groups, gating status
│   └── decisions.md                 index of plans/ and learnings/
├── development/
│   ├── local-development.md         prerequisites, compose, seeding, day-to-day loop
│   ├── configuration.md             every environment variable and its default
│   ├── repository-structure.md      where code lives and why
│   └── contributing.md              conventions, review process, docs maintenance
├── application/
│   ├── frontend.md                  App Router structure, state, workflow rail
│   ├── backend.md                   module layout, routers, services, tasks
│   ├── authentication.md            sessions, CSRF, approval gate, RBAC
│   └── data-model.md                every table, column, relationship, enum
├── processing/
│   ├── pipeline-overview.md         upload → review, stage machine, job lifecycle
│   ├── pdf-and-pages.md             rendering, page selection, storage layout
│   ├── preprocessing.md             the OpenCV chain and per-page config
│   ├── ocr.md                       engines, routing, post-processing, corrections
│   ├── extraction.md                hybrid tiers, batches, prompts, evidence
│   └── jobs-and-queues.md           Celery topology, retries, cancel/supersede/reap
├── operations/
│   ├── deployment.md                Docker Compose, Dokploy, domains, rollback
│   ├── runbook.md                   symptom → diagnosis → action
│   ├── monitoring.md                health checks, New Relic, Flower, metrics
│   ├── backup-and-recovery.md       database and volume backups, restore drill
│   └── wikibase-operations.md       Wikibase/QuickStatements (optional, off by default)
├── testing/
│   ├── strategy.md                  what is tested where and why
│   ├── running-tests.md             commands, fixtures, CI jobs
│   └── evaluation.md                OCR/LLM benchmarks and ground-truth corpora
└── reference/
    ├── api.md                       endpoint-by-endpoint reference
    ├── metadata-fields.md           the 50-field schema and batch grouping
    └── glossary.md                 project vocabulary
```

**Status:** `architecture/`, `application/` and `processing/` are written. The remaining directories
are planned and will be filled in grouped passes (see [writing order](#writing-order)).

## Documentation status

| Group | Files | State |
| --- | --- | --- |
| Architecture | 3 | Written |
| Application | 4 | Written |
| Processing | 6 | Written |
| Development | 4 | Written |
| Operations | 5 | Written |
| Testing | 3 | Written |
| Reference | 3 | Written |

All 28 planned documents are written.

## Writing order

Documentation is written architecture-first, then in dependency order, with a review checkpoint at
each boundary:

1. **Architecture** — topology and integrations establish vocabulary used everywhere else.
2. **Application** — frontend, backend, auth, data model (depends on architecture).
3. **Processing** — the pipeline, which depends on both of the above.
4. **Reference** — API and field definitions, generated against the finished processing docs.
5. **Development** — onboarding, which links to everything but defines nothing new.
6. **Operations** — deployment and runbooks, which assume the pipeline is understood.
7. **Testing** — strategy and evaluation, which references the processing internals.

## Legacy files

Before this tree existed, `docs/` held 25 flat files written at various points during development:
`runbook.md`, `api-reference.md`, `developer-guide.md`, `local-development-guide.md`,
`tech_stack.md`, `user-guide.md`, `known-issues.md`, `monitoring.md`, `ocr-setup.md`,
`ocr-training.md`, `wikibase-reference.md`, `changelog.md`, and others.

They are **superseded** by the organised tree above and should not be treated as current. They are
kept for now because they contain detail that has not all been migrated (notably the user-facing
guide and the OCR training notes).

Migration is deliberately incomplete rather than half-done: the new documents describe current
behaviour, and the old files are left untouched so nothing is lost. Removing or merging them is a
separate task, tracked in [repository structure](development/repository-structure.md).

## Conventions

- **Implemented vs planned vs known-issue** must be marked explicitly. A feature that does not exist
  is not documented as if it does.
- **No host-specific detail.** Production IPs, node names, panel ports and credentials never appear
  in `docs/`. Operational specifics live in a gitignored `infra/local/`.
- **Diagrams** use Mermaid fenced code blocks so they render on GitHub.
- **Code references** are relative paths from the repository root, e.g.
  `backend/app/tasks/ocr_tasks.py`.
- **No duplication.** A fact has exactly one home; other documents link to it.

## Documentation maintenance

There is no automated documentation gate. Keeping these documents accurate is a review
responsibility, described in [contributing.md](development/contributing.md). The short version:

| If you change… | Update |
| --- | --- |
| A router, endpoint, or response shape | `reference/api.md` |
| A migration, model, or enum | `application/data-model.md` |
| Auth, sessions, CSRF, or roles | `application/authentication.md` |
| OCR engines, preprocessing, or routing | `processing/ocr.md`, `processing/preprocessing.md` |
| Prompts, batches, or extraction tiers | `processing/extraction.md`, `reference/metadata-fields.md` |
| A Celery task, queue, or retry policy | `processing/jobs-and-queues.md` |
| Compose services, ports, or volumes | `operations/deployment.md`, `architecture/integrations.md` |
| A health check or metric | `operations/monitoring.md` |
| A frontend route or workflow step | `application/frontend.md`, `processing/pipeline-overview.md` |
