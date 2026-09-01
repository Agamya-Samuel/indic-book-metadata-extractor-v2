.PHONY: help up down build rebuild logs logs-backend logs-worker-ocr logs-worker-llm reset-db download-model migrate test-e2e status shell-backend clean restart backup-db backup-storage backup restore-db deploy deploy-status deploy-env wikibase-shell wikibase-logs wikibase-update install-gadgets wikibase-init check-compose-drift

help:
	@echo "Indic Book Metadata Extractor - Development Commands"
	@echo "===================================================="
	@echo ""
	@echo "  make up              Start all services (detached)"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make build           Build all images"
	@echo "  make rebuild         Rebuild all images (no cache) and restart"
	@echo "  make status          Show status of all services"
	@echo "  make logs            Tail logs for all services"
	@echo "  make logs-backend    Tail backend logs"
	@echo "  make logs-worker-ocr  Tail OCR worker logs"
	@echo "  make logs-worker-llm  Tail LLM worker logs"
	@echo "  make migrate         Run database migrations"
	@echo "  make reset-db        Reset database (destroys data!)"
	@echo "  make download-model  Download Qwen2.5 7B model to Ollama"
	@echo "  make test-e2e        Run end-to-end smoke test"
	@echo "  make shell-backend   Open shell in backend container"
	@echo "  make backup-db       Create a manual database backup"
	@echo "  make backup-storage  Create a manual storage backup"
	@echo "  make backup          Backup both database and storage"
	@echo "  make restore-db      Restore database from backup (BACKUP=file.dump)"
	@echo "  make clean           Remove all containers, volumes, and images"
	@echo ""
	@echo "  Wikibase:"
	@echo "  make wikibase-shell  Open shell in wikibase container"
	@echo "  make wikibase-logs   Tail wikibase logs"
	@echo "  make wikibase-update Rebuild custom wikibase image and restart"
	@echo "  make wikibase-init   Run property creation (first boot only)"
	@echo "  make install-gadgets Install curated Wikidata gadgets"
	@echo ""
	@echo "  Dokploy Deployment:"
	@echo "  make deploy          Push to main + trigger Dokploy deploy"
	@echo "  make deploy-status   Check Dokploy deployment status"
	@echo "  make deploy-env      Show required env vars for Dokploy"
	@echo ""
	@echo "  Multi-env safety:"
	@echo "  make check-compose-drift  Diff prod vs staging compose, fail on unexpected drift"

up:
	@echo "Starting services..."
	docker compose up -d

down:
	@echo "Stopping services..."
	docker compose down

restart:
	@echo "Restarting services..."
	docker compose restart

build:
	@echo "Building images..."
	docker compose build

rebuild:
	@echo "Rebuilding images (no cache)..."
	docker compose build --no-cache
	docker compose up -d

status:
	docker compose ps

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-worker-ocr:
	docker compose logs -f worker-ocr

logs-worker-llm:
	docker compose logs -f worker-llm

migrate:
	@echo "Running database migrations..."
	docker compose exec backend uv run alembic upgrade head

reset-db:
	@echo "WARNING: This will destroy all database data!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds..."
	@sleep 5
	docker compose down -v
	docker compose up -d postgres redis
	@echo "Waiting for postgres to be ready..."
	@sleep 5
	docker compose up -d backend worker-ocr worker-llm
	@echo "Database reset complete. Run 'make up' to start all services."

download-model:
	@echo "Downloading Qwen2.5 7B model..."
	docker compose exec ollama ollama pull qwen2.5:7b

test-e2e:
	@echo "Running E2E smoke test..."
	@echo "Usage: make test-e2e PDF=path/to/test.pdf"
	docker compose exec backend uv run python scripts/e2e_smoke.py --pdf $(or $(PDF),$(error PDF is required: make test-e2e PDF=path/to/test.pdf))

shell-backend:
	docker compose exec backend bash

