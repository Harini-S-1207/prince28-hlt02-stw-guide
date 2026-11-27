"""The worker process: uv run arq stw_guide.workers.main.WorkerSettings."""

import asyncio
import logging

from arq.worker import Worker

from stw_guide.config import Settings, get_settings
from stw_guide.db.ingest_jobs import IngestRepository
from stw_guide.db.llm_calls import make_recorder
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.ingest.fetch import make_client
from stw_guide.llm.doc_meta import DocMeta
from stw_guide.llm.gateway import build_gateway
from stw_guide.llm.prompts import latest, read_prompt
from stw_guide.logging_setup import configure_logging
from stw_guide.workers.ingest import Pace, ingest_document
from stw_guide.workers.queue import Queue, redis_settings

logger = logging.getLogger("stw_guide.worker")


async def startup(ctx: dict) -> None:
    """Initialize database, HTTP client, LLM gateway, and recovery."""
    settings: Settings = ctx["settings"]

    if not ctx.get("embedded"):
        configure_logging(settings.log_level)
        logging.getLogger("arq").handlers.clear()

    logging.getLogger("httpx").setLevel(logging.WARNING)

    engine = make_engine(settings)
    ctx["engine"] = engine
    ctx["sessionmaker"] = make_sessionmaker(engine)

    ctx["gateway"] = build_gateway(
        settings,
        make_recorder(ctx["sessionmaker"]),
    )

    ctx["http"] = make_client(2)
    ctx["pace"] = Pace(settings.ingest_rpm)
    ctx["extract"] = None

    if ctx["gateway"].providers:
        try:
            version = latest(settings.prompts_dir, "extract")
        except FileNotFoundError:
            logger.warning(
                "No prompts/extract_v*.md found; "
                "documents will be parsed without extraction"
            )
        else:
            prompt = read_prompt(settings.prompts_dir, version)

            ctx["extract"] = {
                "schema": DocMeta,
                "prompt": prompt,
                "version": version,
                "chars": 6000,
            }

    # PostgreSQL is the source of truth.
    # Restore unfinished items if Redis lost its queued jobs.
    async with ctx["sessionmaker"]() as session:
        item_ids = await IngestRepository(session).open_item_ids()
        queued = await Queue(ctx["redis"]).put(item_ids)

    logger.info(
        "Worker ready; %s unfinished item(s) restored to Redis",
        queued,
    )


async def shutdown(ctx: dict) -> None:
    """Close resources when the worker stops."""
    await ctx["http"].aclose()
    await ctx["engine"].dispose()


def worker_options(
    settings: Settings,
    *,
    embedded: bool = False,
) -> dict:
    """Build the ARQ worker configuration."""
    return {
        "functions": [ingest_document],
        "on_startup": startup,
        "on_shutdown": shutdown,
        "redis_settings": redis_settings(settings.redis_url),
        "ctx": {
            "settings": settings,
            "embedded": embedded,
        },
        "max_jobs": settings.ingest_concurrency,
        "job_timeout": settings.ingest_job_timeout,
        "max_tries": settings.ingest_max_tries,
        "keep_result": 0,
        "poll_delay": 1.0,
    }


async def run_embedded(settings: Settings) -> None:
    """Run a worker inside the API process."""
    worker = Worker(
        **worker_options(settings, embedded=True),
        handle_signals=False,
    )

    try:
        await worker.async_run()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Embedded worker stopped; check REDIS_URL and worker configuration"
        )
    finally:
        await worker.close()


# ARQ reads this setting when running the worker command.
WorkerSettings = worker_options(get_settings())
