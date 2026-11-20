"""FastAPI dependencies shared across routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.config import Settings
from stw_guide.db.repository import DocumentRepository


async def get_db(
    request: Request,
) -> AsyncIterator[AsyncSession]:
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
            await connection.execute(text("SELECT 1"))
        return True

    except (SQLAlchemyError, OSError, TimeoutError):
        return False


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbCheckDep = Annotated[bool, Depends(check_db)]
RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
