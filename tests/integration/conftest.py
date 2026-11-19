"""Integration tests using a real PostgreSQL database.

Creates a fresh temporary database for each test session,
runs Alembic migrations, and drops the database afterward.
"""

import asyncio
import os
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from stw_guide.config import get_settings
from stw_guide.db.url import to_asyncpg_url

BASE_URL = os.getenv("TEST_DATABASE_URL")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when PostgreSQL URL is unavailable."""
    if BASE_URL:
        return

    skip = pytest.mark.skip(reason="Set TEST_DATABASE_URL to run integration tests")

    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(skip)


async def _admin(sql: str) -> None:
    """Execute an administrative SQL command."""
    engine = create_async_engine(
        to_asyncpg_url(BASE_URL),
        isolation_level="AUTOCOMMIT",
    )

    try:
        async with engine.connect() as connection:
            await connection.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_url():
    """Create a temporary database, migrate it, and clean it up."""
    if not BASE_URL:
        pytest.skip("TEST_DATABASE_URL is not configured")

    name = f"test_{uuid.uuid4().hex[:8]}"
    patch = pytest.MonkeyPatch()
    database_created = False

    try:
        asyncio.run(_admin(f'CREATE DATABASE "{name}"'))
        database_created = True

        url = make_url(to_asyncpg_url(BASE_URL)).set(database=name)
        url_str = url.render_as_string(hide_password=False)

        try:
            patch.setenv("APP_ENV", "ci")
            patch.setenv("DATABASE_URL", url_str)
            get_settings.cache_clear()

            command.upgrade(Config("alembic.ini"), "head")

        finally:
            # Restore the original environment immediately after migration.
            get_settings.cache_clear()
            patch.undo()

        yield url_str

    finally:
        if database_created:
            asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
