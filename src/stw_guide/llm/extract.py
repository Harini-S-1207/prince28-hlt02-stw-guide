"""Structured output: validate extracted document metadata before storing it."""

import asyncio
import json
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stw_guide.db.models import Document, Page
from stw_guide.llm.gateway import LLMGateway, LLMUnavailable

# Keys already written by the parser; extraction must not overwrite them.
RESERVED = {"source", "path", "parser", "pages", "tables", "chars", "extract"}


def parse_json(reply: str) -> dict:
    """Extract a JSON object, even if the model adds fences or surrounding text."""
    start, end = reply.find("{"), reply.rfind("}")

    if start == -1 or end <= start:
        try:
            value = json.loads(reply.strip())
        except json.JSONDecodeError as exc:
            raise ValueError("the reply contains no JSON object") from exc

        if not isinstance(value, dict):
            raise TypeError("the JSON is not an object")
        return value

    value = json.loads(reply[start : end + 1])
    if not isinstance(value, dict):
        raise TypeError("the JSON is not an object")
    return value


def explain(error: Exception) -> str:
    """Return a short validation reason for the repair prompt."""
    if isinstance(error, ValidationError):
        problems = error.errors()[:6]
        return "; ".join(
            f"{'.'.join(map(str, p['loc'])) or 'object'}: {p['msg']}" for p in problems
        )
    return str(error)


@dataclass
class Extraction:
    record: BaseModel | None
    attempts: int = 0
    errors: list[str] = field(default_factory=list)
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_inr: float = 0.0


async def extract(
    gateway: LLMGateway,
    schema: type[BaseModel],
    prompt: str,
    version: str,
    title: str,
    text: str,
    *,
    max_attempts: int = 3,
    native_schema: bool = False,
) -> Extraction:
    """Ask the model for JSON and retry replies that fail validation."""
    json_schema = schema.model_json_schema()
    system = (
        f"{prompt}\n\nThe JSON object must match this JSON schema:\n"
        f"{json.dumps(json_schema)}"
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"Title: {title}\n<document>\n{text}\n</document>",
        },
    ]
    options: dict = {"temperature": 0}
    if native_schema:
        spec = {"name": schema.__name__, "schema": json_schema}
        options["response_format"] = {
            "type": "json_schema",
            "json_schema": spec,
        }

    out = Extraction(record=None)
    for attempt in range(1, max_attempts + 1):
        result = await gateway.generate(
            messages, purpose="extract", prompt_version=version, **options
        )
        out.attempts, out.model = attempt, result.model
        out.tokens_in += result.tokens_in
        out.tokens_out += result.tokens_out
        out.cost_inr += result.cost_inr

        try:
            out.record = schema.model_validate(parse_json(result.text))
            return out
        except ValueError as error:
            out.errors.append(explain(error))
            repair = (
                f"That reply was rejected: {out.errors[-1]}. "
                "Reply again with only the corrected JSON object."
            )
            messages = [
                *messages,
                {"role": "assistant", "content": result.text},
                {"role": "user", "content": repair},
            ]
    return out


async def pending(
    session: AsyncSession,
    version: str,
    *,
    limit: int = 0,
    retry_failed: bool = False,
) -> list[Document]:
    """Find documents not handled by this prompt version."""
    note = Document.metadata_["extract"]
    not_done = note["prompt"].astext.is_distinct_from(version)
    failed = note["error"].astext.is_not(None)
    stmt = select(Document).where(Document.doc_type != "record")
    stmt = stmt.where(or_(not_done, failed) if retry_failed else not_done).order_by(
        Document.id
    )
    return list(await session.scalars(stmt.limit(limit) if limit else stmt))


async def document_text(session: AsyncSession, document: Document, chars: int) -> str:
    """Read up to the first three pages, limited to control cost."""
    stmt = (
        select(Page.text)
        .where(Page.document_id == document.id)
        .order_by(Page.page_no)
        .limit(3)
    )
    return "\n\n".join(await session.scalars(stmt))[:chars]


async def save(
    session: AsyncSession,
    document: Document,
    result: Extraction,
    version: str,
) -> None:
    """Merge extracted fields into metadata without losing parser metadata."""
    note = {
        "prompt": version,
        "model": result.model,
        "attempts": result.attempts,
    }
    fields = {}
    if result.record is None:
        note["error"] = result.errors[-1][:300]
    else:
        fields = result.record.model_dump(mode="json")

    document.metadata_ = {
        **document.metadata_,
        **fields,
        "extract": note,
    }
    await session.commit()


async def run(
    sessionmaker: async_sessionmaker,
    gateway: LLMGateway,
    schema: type[BaseModel],
    prompt: str,
    version: str,
    *,
    limit: int = 0,
    rpm: float = 12,
    chars: int = 6000,
    retry_failed: bool = False,
    native: bool = False,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    echo: Callable[[str], None] = print,
) -> Counter:
    """Process pending documents at a controlled rate; safe to resume."""
    clash = RESERVED & set(schema.model_fields)
    if clash:
        raise ValueError(
            f"rename these fields, the parser already uses them: {sorted(clash)}"
        )

    counts: Counter = Counter()

    # Fetch document details using a short-lived database session.
    async with sessionmaker() as session:
        documents = await pending(
            session,
            version,
            limit=limit,
            retry_failed=retry_failed,
        )
        todo = [
            (document.id, document.external_id, document.title)
            for document in documents
        ]

    counts["pending"] = len(todo)

    for number, (document_id, external_id, title) in enumerate(todo, start=1):
        label = f"{external_id}  {title[:50]}"

        # Read document text, then close the session before calling the LLM.
        async with sessionmaker() as session:
            document = await session.get(Document, document_id)
            if document is None:
                counts["missing"] += 1
                echo(f"SKIPPED {label}: document no longer exists")
                continue

            text = await document_text(session, document, chars)

        # No database session remains open during model calls or waiting.
        for waited in (False, True):
            try:
                result = await extract(
                    gateway,
                    schema,
                    prompt,
                    version,
                    title,
                    text,
                    native_schema=native,
                )
                break
            except LLMUnavailable as error:
                if waited:
                    echo(f"stopped: no model can answer ({str(error)[:160]})")
                    counts["stopped"] = 1
                    return counts

                echo("no model can answer right now (rate limit?): waiting 60 s")
                await sleep(60)

        # Reopen a fresh session to save the extraction result.
        async with sessionmaker() as session:
            document = await session.get(Document, document_id)
            if document is None:
                counts["missing"] += 1
                echo(f"SKIPPED {label}: document disappeared before saving")
                continue

            await save(session, document, result, version)

        counts["tokens_in"] += result.tokens_in
        counts["tokens_out"] += result.tokens_out
        counts["micro_inr"] += round(result.cost_inr * 1_000_000)

        if result.record is None:
            counts["failed"] += 1
            echo(f"FAILED   {label}  {result.errors[-1][:90]}")
        else:
            counts["ok"] += 1
            if result.attempts > 1:
                counts["repaired"] += 1
                echo(f"repaired {label}  after: {result.errors[0][:90]}")

        if number % 10 == 0:
            echo(f"... {number} of {len(todo)} documents")

        if number < len(todo):
            await sleep(60 / rpm)

    return counts
