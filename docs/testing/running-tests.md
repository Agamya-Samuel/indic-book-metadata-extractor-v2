# Running Tests

Commands for each suite. For what is tested and why, see [strategy](strategy.md).

---

## 1. Backend

pytest configuration lives in `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`asyncio_mode = "auto"` means async tests need no decorator.

```bash
cd backend
uv sync                                  # first time

uv run pytest                            # everything
uv run pytest tests/unit                 # unit only
uv run pytest tests/integration          # needs a database
uv run pytest tests/unit/test_client_ip.py            # one file
uv run pytest tests/unit/test_client_ip.py::test_x    # one test
uv run pytest -k "stage or supersede"    # by name
uv run pytest -x --lf                    # stop on first failure, rerun last failed
```

Integration tests need a reachable PostgreSQL with migrations applied. The simplest reliable setup is
the compose database:

```bash
docker compose up -d postgres redis
docker compose exec backend uv run pytest tests/integration
```

---

## 2. Backend lint and format

```bash
cd backend
uv run ruff format .
uv run ruff check .
```

Line length is 120 (`[tool.ruff]`). CPU-only torch is pinned through a dedicated index
(`pytorch-cpu`), so `uv sync` never pulls CUDA wheels.

---

## 3. Frontend

Scripts from `frontend/package.json`:

```bash
cd frontend
npm install

npm test               # vitest run (CI mode)
npm run test:watch     # watch mode
npm run test:coverage  # with coverage

npm run lint           # eslint
npm run lint:contrast  # custom contrast checker

npm run test:e2e       # playwright
npm run test:e2e:ui    # playwright interactive
```

Single file or pattern:

```bash
npx vitest run tests/lib/workflow-state.test.ts
npx vitest run -t "marks downstream stages stale"
```

---

## 4. End-to-end

```bash
make test-e2e
```

Runs `backend/scripts/e2e_smoke.py` against a running stack: upload → select pages → OCR → extract,
asserting that jobs are created, dispatched, and reach a terminal state.

A full production-shaped run lives in `backend/scripts/e2e_prod.py` and targets a deployed
environment.

E2E requires a healthy stack, a reachable Ollama with the model pulled, and a sample PDF. It is slower
than everything else combined.

---

## 5. Inside containers

```bash
docker compose exec backend uv run pytest
docker compose exec backend uv run ruff check .
docker compose exec frontend npm test
```

Useful when a host toolchain would differ from the image.

---

## 6. Before pushing

Minimum:

```bash
cd backend  && uv run ruff format --check . && uv run ruff check . && uv run pytest tests/unit
cd frontend && npm run lint && npm test
```

If you touched either compose file:

```bash
make check-compose-drift
```

If you changed OCR or prompts, run the relevant evaluation instead of relying on tests — see
[evaluation](evaluation.md).

---

## 7. CI

`.github/workflows/ci.yml` and `.github/workflows/security.yml` exist. **There is no documentation
check in CI** and no docs coverage gate, by decision: docs accuracy is a review responsibility
(see [contributing](../development/contributing.md)).

Read the workflow files for the exact jobs and triggers rather than trusting a description here.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `pytest` cannot connect | No database running | `docker compose up -d postgres` |
| Integration tests hang | A `FOR UPDATE` waiting on another session | Ensure no worker is running against the same DB |
| Vitest cannot resolve `@/` | Running outside `frontend/` | `cd frontend` first |
| Playwright browsers missing | First run | `npx playwright install` |
| E2E times out at extraction | Model not pulled or Ollama cold | `make download-model`; allow the first load |
| Ruff reformats a file you just wrote | Line length 120, import order | Accept the format run |
