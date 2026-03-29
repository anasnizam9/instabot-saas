# InstaBot SaaS - Phase 1 Backend

This phase includes:
- FastAPI app scaffold
- JWT auth (register, login, me, refresh, logout)
- User + Organization + Membership models
- RefreshToken persistence with rotation
- Role-based organization access dependency
- Async SQLAlchemy setup
- Health check endpoint

## 1) Setup

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

For local rapid iteration (dev mode), set in `.env`:
```
AUTO_CREATE_TABLES=true
```

For production/standard workflow, use Alembic (default `AUTO_CREATE_TABLES=false`).

## 2) Database Migrations (Alembic)

Required for standard deployments:

```powershell
alembic upgrade head
```

The first migration file:
- `alembic/versions/20260329_0001_phase1_init.py`

Create new migrations after model changes:
```powershell
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 3) Run API

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open docs: http://127.0.0.1:8000/docs

## 4) Endpoints

### Auth
- `POST /api/v1/auth/register` - Create account + org
- `POST /api/v1/auth/login` - Get tokens
- `POST /api/v1/auth/refresh` - Rotate tokens
- `POST /api/v1/auth/logout` - Revoke refresh token
- `GET /api/v1/auth/me` - Current user info

### Organizations
- `POST /api/v1/organizations` - Create org
- `GET /api/v1/organizations` - List user's orgs
- `GET /api/v1/organizations/{organization_id}` - Org detail + members
- `GET /api/v1/organizations/{organization_id}/my-role` - User's role in org
- `PATCH /api/v1/organizations/{organization_id}/members/{user_id}` - Update member role (owner only)
- `DELETE /api/v1/organizations/{organization_id}/members/{user_id}` - Remove member (owner only)

### Health
- `GET /api/v1/health` - Server status

## 5) Sample Auth Flow

```json
{
  "email": "owner@example.com",
  "full_name": "Owner Name",
  "password": "StrongPass123",
  "organization_name": "My Agency"
}
```

Use returned `access_token` as Bearer token for `/api/v1/auth/me`.

## 5) Migrations (Alembic)

```powershell
alembic upgrade head
```

The first migration file is available under:
- `alembic/versions/20260329_0001_phase1_init.py`

## 6) Tests

```powershell
pytest -q
```

## 7) Notes

- Database defaults to local SQLite (`instabot.db`) for quick start.
- `AUTO_CREATE_TABLES=true` is enabled for rapid local setup.
- For migration-only workflow, set `AUTO_CREATE_TABLES=false` and run Alembic.
- Next phase will integrate Meta Instagram OAuth.

## 8) Phase 5 Kickoff (CI/CD Baseline)

The repository now includes a GitHub Actions pipeline that runs on push and pull request:
- Install dependencies from `requirements.txt`
- Run Alembic migrations (`alembic upgrade head`)
- Run test suite (`pytest -q`)

Workflow file:
- `.github/workflows/backend-ci.yml`

Dependency update automation is also enabled with Dependabot:
- `.github/dependabot.yml`

If your default branch is not `main` or `develop`, update branch filters in the CI workflow accordingly.

## 9) Phase 5 Complete (Production Readiness Baseline)

Phase 5 now includes quality gates, security checks, and runtime health/observability improvements.

### CI Quality Gates
- Linting with `ruff`
- Formatting check with `black --check`
- Import order check with `isort --check-only`
- Migration validation with `alembic upgrade head`
- Test execution with `pytest -q`

Pipeline file:
- `.github/workflows/backend-ci.yml`

### Security Baseline
- Dependency update PR automation via Dependabot (`.github/dependabot.yml`)
- Dependency vulnerability scanning via `pip-audit` in CI (`security-scan` job)

### Runtime Observability & Health
- Request correlation header support (`X-Request-ID`, configurable via env)
- Request-level access logs with latency and request id
- Liveness endpoint: `GET /api/v1/health/live`
- Readiness endpoint: `GET /api/v1/health/ready`
  - DB connectivity check (`SELECT 1`)
  - Scheduler running state visibility

### New Environment Variables
- `LOG_LEVEL`
- `REQUEST_ID_HEADER`
- Full scheduler/publisher/webhook env vars are listed in `.env.example`

## 10) Local Validation Commands

```powershell
alembic upgrade head
pytest -q
```

Optional local quality checks:

```powershell
pip install ruff==0.13.1 black==24.10.0 isort==5.13.2
ruff check app tests
black --check app tests
isort --check-only app tests
```

## 11) Phase 6 Start (Deployment + Runtime Safety)

Phase 6 now includes deployment workflow scaffolding and production startup safeguards.

### Deployment Workflows
- `.github/workflows/deploy-staging.yml`
  - Triggers on push to `develop` and manual dispatch
  - Requires secrets: `STAGING_DEPLOY_COMMAND`, `STAGING_HEALTHCHECK_URL`
- `.github/workflows/deploy-production.yml`
  - Manual dispatch only
  - Requires secrets: `PRODUCTION_DEPLOY_COMMAND`, `PRODUCTION_HEALTHCHECK_URL`

### Production Runtime Validation
When `APP_ENV=production`, app startup will fail if:
- `SECRET_KEY` is default
- `ENCRYPTION_KEY` is default or shorter than 32 chars
- `AUTO_CREATE_TABLES=true`
- `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` is empty

Implementation files:
- `app/core/runtime_checks.py`
- `app/main.py`

### Runbook
- `docs/phase6-runbook.md`

## 12) Phase 6 Continue (Non-Docker Deployment)

### New Non-Docker Deployment Artifacts
- `scripts/start-prod.ps1`
- `scripts/start-prod.sh`
- `Procfile`
- `render.yaml`

### Local Production-like Run (PowerShell)

```powershell
$env:APP_ENV = "production"
$env:AUTO_CREATE_TABLES = "false"
$env:SECRET_KEY = "replace-with-strong-secret"
$env:ENCRYPTION_KEY = "replace-with-32-char-or-longer-key"
$env:INSTAGRAM_WEBHOOK_VERIFY_TOKEN = "replace-webhook-token"
./scripts/start-prod.ps1
```

Then verify:
- `GET http://127.0.0.1:8000/api/v1/health`
- `GET http://127.0.0.1:8000/api/v1/health/ready`

### Platform Deploy Notes
- Render can use `render.yaml` directly.
- Procfile-compatible platforms can use `Procfile`.
- Staging/production GitHub workflows remain non-docker and use deploy commands from secrets.

### Optional Container Path
- Container artifacts (`Dockerfile`, `docker-compose.yml`, `release-container.yml`) are still available if needed later.
