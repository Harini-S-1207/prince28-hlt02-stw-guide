"""FastAPI dependencies shared across routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

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


RepoDep = Annotated[DocumentRepository, Depends(get_repo)]
