from unittest.mock import AsyncMock, MagicMock

import pytest

from stw_guide.repositories.documents import DocumentRepository


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def repository(session):
    return DocumentRepository(session)


@pytest.mark.asyncio
async def test_list_documents_without_search(repository, session):
    documents = [MagicMock(), MagicMock()]

    result = MagicMock()
    result.scalars.return_value.all.return_value = documents
    session.execute.return_value = result

    response = await repository.list_documents()

    assert response == documents
    session.execute.assert_awaited_once()

    statement = str(session.execute.await_args.args[0])
    assert "ORDER BY documents.id" in statement


@pytest.mark.asyncio
async def test_list_documents_with_search(repository, session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    response = await repository.list_documents(q="cardiology")

    assert response == []

    statement = str(session.execute.await_args.args[0])
    assert "lower(documents.title) LIKE lower(:title_1)" in statement
    assert "lower(documents.external_id) LIKE lower(:external_id_1)" in statement


@pytest.mark.asyncio
async def test_list_documents_with_custom_limit(repository, session):
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute.return_value = result

    await repository.list_documents(limit=5)

    statement = str(session.execute.await_args.args[0])
    assert "LIMIT :param_1" in statement


@pytest.mark.asyncio
async def test_get_document_found(repository, session):
    document = MagicMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = document
    session.execute.return_value = result

    response = await repository.get_document("DOC-001")

    assert response is document
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_document_not_found(repository, session):
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    response = await repository.get_document("UNKNOWN")

    assert response is None
    session.execute.assert_awaited_once()
