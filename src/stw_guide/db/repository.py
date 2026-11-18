import re
from typing import Any

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.db.models import Document

FILTER_KEY = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


def to_dict(doc: Document) -> dict[str, Any]:
    """Convert a database document into the API response format."""
    metadata = doc.metadata_ or {}

    return {
        "id": doc.external_id,
        "metadata": metadata,
        **metadata,
        "title": doc.title,
        "doc_type": doc.doc_type,
        "source_url": doc.source_url,
        "licence": doc.licence,
        "published_on": (doc.published_on.isoformat() if doc.published_on else None),
    }


def _value_candidates(value: str) -> list[Any]:
    """Generate possible JSONB values for a query-string filter."""
    candidates: list[Any] = [value, [value]]
    lowered = value.lower()

    if lowered in {"true", "false"}:
        candidates.append(lowered == "true")

    try:
        candidates.append(int(value))
    except ValueError:
        pass

    try:
        candidates.append(float(value))
    except ValueError:
        pass

    return candidates


class DocumentRepository:
    """Read documents from PostgreSQL."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        q: str | None = None,
        filters: dict[str, str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, list[dict[str, Any]]]:
        """Search, filter and paginate documents."""
        stmt = select(Document)

        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Document.title.ilike(pattern),
                    cast(Document.metadata_, Text).ilike(pattern),
                )
            )

        for key, value in (filters or {}).items():
            candidates = _value_candidates(value)
            stmt = stmt.where(
                or_(
                    *[
                        Document.metadata_.contains({key: candidate})
                        for candidate in candidates
                    ]
                )
            )

        stmt = stmt.order_by(Document.external_id).limit(limit).offset(offset)

        result = await self.session.scalars(stmt)
        documents = result.all()

        items = [to_dict(doc) for doc in documents]

        return len(items), items

    async def get(self, external_id: str) -> dict[str, Any] | None:
        """Retrieve one document by its external ID."""
        stmt = select(Document).where(Document.external_id == external_id)
        result = await self.session.scalar(stmt)

        return to_dict(result) if result else None
