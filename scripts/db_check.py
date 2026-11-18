"""Check the Neon PostgreSQL database connection."""

import asyncio

from sqlalchemy import text

from stw_guide.config import get_settings
from stw_guide.db.session import make_engine


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings)

    try:
        async with engine.connect() as connection:
            database = await connection.scalar(text("SELECT current_database()"))
            version = await connection.scalar(text("SELECT version()"))

            print(f"Connected to database '{database}'")
            print(version)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
