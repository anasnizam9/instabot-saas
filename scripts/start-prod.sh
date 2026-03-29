#!/usr/bin/env sh
set -eu

: "${APP_ENV:=production}"
: "${AUTO_CREATE_TABLES:=false}"
: "${PORT:=8000}"

export APP_ENV
export AUTO_CREATE_TABLES

python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
