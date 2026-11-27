"""One job = one document: get the file, parse it, extract its record, store everything."""

import asyncio
import hashlib
import logging
import re
import tempfile
import time
from pathlib import Path

import httpx
from arq import Retry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.db.models import Document, IngestItem
from stw_guide.ingest.fetch import (
    RETRYABLE,
    HostGate,
    Robots,
    Source,
    fetch_one,
)
from stw_guide.ingest.parse import ParseError, parse_file
from stw_guide.ingest.store import document_id, save_document, save_failure
from stw_guide.llm.extract import document_text, extract, save

logger = logging.getLogger("stw_guide.worker")
GITHUB_BLOB = re.compile(r"^https://github\.com/([^/]+/[^/]+)/blob/[^/]+/(.+)$")


class Permanent(Exception):
    """An error that will not be fixed by retrying."""


def plan(
    records: list[dict],
    done_ids: set[str],
    *,
    source: str = "",
    limit: int = 0,
) -> list[dict]:
    """Select downloaded records that are not already in the database."""
    todo = []
    seen = set(done_ids)

    for record in records:
        if record.get("status") != "downloaded" or (
            source and record.get("source") != source
        ):
            continue

        doc_id = document_id(record["sha256"])

        if doc_id in seen:
            continue

        seen.add(doc_id)
        todo.append(record)

    return todo[:limit] if limit else todo


def raw_url(record: dict) -> str:
    """Convert a GitHub blob URL into a pinned raw-content URL."""
    match = GITHUB_BLOB.match(record["url"])

    if record.get("via") == "git" and match and record.get("commit"):
        return (
            f"https://raw.githubusercontent.com/"
            f"{match[1]}/{record['commit']}/{match[2]}"
        )

    return record["url"]


def sha256_of(path: Path) -> str:
    """Calculate a file's SHA-256 hash."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


class Pace:
    """Limit model calls per minute across this worker."""

    def __init__(
        self,
        per_minute: float,
        clock=time.monotonic,
        sleep=asyncio.sleep,
    ) -> None:
        if per_minute <= 0:
            raise ValueError("per_minute must be greater than zero")

        self._gap = 60 / per_minute
        self._clock = clock
        self._sleep = sleep
        self._next = 0.0

    async def wait(self) -> None:
        now = self._clock()
        delay = max(0.0, self._next - now)
        self._next = max(now, self._next) + self._gap

        if delay:
            await self._sleep(delay)


async def get_file(
    record: dict,
    folder: Path,
    client: httpx.AsyncClient,
    sleep=asyncio.sleep,
) -> Path:
    """Use the local file if available; otherwise download it."""
    path = Path(record["path"])

    if path.is_file():
        return path

    if record.get("via") == "manual":
        raise Permanent("Downloaded manually: the file is unavailable on this machine")

    source = Source(
        raw_url(record),
        record["source"],
        record.get("licence") or "unknown",
    )

    result = await fetch_one(
        client,
        source,
        root=folder,
        raw_dir=folder / "raw",
        robots=Robots(client),
        gate=HostGate(0.5, sleep),
        slots=asyncio.Semaphore(1),
        max_attempts=2,
        sleep=sleep,
    )

    if result["status"] == "downloaded":
        return folder / result["path"]

    problem = f"download {result['status']}: {result.get('error', '')}"

    if result["status"] == "blocked" or result.get("http_status") not in {
        None,
        *RETRYABLE,
    }:
        raise Permanent(problem)

    raise RuntimeError(problem)


async def process(
    ctx: dict,
    session: AsyncSession,
    item: IngestItem,
) -> tuple[str, int]:
    """Process one item and return its final status and page count."""
    record = dict(item.record)

    with tempfile.TemporaryDirectory() as folder:
        path = await get_file(
            record,
            Path(folder),
            ctx["http"],
        )

        record["sha256"] = await asyncio.to_thread(
            sha256_of,
            path,
        )

        doc_id = document_id(record["sha256"])

        document = await session.scalar(
            select(Document).where(Document.external_id == doc_id)
        )

        status = "skipped"

        if document is None:
            try:
                parsed = await asyncio.to_thread(parse_file, path)
            except ParseError as error:
                await save_failure(session, record, error)
                raise Permanent(f"parse: {error.reason}") from error

            await save_document(session, record, parsed)

            document = await session.scalar(
                select(Document).where(Document.external_id == doc_id)
            )

            status = "done"

    pages = int(document.metadata_.get("pages", 0))

    task = ctx.get("extract")
    note = document.metadata_.get("extract") or {}

    if task and (note.get("prompt") != task["version"] or "error" in note):
        await ctx["pace"].wait()

        text = await document_text(
            session,
            document,
            task["chars"],
        )

        result = await extract(
            ctx["gateway"],
            task["schema"],
            task["prompt"],
            task["version"],
            document.title,
            text,
        )

        await save(
            session,
            document,
            result,
            task["version"],
        )

        if result.record is None:
            raise Permanent(f"extract: {result.errors[-1][:200]}")

        status = "done"

    return status, pages


async def ingest_document(ctx: dict, item_id: int) -> str:
    """ARQ job function: process one document with persistent retry tracking."""
    max_tries = ctx["settings"].ingest_max_tries

    async with ctx["sessionmaker"]() as session:
        item = await session.get(IngestItem, item_id)

        if item is None or item.status not in ("queued", "running"):
            return "ignored"

        if item.attempts >= max_tries:
            item.status = "failed"
            item.error = f"gave up: started {item.attempts} times and never finished"
            await session.commit()
            return "failed"

        item.status = "running"
        item.attempts += 1
        attempt = item.attempts

        await session.commit()

        try:
            item.status, item.pages = await process(
                ctx,
                session,
                item,
            )
            item.error = ""

        except Permanent as error:
            await session.rollback()
            item = await session.get(IngestItem, item_id)

            if item is None:
                return "ignored"

            item.status = "failed"
            item.error = str(error)[:500]

        except Exception as error:
            await session.rollback()
            item = await session.get(IngestItem, item_id)

            if item is None:
                return "ignored"

            reason = f"{type(error).__name__}: {error}"[:500]

            if attempt >= max_tries:
                item.status = "failed"
                item.error = f"gave up after {attempt} tries: {reason}"
            else:
                item.status = "queued"
                item.error = f"try {attempt} failed: {reason}"

                await session.commit()

                logger.warning(
                    "item %s will be retried: %s",
                    item_id,
                    reason,
                )

                raise Retry(defer=attempt * 30) from error

        await session.commit()

        logger.info("item %s %s", item_id, item.status)

        return item.status
