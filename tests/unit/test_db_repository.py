from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from stw_guide.db.repository import (
    DocumentRepository,
    _value_candidates,
    to_dict,
)


def make_document(
    *,
    external_id="DOC-001",
    metadata=None,
    published_on=None,
):
    document = MagicMock()
    document.external_id = external_id
    document.metadata_ = metadata
    document.title = "Cardiology Guide"
    document.doc_type = "STW"
    document.source_url = "https://example.com"
    document.licence = "CC-BY"
    document.published_on = published_on
    return document


def test_to_dict_with_metadata_and_published_date():
    document = make_document(
        metadata={"specialty": "cardiology"},
        published_on=date(2026, 1, 15),
    )

    result = to_dict(document)

    assert result["id"] == "DOC-001"
    assert result["metadata"] == {"specialty": "cardiology"}
    assert result["specialty"] == "cardiology"
    assert result["published_on"] == "2026-01-15"


def test_to_dict_without_metadata_or_published_date():
    document = make_document(metadata=None, published_on=None)

    result = to_dict(document)

    assert result["metadata"] == {}
    assert result["published_on"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", ["true", ["true"], True]),
        ("false", ["false", ["false"], False]),
        ("25", ["25", ["25"], 25, 25.0]),
        ("2.5", ["2.5", ["2.5"], 2.5]),
        ("cardiology", ["cardiology", ["cardiology"]]),
    ],
)
def test_value_candidates(value, expected):
    assert _value_candidates(value) == expected


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def repository(session):
    return DocumentRepository(session)


@pytest.mark.asyncio
async def test_list_without_search_or_filters(repository, session):
    documents = [make_document(), make_document(external_id="DOC-002")]

    result = MagicMock()
    result.all.return_value = documents
    session.scalars.return_value = result

    total, items = await repository.list()

    assert total == 2
    assert len(items) == 2
    session.scalars.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_with_search(repository, session):
    result = MagicMock()
    result.all.return_value = []
    session.scalars.return_value = result

    total, items = await repository.list(q="cardiology")

    assert total == 0
    assert items == []

    statement = str(session.scalars.await_args.args[0])
    assert "LIKE lower" in statement


@pytest.mark.asyncio
async def test_list_with_metadata_filter(repository, session):
    result = MagicMock()
    result.all.return_value = []
    session.scalars.return_value = result

    await repository.list(filters={"specialty": "cardiology"})

    statement = str(session.scalars.await_args.args[0])
    assert "metadata" in statement


@pytest.mark.asyncio
async def test_list_with_search_filter_and_pagination(repository, session):
    result = MagicMock()
    result.all.return_value = []
    session.scalars.return_value = result

    await repository.list(
        q="heart",
        filters={"active": "true"},
        limit=5,
        offset=10,
    )

    statement = str(session.scalars.await_args.args[0])
    assert "LIKE lower" in statement
    assert "LIMIT" in statement
    assert "OFFSET" in statement


@pytest.mark.asyncio
async def test_get_document_found(repository, session):
    document = make_document()
    session.scalar.return_value = document

    result = await repository.get("DOC-001")

    assert result["id"] == "DOC-001"
    session.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_not_found(repository, session):
    session.scalar.return_value = None

    result = await repository.get("UNKNOWN")

    assert result is None
    session.scalar.assert_awaited_once()
