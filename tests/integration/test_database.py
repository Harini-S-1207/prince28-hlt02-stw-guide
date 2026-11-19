import asyncio
import hashlib
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from stw_guide.api.main import create_app
from stw_guide.config import Settings
from stw_guide.db.models import Document
from stw_guide.db.repository import DocumentRepository
from stw_guide.db.session import make_engine, make_sessionmaker

ROWS = [
    {
        "id": "integration-001",
        "condition": "Alpha guideline",
        "source": {},
        "kind": "circular",
        "year": 2024,
        "tags": ["a", "b"],
    },
    {
        "id": "integration-002",
        "condition": "Beta guideline",
        "source": {},
        "kind": "guideline",
        "year": 2025,
        "tags": ["b"],
    },
    {
        "id": "integration-003",
        "condition": "Gamma guideline",
        "source": {},
        "kind": "circular",
        "year": 2025,
        "tags": [],
    },
]


@pytest.fixture
async def seeded(database_url):
    settings = Settings(
        app_env="ci",
        database_url=database_url,
    )
    engine = make_engine(settings)
    session_factory = make_sessionmaker(engine)

    try:
        async with session_factory() as session:
            await session.execute(text("DELETE FROM pages"))
            await session.execute(text("DELETE FROM documents"))

            for row in ROWS:
                content = json.dumps(row, sort_keys=True)
                session.add(
                    Document(
                        external_id=row["id"],
                        title=row["condition"],
                        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        metadata_=row,
                    )
                )

            await session.commit()

        yield settings

    finally:
        await engine.dispose()


def test_migrations_create_required_tables(database_url):
    async def check():
        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
                tables = set(result.scalars().all())

                assert {"documents", "pages", "alembic_version"} <= tables
        finally:
            await engine.dispose()

    asyncio.run(check())


@pytest.mark.parametrize(
    ("filters", "expected_ids"),
    [
        ({"kind": "circular"}, {"integration-001", "integration-003"}),
        ({"year": "2025"}, {"integration-002", "integration-003"}),
        ({"tags": "b"}, {"integration-001", "integration-002"}),
        (
            {"kind": "circular", "year": "2025"},
            {"integration-003"},
        ),
    ],
)
async def test_repository_metadata_filters(seeded, filters, expected_ids):
    engine = make_engine(seeded)
    session_factory = make_sessionmaker(engine)

    try:
        async with session_factory() as session:
            repository = DocumentRepository(session)
            total, items = await repository.list(
                filters=filters,
                limit=100,
            )

            actual_ids = {item["id"] for item in items}

            assert total == len(expected_ids)
            assert actual_ids == expected_ids
    finally:
        await engine.dispose()


def test_api_against_real_database(seeded):
    app = create_app(seeded)

    with TestClient(app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["checks"]["database"] is True

        response = client.get("/v1/documents/integration-001")
        assert response.status_code == 200
        assert response.json()["title"] == "Alpha guideline"

        search = client.get(
            "/v1/documents",
            params={"q": "Beta guideline"},
        )
        assert search.status_code == 200
        assert search.json()["total"] == 1


def test_loader_is_idempotent(database_url, tmp_path):
    loader_rows = [{**row, "id": f"loader-{row['id']}"} for row in ROWS]

    data_file = tmp_path / "records.json"
    data_file.write_text(
        json.dumps(loader_rows),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["APP_ENV"] = "ci"
    env["DATABASE_URL"] = database_url
    env["DATA_FILE"] = str(data_file)

    result = subprocess.run(
        [sys.executable, "scripts/load_db.py"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Inserted: 3" in result.stdout

    second = subprocess.run(
        [sys.executable, "scripts/load_db.py"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Unchanged: 3" in second.stdout
