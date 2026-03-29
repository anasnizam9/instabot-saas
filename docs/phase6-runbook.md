# Phase 6 Runbook

## 1) Goal

Phase 6 adds deployment automation and production safety checks.

## 2) Workflows

- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-production.yml`

Optional container release:
- `.github/workflows/release-container.yml`

## 3) Required GitHub Secrets

### Staging

- `STAGING_DEPLOY_COMMAND`
- `STAGING_HEALTHCHECK_URL`

### Production

- `PRODUCTION_DEPLOY_COMMAND`
- `PRODUCTION_HEALTHCHECK_URL`

## 4) Runtime Safety Rules

When `APP_ENV=production`, the app blocks startup if:
- `SECRET_KEY` is default
- `ENCRYPTION_KEY` is default or shorter than 32 chars
- `AUTO_CREATE_TABLES=true`
- `INSTAGRAM_WEBHOOK_VERIFY_TOKEN` is empty

## 5) Deployment Steps

1. Merge to `develop` to trigger staging deploy, or run workflow manually.
2. Confirm health check passes.
3. Trigger production workflow manually.
4. Confirm production health check passes.

## 6) Non-Docker Deployment

1. Ensure required env vars are set:
	- `APP_ENV=production`
	- `AUTO_CREATE_TABLES=false`
	- `SECRET_KEY`
	- `ENCRYPTION_KEY`
	- `INSTAGRAM_WEBHOOK_VERIFY_TOKEN`
2. Run startup command:
	- PowerShell: `./scripts/start-prod.ps1`
	- Linux/macOS: `./scripts/start-prod.sh`
3. Validate:
	- `curl -fsS http://127.0.0.1:8000/api/v1/health/ready`

## 7) Optional Containerized Deployment

1. Build image:
	- `docker build -t instabot-saas-api:latest .`
2. Start stack:
	- `docker compose up --build -d`
3. Validate:
	- `curl -fsS http://127.0.0.1:8000/api/v1/health/ready`
4. Stop stack:
	- `docker compose down`

## 8) Rollback

1. Re-run deploy command with previous image/build reference.
2. Verify health check endpoint.
3. If rollback includes schema reversal, use controlled Alembic downgrade procedure.
