"""Show PostgreSQL query plans for JSONB metadata filtering.

Usage:
    uv run python scripts/explain.py <field> <value>
"""

import asyncio
import json
import sys

from sqlalchemy import text

from stw_guide.config import get_settings
from stw_guide.db.session import make_engine


async def main(field: str, value: str) -> None:
    engine = make_engine(get_settings())

    query = text("""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT external_id, title
        FROM documents
        WHERE metadata @> CAST(:filter AS jsonb)
    """)

    params = {"filter": json.dumps({field: value})}

    try:
        async with engine.connect() as connection:
            print(f"\nQuery plan for {field} = {value}:\n")

            result = await connection.execute(query, params)
            for row in result:
                print(row[0])

            print("\nQuery plan with sequential scans disabled:\n")
            await connection.execute(text("SET enable_seqscan = off"))

            result = await connection.execute(query, params)
            for row in result:
                print(row[0])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run python scripts/explain.py <field> <value>")
        raise SystemExit(1)

    asyncio.run(main(sys.argv[1], sys.argv[2]))
