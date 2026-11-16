# Contributing

How work is proposed, implemented, reviewed, and documented in this repository.

This project has an unusual convention set: it separates **intent** (`plans/`), **evidence**
(`learnings/`) and **current truth** (`docs/`). Following that separation is the main thing that keeps
the documentation honest.

---

## 1. Before writing code

Work goes through four gates, in order:

```text
feasibility study → proof of concept → documentation → implementation
```

1. **Feasibility** — is this achievable with the available hardware, data and libraries? Recorded in
   `plans/XXX-*.md` with explicit success criteria.
2. **PoC** — a minimal validated approach in `poc/`, with results in `learnings/`.
3. **Documentation** — the approach is written down before it is productionised.
4. **Implementation** — incremental, with verification at each step.

**No implementation without a documented PoC.** Small fixes and obvious bugs are exempt; anything that
changes a pipeline stage, an extraction tier, or a service is not.

If a study hits a blocker (OCR accuracy too low, LLM unreliable), stop and escalate — document it in
`learnings/`, propose alternatives in the plan, and get a product-level decision before proceeding.

---

## 2. Records

| Folder | When | Contents |
| --- | --- | --- |
| `plans/` | Before work | Scope, approach, success criteria, alternatives |
| `learnings/` | After work | Measurements, outcome, what it means |
| `todos/` | During long work | Handoff state for the next session |
| `poc/` | After validation | The validated artefact |

Naming is `XXX-description.md` with a three-digit number, allocated sequentially per folder. Do not
reuse a number. Include a `**Status:**` line — [the index](../architecture/decisions.md) reads it.

Link a plan from its learning and vice versa. When behaviour changes, update the relevant `docs/` file
in the same change.

---

## 3. Code conventions

### Backend (Python)

- `uv` for dependencies; `uv run` for execution.
- Ruff for both formatting and linting: `uv run ruff format .` and `uv run ruff check .`.
- Type hints on public functions; `from __future__ import annotations` where it helps.
- Async SQLAlchemy throughout. **Never** open a second session for a stage transition — it deadlocks
  against the transaction's foreign-key locks.
- Services own logic; routers stay thin.
- Route errors through `AuthError` / `HTTPException`, not bare exceptions.
- Truncate anything persisted in an error column (`[:2000]`).

### Frontend (TypeScript)

- App Router, client components marked `"use client"`.
- TanStack Query for server state; Zustand only for cross-step UI state.
- All HTTP goes through `frontend/src/lib/api.ts`. Do not call `fetch` directly in components.
- `npm run lint` and `npm test` before pushing.
- New workflow logic belongs in `lib/workflow-state.ts`, not duplicated in components.

### Both

- No comments that restate the code. Comment **why**, especially where a constraint is non-obvious.
- Do not add abstractions for single use sites.
- Delete dead code rather than leaving it flagged.

---

## 4. Commits

- **Small, logical commits.** Not one giant commit per task.
- **Heading plus body.** The heading is a conventional prefix (`feat`, `fix`, `docs`, `perf`,
  `refactor`, `test`, `build`, `ci`, `chore`) and a short imperative summary. The body explains what
  changed and why.
- **No co-author trailers.** This repository intentionally omits them.
- Reference the learning or plan in the body when the change implements one.

Example:

```text
feat(ocr): route dominant-script pages to the narrowed language model

Telugu pages measured 0.331 CER on tel+eng and 0.272 on tel alone; Hindi
0.081 vs 0.063. Re-OCR with the narrowed model when the expected script
share is at least 0.85 and Latin is at most 0.15, keeping the alternative
only when it produces at least 90% of the original text length.

Evidence: learnings/029, plans/020
```

---

## 5. Review

There is **no automated documentation gate** and no CI check that fails on stale docs. Accuracy is a
review responsibility, not a build step.

A reviewer should confirm:

| Check | Why |
| --- | --- |
| Does the change match its plan? | Prevents scope drift |
| Is there a learning for non-obvious measurements? | Keeps evidence reproducible |
| Are the relevant `docs/` files updated? | This is the only thing keeping docs current |
| Do new env vars appear in `configuration.md`? | Otherwise they are discoverable only in code |
| Do new endpoints appear in `api.md`? | Same |
| Do new services/ports appear in `deployment.md` and `integrations.md`? | Same |
| Were migrations added, not edited? | Editing an applied migration corrupts history |
| Do tests pass? | `npm test`, backend unit suite, `make test-e2e` where relevant |

---

## 6. Documentation maintenance

When you change something, update its single home:

| Change | Update |
| --- | --- |
| Router, endpoint, response shape | `docs/reference/api.md` |
| Model, enum, migration | `docs/application/data-model.md` |
| Auth, sessions, CSRF, roles | `docs/application/authentication.md` |
| OCR engine, routing, post-processing | `docs/processing/ocr.md` |
| Preprocessing chain or defaults | `docs/processing/preprocessing.md` |
| Prompts, batches, tiers | `docs/processing/extraction.md`, `docs/reference/metadata-fields.md` |
| Celery task, queue, retry policy | `docs/processing/jobs-and-queues.md` |
| Compose service, port, volume | `docs/operations/deployment.md`, `docs/architecture/integrations.md` |
| Health check, metric, alert | `docs/operations/monitoring.md` |
| Frontend route or workflow step | `docs/application/frontend.md`, `docs/processing/pipeline-overview.md` |
| Environment variable | `docs/development/configuration.md` |

**Rules for docs themselves:**

1. Describe what the code does, not what it should do.
2. Mark `implemented` / `known limitation` / `planned` explicitly.
3. No host-specific detail — no IPs, node names, panel ports or credentials. Public repository.
4. One fact, one home. Link instead of repeating.
5. Mermaid for diagrams so they render on GitHub.

---

## 7. Compose changes

Both compose files must stay in sync. After editing either:

```bash
make check-compose-drift
```

This diffs production against staging and ignores the expected deltas (comments, `DEBUG`,
`NEW_RELIC_*`, `APP_NAME`, memory limits, `WIKIBASE_SCHEME`, worker concurrency, URL schemes). An
unexpected diff means one file was updated and the other was not.

Remember that **development splits `worker-ocr` / `worker-llm`, production uses one `worker`**. Do not
"fix" that difference.

---

## 8. Safety

| Do not | Instead |
| --- | --- |
| `make clean` or `docker compose down -v` with data you need | Stop services only |
| Delete optional-service volumes to "free space" | Gate them with profiles; volumes hold state |
| Edit an applied migration | Add a new revision |
| Force-push shared branches without agreement | Open a PR |
| Commit a real credential | Use `.env` (gitignored) and rotate anything that leaked |

If you find a leaked secret, **rotate it first**. Scrubbing history does not invalidate a live
credential.
