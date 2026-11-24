"""Parse downloaded corpus files and store their pages in PostgreSQL."""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

from stw_guide.config import get_settings
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.ingest.parse import ParseError, parse_file, parse_pdf_ocr
from stw_guide.ingest.store import (
    document_id,
    failed_paths,
    parsed_ids,
    save_document,
    save_failure,
)

MANIFEST = Path("data/manifest.jsonl")


def load_records() -> list[dict]:
    """Load the newest downloaded manifest record for each URL."""
    latest = {}

    with MANIFEST.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            latest[record["url"]] = record

    return [
        record
        for record in latest.values()
        if record.get("status") == "downloaded"
        and Path(record.get("path", "")).is_file()
    ]


def parse_one(path: Path, ocr_language: str):
    """Parse normally; use OCR only when a PDF has no text layer."""
    try:
        return parse_file(path)
    except ParseError as error:
        if (
            error.reason == "no_text_layer"
            and ocr_language
            and path.suffix.lower() == ".pdf"
        ):
            return parse_pdf_ocr(path, ocr_language)
        raise


async def run(args) -> int:
    records = load_records()
    settings = get_settings()
    engine = make_engine(settings)
    session_factory = make_sessionmaker(engine)

    counts = Counter()
    reasons = Counter()
    pages = 0
    started = time.perf_counter()

    try:
        async with session_factory() as session:
            existing_ids = await parsed_ids(session)
            previous_failures = await failed_paths(session)

            done = set(existing_ids)
            todo = []

            for record in records:
                doc_id = document_id(record["sha256"])

                if doc_id in done:
                    continue

                if record["path"] in previous_failures and not args.retry_failed:
                    continue

                # Avoid parsing duplicate file contents.
                done.add(doc_id)
                todo.append(record)

            selected = todo[: args.limit or None]

            print(
                f"Available files: {len(records)} | "
                f"Already parsed: {len(existing_ids)} | "
                f"To process: {len(selected)}"
            )

            for number, record in enumerate(selected, start=1):
                path = Path(record["path"])

                try:
                    parsed = await asyncio.to_thread(parse_one, path, args.ocr)
                    await save_document(session, record, parsed)

                    counts["parsed"] += 1
                    pages += len(parsed.pages)

                except ParseError as error:
                    await session.rollback()
                    await save_failure(session, record, error)
                    reasons[error.reason] += 1
                    print(f"FAILED: {path.name} — {error.reason}")

                if number % 50 == 0:
                    print(
                        f"Progress: {number}/{len(selected)} | "
                        f"Parsed: {counts['parsed']} | "
                        f"Failed: {sum(reasons.values())}"
                    )

    finally:
        await engine.dispose()

    elapsed = time.perf_counter() - started

    print("\n========== PARSE SUMMARY ==========")
    print(f"files={len(records)}")
    print(f"failed={sum(reasons.values())}")
    print(f"parsed={counts['parsed']}")
    print(f"pages={pages}")
    print(f"seconds={elapsed:.2f}")

    if reasons:
        print("\nFailure reasons:")
        for reason, count in reasons.most_common():
            print(f"  {reason}: {count}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse downloaded corpus files into PostgreSQL."
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--ocr", default="")

    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"Manifest not found: {MANIFEST}")
        return 1

    return asyncio.run(run(args))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
