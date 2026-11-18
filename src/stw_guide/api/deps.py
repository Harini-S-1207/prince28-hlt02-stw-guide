"""FastAPI dependencies shared across routes."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_db(
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """Provide a database session."""

    sessionmaker = request.app.state.sessionmaker

    async with sessionmaker() as session:
        yield session
