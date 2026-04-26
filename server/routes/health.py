import os

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from config.settings import get_settings
from database.connection import ping_database

SERVICE_NAME = "alerta-dos-notebooks-api"
DEFAULT_VERSION = "1.0.0"

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "version": os.getenv("APP_VERSION", DEFAULT_VERSION),
    }


@router.get("/ready")
async def ready_check() -> JSONResponse:
    settings_loaded = True
    version = DEFAULT_VERSION

    try:
        settings = get_settings()
        version = settings.app_version
    except ValidationError:
        settings_loaded = False

    database_ok = False
    if settings_loaded:
        try:
            database_ok = await ping_database()
        except Exception:
            database_ok = False

    ready = settings_loaded and database_ok

    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if ready else "not_ready",
            "service": SERVICE_NAME,
            "version": version,
            "checks": {
                "settings": "ok" if settings_loaded else "error",
                "database": "ok" if database_ok else "error",
            },
        },
    )
