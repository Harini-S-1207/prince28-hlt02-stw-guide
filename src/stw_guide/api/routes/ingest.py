"""API endpoints for asynchronous document ingestion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from stw_guide.api.deps import (
    IngestRepoDep,
    ManifestDep,
    QueueDep,
    require_admin,
)
from stw_guide.workers.ingest import plan

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    limit: int = Field(default=20, ge=1, le=2000)
    source: str = Field(default="", max_length=100)
    retry_failed: bool = False


@router.post("", status_code=202, dependencies=[Depends(require_admin)])
async def start(
    body: IngestRequest,
    response: Response,
    repo: IngestRepoDep,
    queue: QueueDep,
    manifest: ManifestDep,
) -> dict:
    """Queue ingestion work and return immediately."""
    if body.retry_failed:
        records = (await repo.failed_records())[: body.limit]
    else:
        known = await repo.known_ids()
        records = plan(
            manifest,
            known,
            source=body.source,
            limit=body.limit,
        )

    if not records:
        response.status_code = 200
        return {
            "job_id": None,
            "queued": 0,
            "detail": "Nothing to do: all of it is ingested.",
        }

    job_id, item_ids = await repo.create(records)

    try:
        await queue.put(item_ids)
    except (RedisError, OSError, TimeoutError):
        raise HTTPException(
            status_code=503,
            detail="The ingestion job was saved, but Redis queue submission failed. "
            "The worker recovery process can restore unfinished items.",
        ) from None

    return {
        "job_id": job_id,
        "queued": len(item_ids),
        "status_url": f"/v1/ingest/{job_id}",
    }


@router.get("/dead-letter")
async def dead_letter(
    repo: IngestRepoDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict:
    """List items that permanently failed."""
    items = await repo.dead_letter(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/{job_id}")
async def progress(
    job_id: str,
    repo: IngestRepoDep,
) -> dict:
    """Return the progress of an ingestion job."""
    found = await repo.progress(job_id)

    if found is None:
        raise HTTPException(
            status_code=404,
            detail=f"No ingest job with id {job_id!r}.",
        )

    return {
        "job_id": found["id"],
        **{key: value for key, value in found.items() if key != "id"},
    }
