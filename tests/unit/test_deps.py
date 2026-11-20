from types import SimpleNamespace

import pytest

from stw_guide.api.deps import get_db, get_repo, get_settings
from stw_guide.db.repository import DocumentRepository


@pytest.mark.asyncio
async def test_get_db_yields_session():
    session = object()

    class FakeSessionContext:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    class FakeSessionMaker:
        def __call__(self):
            return FakeSessionContext()

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(sessionmaker=FakeSessionMaker()))
    )

    generator = get_db(request)
    yielded_session = await anext(generator)

    assert yielded_session is session

    await generator.aclose()


def test_get_repo_returns_document_repository():
    session = object()

    repo = get_repo(session)

    assert isinstance(repo, DocumentRepository)
    assert repo.session is session


def test_get_settings_returns_app_settings():
    settings = object()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )

    assert get_settings(request) is settings
