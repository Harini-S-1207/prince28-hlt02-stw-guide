"""Database operations for STW documents."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.db.models import Document


class DocumentRepository:
    """Read documents from PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_documents(
        self, q: str | None = None, limit: int = 20
    ) -> list[Document]:
        statement = select(Document).order_by(Document.id)

        if q:
            search = f"%{q}%"
            statement = statement.where(
                Document.title.ilike(search) | Document.external_id.ilike(search)
            )

        result = await self.session.execute(statement.limit(limit))
        return list(result.scalars().all())

    async def get_document(self, document_id: str) -> Document | None:
        statement = select(Document).where(Document.external_id == document_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
