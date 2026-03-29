from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.scheduler import is_scheduler_running

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "instabot-saas-api"}


@router.get("/health/live")
async def liveness_check() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    db_ok = True
    db_error = None

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    scheduler_running = is_scheduler_running()

    payload = {
        "status": "ready" if db_ok else "not_ready",
        "checks": {
            "database": "ok" if db_ok else "error",
            "scheduler": "running" if scheduler_running else "stopped",
        },
        "scheduler_enabled": settings.scheduler_enabled,
    }
    if db_error:
        payload["database_error"] = db_error

    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content=payload,
    )
