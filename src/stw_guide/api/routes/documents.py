"""Endpoints for listing and retrieving STW documents."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.api.deps import get_db
from stw_guide.repositories.documents import DocumentRepository

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("")
async def list_documents(
    session: Annotated[AsyncSession, Depends(get_db)],
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    repository = DocumentRepository(session)
    documents = await repository.list_documents(q=q, limit=limit)

    return {
        "total": len(documents),
        "items": [
            {
                "id": d.external_id,
                "title": d.title,
                "source_url": d.source_url,
                "doc_type": d.doc_type,
            }
            for d in documents
        ],
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    repository = DocumentRepository(session)
    document = await repository.get_document(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{document_id}'.",
        )

    return {
        "id": document.external_id,
        "title": document.title,
        "source_url": document.source_url,
        "doc_type": document.doc_type,
        "metadata": document.metadata_,
    }
