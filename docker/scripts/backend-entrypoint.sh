#!/bin/bash
# Backend entrypoint — runs migrations before starting the application.
# Used as ENTRYPOINT in Dockerfile.backend.

set -e

echo "Running database migrations..."
uv run alembic upgrade head

echo "Starting application..."
exec "$@"
