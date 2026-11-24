"""Audit extraction quality for documents already stored in PostgreSQL."""

import argparse
import asyncio
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from stw_guide.config import get_settings
from stw_guide.db.models import Document
from stw_guide.db.session import make_engine, make_sessionmaker
from stw_guide.ingest.parse import ParsedDoc, ParsedPage
from stw_guide.ingest.quality import evaluate_quality


async def run(limit: int = 0) -> int:
    """Evaluate stored pages and update document quality metadata."""
    engine = make_engine(get_settings())
    session_factory = make_sessionmaker(engine)

    counts = Counter()
    totals = Counter()

    try:
        async with session_factory() as session:
            statement = (
                select(Document)
                .where(Document.doc_type != "record")
                .options(selectinload(Document.pages))
                .order_by(Document.id)
            )

            if limit > 0:
                statement = statement.limit(limit)

            documents = (await session.scalars(statement)).all()

            print(f"Documents selected: {len(documents)}")

            for document in documents:
                metadata = dict(document.metadata_ or {})
                stored_pages = sorted(
                    document.pages,
                    key=lambda page: page.page_no,
                )

                parsed_pages = [
                    ParsedPage(
                        page_no=page.page_no,
                        text=page.text,
                        headings=page.headings or [],
                    )
                    for page in stored_pages
                ]

                parsed = ParsedDoc(
                    parser=metadata.get("parser", "unknown"),
                    kind=document.doc_type,
                    title=document.title,
                    pages=parsed_pages,
                )

                report = evaluate_quality(parsed)

                # Page-level table counts are not stored in the pages table.
                # Preserve the original document-level count instead.
                report.table_count = int(metadata.get("tables", 0))

                quality = {
                    "total_pages": report.total_pages,
                    "empty_pages": report.empty_pages,
                    "short_pages": report.short_pages,
                    "boilerplate_pages": report.boilerplate_pages,
                    "total_characters": report.total_characters,
                    "heading_count": report.heading_count,
                    "pages_with_headings": report.pages_with_headings,
                    "pages_with_heading_context": (report.pages_with_heading_context),
                    "heading_coverage": report.heading_coverage,
                    "table_count": report.table_count,
                    "warnings": report.warnings,
                    "status": report.status,
                }

                document.metadata_ = {
                    **metadata,
                    "quality": quality,
                }

                counts[report.status] += 1
                totals["documents"] += 1
                totals["pages"] += report.total_pages
                totals["empty_pages"] += len(report.empty_pages)
                totals["short_pages"] += len(report.short_pages)
                totals["boilerplate_pages"] += len(report.boilerplate_pages)
                totals["characters"] += report.total_characters
                totals["headings"] += report.heading_count
                totals["pages_with_headings"] += report.pages_with_headings

                if report.warnings:
                    print(
                        f"REVIEW: {document.title} | "
                        f"warnings={'; '.join(report.warnings)}"
                    )

                for page_no in report.short_pages:
                    page = next(
                        page for page in parsed_pages if page.page_no == page_no
                    )
                    print(
                        f"  Short page {page_no}: {len(page.text.strip())} characters"
                    )

                for page_no in report.boilerplate_pages:
                    print(f"BOILERPLATE: {document.title} | page={page_no}")

            await session.commit()

        total_pages = totals["pages"]
        heading_coverage = (
            totals["pages_with_headings"] / total_pages * 100 if total_pages else 0.0
        )

        print("\n========== CORPUS QUALITY AUDIT ==========")
        print(f"Documents audited: {totals['documents']}")
        print(f"Passed: {counts['passed']}")
        print(f"Needs review: {counts['review']}")
        print(f"Total pages: {total_pages}")
        print(f"Empty pages: {totals['empty_pages']}")
        print(f"Short pages: {totals['short_pages']}")
        print(f"Boilerplate pages: {totals['boilerplate_pages']}")
        print(f"Total characters: {totals['characters']}")
        print(f"Explicit headings: {totals['headings']}")
        print(f"Heading coverage: {heading_coverage:.2f}%")
        print("==========================================")

        return 0

    finally:
        await engine.dispose()


def main() -> int:
    """Parse command-line arguments and run the audit."""
    parser = argparse.ArgumentParser(
        description="Audit quality of documents already stored in PostgreSQL."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of documents to audit (0 means all).",
    )

    args = parser.parse_args()

    if args.limit < 0:
        parser.error("--limit cannot be negative")

    return asyncio.run(run(args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
