#!/bin/bash
# Backend entrypoint — runs migrations before starting the application.
# Used as ENTRYPOINT in Dockerfile.backend.

set -e

echo "Running database migrations..."

# Check if the current DB revision is known to Alembic.
# If the alembic_version table has a revision that doesn't exist in the
# migration files (e.g. after rewriting the migration chain), Alembic
# will fail with "Can't locate revision". Detect that and re-stamp.
current=$(uv run alembic current 2>&1 || true)
if echo "$current" | grep -q "Can't locate revision"; then
    echo "WARNING: DB has an orphaned revision — re-stamping."
    echo "  $current"
    # Stamp to the last migration *before* head so upgrade head can
    # safely run the latest migration (006) with its idempotent DDL.
    uv run alembic stamp 005
    echo "Stamped to 005."
fi

uv run alembic upgrade head

echo "Starting application..."
# If no CMD was passed (e.g. missing 'command:' in docker-compose),
# fall back to the default uvicorn command instead of execing nothing.
if [ $# -eq 0 ]; then
    echo "WARN: No command passed to entrypoint, using default."
    exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
else
    exec "$@"
fi
