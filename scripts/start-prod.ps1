$ErrorActionPreference = "Stop"

if (-not $env:APP_ENV) { $env:APP_ENV = "production" }
if (-not $env:AUTO_CREATE_TABLES) { $env:AUTO_CREATE_TABLES = "false" }
if (-not $env:PORT) { $env:PORT = "8000" }

python -m alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port $env:PORT
