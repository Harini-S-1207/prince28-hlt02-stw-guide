"""Endpoints for listing and retrieving STW documents."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from stw_guide.api.deps import get_store
from stw_guide.store import RecordStore

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("")
async def list_documents(
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    store: Annotated[RecordStore, Depends(get_store)] = None,
):
    """List and search STW documents."""

    records = store.list_records()

    if q:
        search_text = q.lower()

        records = [
            record
            for record in records
            if search_text in " ".join(str(value) for value in record.values()).lower()
        ]

    return {
        "total": len(records),
        "items": records[:limit],
    }


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    store: Annotated[RecordStore, Depends(get_store)] = None,
):
    """Retrieve one STW document by ID."""

    document = store.get_record(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No document with id '{document_id}'.",
        )

    return document
