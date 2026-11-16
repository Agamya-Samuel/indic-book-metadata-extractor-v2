# Local Development

Running the whole stack locally, and the day-to-day loop.

- Compose: `docker-compose.yml` (development)
- Task runner: `Makefile`
- Frontend: `frontend/` (Next.js 16)
- Backend: `backend/` (FastAPI, `uv`)

---

## 1. Prerequisites

| Tool | Why |
| --- | --- |
| Docker + Compose v2 | Everything runs in containers; no host Python/Node required |
| Make | The `Makefile` is the supported entry point |
| ~20 GB free disk | Images plus the Ollama model |
| 16 GB RAM recommended | Ollama plus Tesseract are memory-hungry |

`uv` and Node are only needed if you run the backend or frontend **outside** Docker.

---

## 2. First run

```bash
cp .env.example .env          # then edit the required values
make up                       # build and start
make status                   # container health
make migrate                  # apply Alembic migrations
make create-admin             # first admin account
make download-model           # pull the Ollama model
```

Then open the frontend on `http://localhost:3000`.

`.env.example` is the template. At minimum set a real `POSTGRES_PASSWORD`, a ≥32-character
`JWT_SECRET_KEY`, and `FRONTEND_URL`. See [configuration](configuration.md) for every variable.

---

## 3. Development topology differs from production

This is the most common source of confusion. **Dev splits the workers; production does not.**

| | Development (`docker-compose.yml`) | Production (`docker-compose.production.yml`) |
| --- | --- | --- |
| OCR tasks | `worker-ocr`, `-Q ocr,default`, concurrency 1 | `worker`, `-Q ocr,llm,default`, concurrency 1 |
| LLM tasks | `worker-llm`, `-Q llm`, concurrency 1 | same single `worker` |
| New Relic infra agent | present under `profiles: [monitoring]` | absent |
| Debug | `DEBUG=true` | `DEBUG=false` |

So `make logs-worker-ocr` and `make logs-worker-llm` exist, but in production both queues are served by
one container. Queue names are identical either way.

---

## 4. Make targets

| Target | Purpose |
| --- | --- |
| `up` / `down` / `restart` | Compose lifecycle |
| `build` / `rebuild` | Build images |
| `status` / `logs` | Container health and logs |
| `logs-backend`, `logs-worker-ocr`, `logs-worker-llm` | Per-service logs |
| `migrate` | Run Alembic migrations |
| `create-admin` | Create/promote an admin (interactive) |
| `reset-db` | **Destructive** — drop and recreate the database |
| `download-model` | Pull the configured Ollama model |
| `test-e2e` | Run the end-to-end script against a running stack |
| `shell-backend` | Shell into the backend container |
| `clean` | Remove containers and volumes — **destructive** |
| `backup-db`, `backup-storage`, `backup`, `restore-db` | Backup and restore |
| `check-compose-drift` | Diff production vs staging compose, ignoring expected deltas |
| `deploy`, `deploy-status`, `deploy-env` | Dokploy helpers (see [deployment](../operations/deployment.md)) |
| `prompt-*` | Prompt evaluation harness (`corpus`, `mask`, `fewshot`, `bundles`, `eval`, `report`, …) |
| `wikibase-*` | Optional Wikibase stack helpers |

---

## 5. Running code outside Docker

Useful for fast iteration on one side of the stack.

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

You still need PostgreSQL, Redis and Ollama reachable — easiest is to start just those:

```bash
docker compose up -d postgres redis ollama
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run lint
npm test               # vitest
npm run test:coverage
```

When running outside Docker, `NEXT_PUBLIC_API_URL` must point at the backend origin, and that origin
must appear in `CORS_ORIGINS`. Cookies are `SameSite=Lax`, so a cross-origin setup breaks sessions —
prefer keeping everything on `localhost:3000` via the Docker frontend.

---

## 6. Day-to-day loop

1. `make logs-worker-ocr` (or `-llm`) in one terminal.
2. Upload a small PDF and drive one stage at a time.
3. For OCR changes, run the OCR evaluation harness rather than eyeballing one page — see
   [evaluation](../testing/evaluation.md).
4. Run `npm run lint`, `npm test` (frontend) and the backend unit suite before pushing.
5. `make check-compose-drift` if you touched either compose file.

---

## 7. First-run troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Backend exits: `JWT_SECRET_KEY must be at least 32 characters` | Non-debug mode with a short key | Set a 64-char hex value |
| Upload returns 413 | `MAX_UPLOAD_SIZE_MB` too low | Raise it in `.env` and restart |
| OCR returns empty text | Model language data missing | Check `TESSERACT_TESSDATA_DIR`; see [ocr](../processing/ocr.md) |
| Extraction returns all nulls | Ollama model not pulled, or wrong endpoint | `make download-model`; check `LLM_NATIVE_ENDPOINT` for thinking models |
| Emails not sent | `SMTP_ENABLED=false` (the default) | Set SMTP variables, or accept in-app notifications only |
| Book stuck at `ocr_running` | A worker died | Wait for the reaper (90 min) or cancel the job |
| `make up` slow | First build plus model pull | Expected on a cold cache |

---

## 8. Notes

- **Never `make clean` on a machine with data you want** — it removes volumes.
- **`make reset-db` is destructive** and does not touch the storage volume, so file/row references
  will dangle afterwards.
- **The `.env` file is gitignored.** Only `.env.example` and the per-environment examples are tracked.
