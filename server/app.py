import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.logging_config import setup_logging
from core.security import sanitize_log_message
from database import connection as database_connection
from database import init_db as init_db_module
from server.errors import register_exception_handlers
from server.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.database_initialized = False
    app.state.database_startup_error = None

    try:
        await init_db_module.init_db()
        app.state.database_initialized = True
        logger.info("Database initialized.")
    except Exception as exc:
        app.state.database_startup_error = sanitize_log_message(exc)
        logger.error(
            "Database initialization failed: %s",
            app.state.database_startup_error,
        )

    yield

    database_connection.close_database_connection()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Alerta dos Notebooks API",
        version="1.0.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
