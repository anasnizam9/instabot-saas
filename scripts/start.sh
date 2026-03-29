#!/usr/bin/env sh
set -eu

echo "[phase6] Running migrations..."
alembic upgrade head

echo "[phase6] Starting API..."
uvicorn app.main:app --host 0.0.0.0 --port 8000
