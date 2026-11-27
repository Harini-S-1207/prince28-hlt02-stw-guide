"""FastAPI dependencies shared across routes."""

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.config import Settings
from stw_guide.db.ingest_jobs import IngestRepository
from stw_guide.db.repository import DocumentRepository
from stw_guide.workers.queue import Queue


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Provide a database session."""
    sessionmaker = request.app.state.sessionmaker

    async with sessionmaker() as session:
        yield session


def get_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DocumentRepository:
    """Provide the document repository."""
    return DocumentRepository(session)


def get_settings(request: Request) -> Settings:
    """Provide application settings."""
    return request.app.state.settings


async def check_db(request: Request) -> bool:
    """Check whether PostgreSQL is reachable."""
    try:
        async with request.app.state.engine.connect() as connection:
            await asyncio.wait_for(
                connection.execute(text("SELECT 1")),
                timeout=2,
            )
        return True
    except (SQLAlchemyError, OSError, TimeoutError):
        return False


async def get_ingest_repo(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IngestRepository:
    """Provide the ingestion repository."""
    return IngestRepository(session)


async def get_queue(request: Request) -> Queue:
    """Connect to Redis lazily when an ingestion request needs it."""
    state = request.app.state

    if getattr(state, "queue", None) is None:
        try:
            state.queue = await Queue.connect(state.settings.redis_url)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="The job queue (Redis) cannot be reached.",
            ) from exc

    return state.queue


def get_manifest(request: Request) -> list[dict]:
    """Read the latest manifest record for each URL."""
    path = request.app.state.settings.manifest_file

    if not path.is_file():
        return []

    latest: dict[str, dict] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if "url" in record:
            latest[record["url"]] = record

    return list(latest.values())


def require_admin(
    request: Request,
    x_admin_token: Annotated[str, Header()] = "",
) -> None:
    """Protect ingestion submission with the configured admin token."""
    settings: Settings = request.app.state.settings

    if not settings.admin_token:
        if settings.app_env == "local":
            return

        raise HTTPException(
            status_code=403,
            detail="Set ADMIN_TOKEN to allow ingestion here.",
        )

    if not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(
            status_code=401,
            detail="Missing or wrong X-Admin-Token header.",
        )


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbCheckDep = Annotated[bool, Depends(check_db)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
IngestRepoDep = Annotated[IngestRepository, Depends(get_ingest_repo)]
QueueDep = Annotated[Queue, Depends(get_queue)]
ManifestDep = Annotated[list[dict], Depends(get_manifest)]
