"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from stw_guide.api.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from stw_guide.api.middleware import register_middleware
from stw_guide.api.routes import documents, health
from stw_guide.config import Settings, get_settings
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.logging_setup import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings)
        app.state.engine = engine
        app.state.sessionmaker = make_sessionmaker(engine)

        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="STW Guide",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    register_middleware(app)

    app.include_router(health.router)
    app.include_router(documents.router)

    return app
