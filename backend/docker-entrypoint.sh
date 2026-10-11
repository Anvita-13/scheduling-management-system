#!/bin/sh
# Entrypoint for the backend container: wait for the database, apply migrations, load sample data
# (once, automatically), then hand off to the real command (CMD in the Dockerfile, normally uvicorn).
set -e

echo "==> Waiting for the database to accept connections..."
python -m app.db.wait_for_db

echo "==> Applying database migrations (alembic upgrade head)..."
alembic upgrade head

if [ "${RESET_ON_START:-false}" = "true" ]; then
  echo "==> RESET_ON_START=true: wiping the database and loading a fresh sample dataset..."
  python -m app.db.seed --reset
elif [ "${SEED_ON_START:-true}" = "true" ]; then
  echo "==> Loading the sample dataset (skipped automatically if the database already has data)..."
  python -m app.db.seed || echo "==> Sample data already present — skipping seed."
fi

echo "==> Starting the application server..."
exec "$@"
