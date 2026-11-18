"""Show PostgreSQL query execution plan for JSONB filtering."""

import asyncio

from sqlalchemy import text

from stw_guide.config import get_settings
from stw_guide.db.session import make_engine


async def main():
    engine = make_engine(get_settings())

    query = text("""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT external_id, title
        FROM documents
        WHERE metadata @> CAST(:filter AS jsonb)
    """)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                query,
                {"filter": '{"specialty": "Cardiology"}'},
            )

            print("Query plan for specialty = Cardiology:\n")

            for row in result:
                print(row[0])
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
