"""Optional integration tests against a real PostgreSQL database."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stw_guide.db.models import Document
from stw_guide.db.repository import DocumentRepository

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


def run_integration_test(check):
    async def run():
        engine = create_async_engine(TEST_DATABASE_URL)
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        external_id = f"integration-{uuid4()}"
        document = Document(
            external_id=external_id,
            title="Integration test guideline",
            sha256=uuid4().hex,
            metadata_={"condition": "integration-test"},
        )

        try:
            async with session_factory() as session:
                session.add(document)
                await session.commit()

                repo = DocumentRepository(session)
                await check(repo, external_id)

        finally:
            async with session_factory() as session:
                await session.execute(
                    Document.__table__.delete().where(
                        Document.external_id == external_id
                    )
                )
                await session.commit()

            await engine.dispose()

    asyncio.run(run())


def test_postgres_get_document():
    async def check(repo, external_id):
        result = await repo.get(external_id)
        assert result is not None
        assert result["id"] == external_id
        assert result["title"] == "Integration test guideline"

    run_integration_test(check)


def test_postgres_list_documents():
    async def check(repo, external_id):
        total, items = await repo.list(
            q="Integration test guideline",
            filters={},
            limit=100,
            offset=0,
        )

        assert total >= 1
        assert any(item["id"] == external_id for item in items)

    run_integration_test(check)


def test_postgres_jsonb_metadata_filter():
    async def check(repo, external_id):
        total, items = await repo.list(
            q=None,
            filters={"condition": "integration-test"},
            limit=100,
            offset=0,
        )

        assert total >= 1
        assert any(item["id"] == external_id for item in items)

    run_integration_test(check)
