"""Database operations for ingestion jobs and their items."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.db.models import Document, IngestItem, IngestJob, ParseFailure
from stw_guide.ingest.store import document_id

OPEN = ("queued", "running")


class IngestRepository:
    """Create jobs, track progress, and inspect failed ingestion items."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def known_ids(self) -> set[str]:
        """Return IDs of documents already parsed or previously failed."""
        parsed = set(
            await self.session.scalars(
                select(Document.external_id).where(Document.doc_type != "record")
            )
        )

        failed_hashes = await self.session.scalars(select(ParseFailure.sha256))
        failed = {document_id(value) for value in failed_hashes}

        return parsed | failed

    async def create(self, records: list[dict]) -> tuple[str, list[int]]:
        """Create one job and its queued items."""
        job_id = uuid.uuid4().hex

        job = IngestJob(
            id=job_id,
            requested=len(records),
            items=[IngestItem(record=record) for record in records],
        )

        self.session.add(job)
        await self.session.flush()

        item_ids = [item.id for item in job.items]

        await self.session.commit()
        return job_id, item_ids

    async def progress(self, job_id: str) -> dict | None:
        """Return status counts and progress information for one job."""
        job = await self.session.get(IngestJob, job_id)
        if job is None:
            return None

        rows = await self.session.execute(
            select(IngestItem.status, func.count())
            .where(IngestItem.job_id == job_id)
            .group_by(IngestItem.status)
        )

        counts = dict(rows.all())
        for status in ("queued", "running", "done", "skipped", "failed"):
            counts.setdefault(status, 0)

        pages = await self.session.scalar(
            select(func.coalesce(func.sum(IngestItem.pages), 0)).where(
                IngestItem.job_id == job_id
            )
        )

        updated = await self.session.scalar(
            select(func.max(IngestItem.updated_at)).where(IngestItem.job_id == job_id)
        )

        finished = not (counts["queued"] or counts["running"])
        elapsed = max(
            0,
            int((datetime.now(UTC) - job.created_at).total_seconds()),
        )

        return {
            "id": job.id,
            "status": "finished" if finished else "running",
            "requested": job.requested,
            "counts": counts,
            "pages": pages,
            "created_at": job.created_at,
            "updated_at": updated,
            "seconds": elapsed,
            "dead_letter": await self.dead_letter(job_id),
        }

    async def dead_letter(
        self,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return failed items for inspection."""
        stmt = (
            select(IngestItem)
            .where(IngestItem.status == "failed")
            .order_by(IngestItem.id)
            .limit(limit)
        )

        if job_id is not None:
            stmt = stmt.where(IngestItem.job_id == job_id)

        items = await self.session.scalars(stmt)

        return [
            {
                "item": item.id,
                "job_id": item.job_id,
                "url": item.record.get("url", ""),
                "path": item.record.get("path", ""),
                "attempts": item.attempts,
                "error": item.error,
            }
            for item in items
        ]

    async def failed_records(self) -> list[dict]:
        """Return unique records that have permanently failed."""
        records = await self.session.scalars(
            select(IngestItem.record)
            .where(IngestItem.status == "failed")
            .order_by(IngestItem.id)
        )

        unique = {}
        for record in records:
            unique[record.get("url", str(record))] = record

        return list(unique.values())

    async def open_item_ids(self) -> list[int]:
        """Return queued or running items for worker recovery."""
        return list(
            await self.session.scalars(
                select(IngestItem.id)
                .where(IngestItem.status.in_(OPEN))
                .order_by(IngestItem.id)
            )
        )
