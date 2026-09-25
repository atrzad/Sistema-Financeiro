from fastapi import APIRouter

from app.api.v1 import health
from app.core.config import Settings


def build_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    router.include_router(health.router)
    if settings.is_local:
        from app.api.v1 import debug

        router.include_router(debug.router)
    return router
