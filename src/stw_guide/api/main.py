"""FastAPI application factory."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from stw_guide.api.errors import (
    http_exception_handler,
    validation_exception_handler,
)
from stw_guide.api.middleware import register_middleware
from stw_guide.api.routes import chat, documents, health, ingest, usage
from stw_guide.config import Settings, get_settings
from stw_guide.db.llm_calls import make_recorder
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.llm.gateway import build_gateway
from stw_guide.logging_setup import configure_logging

logger = logging.getLogger("stw_guide")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    engine = make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("starting", extra={"status": settings.app_env})
        worker = None

        try:
            if settings.worker_in_api:
                from stw_guide.workers.main import run_embedded

                worker = asyncio.create_task(run_embedded(settings))

            yield

        finally:
            if worker is not None:
                worker.cancel()
                with suppress(asyncio.CancelledError):
                    await worker

            try:
                queue = getattr(app.state, "queue", None)
                if queue is not None:
                    await queue.close()
            finally:
                await engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        lifespan=lifespan,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_sessionmaker(engine)
    app.state.system_prompt = chat.load_prompt(settings.prompts_dir)

    recorder = make_recorder(app.state.sessionmaker)
    app.state.gateway = build_gateway(settings, recorder=recorder)

    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )

    register_middleware(app)

    v1 = APIRouter(prefix="/v1")
    v1.include_router(documents.router)
    v1.include_router(chat.router)
    v1.include_router(usage.router)
    v1.include_router(ingest.router)

    app.include_router(health.router)
    app.include_router(v1)

    return app
