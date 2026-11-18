"""Endpoints for listing and retrieving STW documents."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.api.deps import get_db
from stw_guide.db.repository import FILTER_KEY, DocumentRepository

router = APIRouter(prefix="/documents", tags=["documents"])

RESERVED = {"q", "limit", "offset"}


@router.get("")
async def list_documents(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """List documents with optional search and metadata filters."""
    filters = {
        key: value for key, value in request.query_params.items() if key not in RESERVED
    }

    bad = [key for key in filters if not FILTER_KEY.match(key)]

    if bad:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filter name: {bad[0]}",
        )

    repo = DocumentRepository(session)

    total, items = await repo.list(
        q=q,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": filters,
        "items": items,
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Retrieve a document by its external ID."""
    repo = DocumentRepository(session)
    record = await repo.get(doc_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{doc_id}'.",
        )

    return record
