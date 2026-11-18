# Technical Documentation

The primary technical reference for the Indic Book Metadata Extractor. It documents the system as
implemented on `main`.

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
| Publish metadata to OpenRefine/Wikibase | [Export pipeline](operations/export-pipeline.md) |
| Fix something at 2am | [Runbook](operations/runbook.md) |
| Use the application | [User guide](user-guide.md) |

## Documentation map

```text
docs/
├── README.md                        ← you are here
├── architecture/
│   ├── system-architecture.md       topology, request path, data model, pipeline
│   ├── integrations.md              external services, service groups, gating status
│   └── decisions.md                 index of plans/ and learnings/
├── application/
│   ├── frontend.md                  App Router structure, state, workflow rail
│   ├── backend.md                   module layout, routers, services, tasks
│   ├── authentication.md            sessions, CSRF, approval gate, RBAC
│   └── data-model.md                every table, column, relationship, enum
├── processing/
│   ├── pipeline-overview.md         upload → review, stage machine, job lifecycle
│   ├── pdf-and-pages.md             rendering, page selection, storage layout
│   ├── preprocessing.md             the OpenCV chain and per-page config
│   ├── ocr.md                       engines, routing, post-processing, troubleshooting
│   ├── ocr-training.md              fine-tuning the Telugu line model
│   ├── extraction.md                hybrid tiers, batches, prompts, evidence
│   └── jobs-and-queues.md           Celery topology, retries, cancel/supersede/reap
├── development/
│   ├── local-development.md         prerequisites, Docker, native setup, ports
│   ├── configuration.md             every environment variable and its default
│   ├── repository-structure.md      where code and data live
│   └── contributing.md              conventions, review, docs maintenance
├── operations/
│   ├── deployment.md                compose, Dokploy, domains, rollback
│   ├── export-pipeline.md           application → OpenRefine → Wikibase, verified
│   ├── runbook.md                   symptom → diagnosis → action
│   ├── monitoring.md                health, New Relic, admin metrics, alerting
│   ├── backup-and-recovery.md       dumps, restore drill, volume inventory
│   ├── bulk-operations.md           OpenRefine + Wikibase bulk workflows
│   ├── wikibase-operations.md       optional stack, extensions, known defects
│   ├── wikidata-workflow.md         QID creation and property mapping
│   └── ocr-postdeploy.md            post-deploy OCR tuning steps
├── testing/
│   ├── strategy.md                  what is tested where and why
│   ├── running-tests.md             commands, fixtures, CI
│   ├── evaluation.md                OCR/LLM benchmarks and ground truth
│   └── results/
│       ├── llm-model-evaluation.md  model comparison results
│       └── ground-truth-coverage.md corpus conformance and coverage
├── reference/
│   ├── api.md                       endpoint reference and body schemas
│   ├── metadata-fields.md           the 49-field schema, batches, Wikidata mapping
│   └── glossary.md                  project vocabulary
├── user-guide.md                    end-user walkthrough
├── known-limitations.md             limits, gaps, platform notes
└── history/                         archived documents — past state, not current
```

Related top-level directories:

| Directory | Contents |
| --- | --- |
| [`datasets/`](../datasets/README.md) | Ground truth, sample PDFs, frozen evaluation corpus |
| [`benchmarks/`](../benchmarks/README.md) | Measured outputs: reports and prompt-eval results |
| [`learnings/`](../learnings/) | Evidence written after work; indexed in [decisions](architecture/decisions.md) |
| [`plans/`](../plans/) | Proposals written before work |
| [`todos/`](../todos/) | Execution checklists for long-running work |

## Conventions

- **Implemented vs planned vs known-issue** is marked explicitly. A feature that does not exist is not
  documented as if it does.
- **No host-specific detail.** Production IPs, node names, panel ports and credentials never appear in
  `docs/`. Operational specifics live in a gitignored `infra/local/`.
- **Diagrams** use Mermaid fenced code blocks so they render on GitHub.
- **Code references** are relative paths from the repository root.
- **No duplication.** A fact has exactly one home; other documents link to it.
- **Archived material** lives in [history/](history/README.md) and is never treated as current.

## Documentation maintenance

There is no automated documentation gate. Keeping these documents accurate is a review responsibility,
described in [contributing.md](development/contributing.md). The short version:

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
| An environment variable | `development/configuration.md` |
| A dataset, sample, or corpus path | `datasets/README.md` and the script that reads it |
