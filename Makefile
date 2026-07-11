.PHONY: help up down build rebuild logs logs-backend logs-worker-ocr logs-worker-llm reset-db download-model migrate test-e2e status shell-backend clean restart backup-db backup-storage backup restore-db deploy deploy-status deploy-env

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
	@echo "  make download-model  Download Airavata model to Ollama"
	@echo "  make test-e2e        Run end-to-end smoke test"
	@echo "  make shell-backend   Open shell in backend container"
	@echo "  make backup-db       Create a manual database backup"
	@echo "  make backup-storage  Create a manual storage backup"
	@echo "  make backup          Backup both database and storage"
	@echo "  make restore-db      Restore database from backup (BACKUP=file.dump)"
	@echo "  make clean           Remove all containers, volumes, and images"
	@echo ""
	@echo "  Dokploy Deployment:"
	@echo "  make deploy          Push to main + trigger Dokploy deploy"
	@echo "  make deploy-status   Check Dokploy deployment status"
	@echo "  make deploy-env      Show required env vars for Dokploy"

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
	@echo "Downloading Airavata model..."
	docker compose exec ollama ollama pull airavata

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

# ── Dokploy Deployment ─────────────────────────────────────────────────────────

deploy:
	@bash scripts/dokploy-deploy.sh

deploy-status:
	@bash scripts/dokploy-deploy.sh --status

deploy-env:
	@bash scripts/dokploy-deploy.sh --env-setup
