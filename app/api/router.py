from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.organizations import router as organizations_router
from app.api.routes.instagram import router as instagram_router
from app.api.routes.posts import router as posts_router
from app.api.routes.automation import router as automation_router
from app.api.routes.analytics import router as analytics_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(instagram_router)
api_router.include_router(posts_router)
api_router.include_router(automation_router)
api_router.include_router(analytics_router)