clean:
	@echo "Cleaning up containers, volumes, and local images..."
	docker compose down -v --rmi local
	@echo "Clean complete."

backup-db:
	@echo "Creating database backup..."
	docker compose exec backup /backup-db.sh

backup-storage:
	@echo "Creating storage backup..."
	bash docker/scripts/backup-storage.sh

backup:
	$(MAKE) backup-db
	$(MAKE) backup-storage

restore-db:
	@echo "Restoring database from backup..."
	bash docker/scripts/restore-db.sh $(or $(BACKUP),$(error BACKUP is required: make restore-db BACKUP=./backups/indic_books_20240101_120000.dump))

# ── Wikibase ──────────────────────────────────────────────────────────────────

wikibase-shell:
	docker compose exec wikibase bash

wikibase-logs:
	docker compose logs -f wikibase

wikibase-update:
	@echo "Rebuilding custom Wikibase image..."
	docker compose build wikibase
	docker compose up -d wikibase wikibase-jobrunner

wikibase-init:
	@echo "Running property creation..."
	docker compose run --rm wikibase-init

install-gadgets:
	@echo "Installing curated Wikidata gadgets..."
	docker compose exec wikibase bash /install-gadgets.sh

# ── Dokploy Deployment ─────────────────────────────────────────────────────────

deploy:
	@bash scripts/dokploy-deploy.sh

deploy-status:
	@bash scripts/dokploy-deploy.sh --status

deploy-env:
	@bash scripts/dokploy-deploy.sh --env-setup

# ── Compose Drift Check ────────────────────────────────────────────────────────
# Production and staging compose files share 95% of their content. When you
# edit one, you almost always need to edit the other. This target diffs the
# two files, ignoring the lines that are expected to differ (DEBUG, env labels,
# memory limits, scheme). If a diff shows changes outside that allowlist, the
# environments have likely drifted and need a manual sync.

check-compose-drift:
	@echo "Diffing docker-compose.production.yml vs docker-compose.staging.yml..."
	@echo "(ignoring expected deltas: comments, DEBUG, NEW_RELIC_*, APP_NAME, memory limits,"
	@echo " WIKIBASE_SCHEME, worker concurrency, URL schemes)"
	@diff -u \
		--label=docker-compose.production.yml \
		--label=docker-compose.staging.yml \
		docker-compose.production.yml docker-compose.staging.yml \
	| grep -E '^[+-]' \
	| grep -vE '^(---|\+\+\+)' \
	| grep -vE '^[+-][[:space:]]*#' \
	| grep -vE 'DEBUG: "?(true|false)"?' \
	| grep -vE 'NEW_RELIC_(ENVIRONMENT|APP_NAME|LOG):' \
	| grep -vE 'APP_NAME:' \
	| grep -vE 'staging' \
	| grep -vE 'memory: (128M|1G|2G|4G|6G|8G)' \
	| grep -vF 'WIKIBASE_SCHEME:-http' \
	| grep -vF 'WIKIBASE_SCHEME:-https' \
	| grep -vF '"http://${WIKIBASE_HOST}"' \
	| grep -vF '"https://${WIKIBASE_HOST}"' \
	| grep -vF -- '--concurrency=4' \
	| grep -vF -- '--concurrency=8' \
	| grep -vF 'QUICKSTATEMENTS_PUBLIC_URL:-https://localhost' \
	| grep -vF 'QUICKSTATEMENTS_PUBLIC_URL:-http://localhost' \
	| grep -vE '^[+-][[:space:]]+(deploy:|resources:|limits:)' \
	| { read -r LINE && { echo ""; echo "ERROR: Unexpected drift between production and staging compose files."; echo "Review the diff above and sync both files intentionally."; echo "If the change is intentional, update the allowlist in this Makefile."; echo ""; echo "$$LINE"; cat; exit 1; } || { echo "OK: no unexpected drift (only allowlisted differences)."; exit 0; }; }
