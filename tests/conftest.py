import pytest
from fastapi.testclient import TestClient

from stw_guide.api import main as api_main
from stw_guide.api.deps import get_db
from stw_guide.api.main import create_app
from stw_guide.api.routes import documents as document_routes
from stw_guide.config import Settings

SAMPLE = [
    {"id": "001", "title": "Alpha guideline"},
    {"id": "002", "title": "Beta circular"},
    {"id": "003", "title": "Gamma notice"},
]


class FakeResult:
    def __init__(self, records):
        self.records = records

    def scalars(self):
        return self

    def all(self):
        return self.records

    def scalar_one_or_none(self):
        return self.records[0] if self.records else None


class FakeSession:
    async def execute(self, statement):
        return FakeResult([])


class FakeEngine:
    def __init__(self):
        self.fail = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def connect(self):
        return self

    async def execute(self, statement):
        if self.fail:
            from sqlalchemy.exc import OperationalError

            raise OperationalError("SELECT 1", {}, Exception("Database unavailable"))

    async def dispose(self):
        pass


class FakeDocument:
    def __init__(self, record):
        self.external_id = record["id"]
        self.title = record["title"]
        self.source_url = None
        self.doc_type = "record"
        self.metadata_ = record


class FakeRepository:
    def __init__(self, session):
        self.records = [FakeDocument(record) for record in SAMPLE]

    async def list_documents(self, q=None, limit=20):
        records = self.records
        if q:
            records = [
                record
                for record in records
                if q.lower() in record.title.lower()
                or q.lower() in record.external_id.lower()
            ]
        return records[:limit]

    async def get_document(self, document_id):
        return next(
            (record for record in self.records if record.external_id == document_id),
            None,
        )


@pytest.fixture
def client(monkeypatch):
    engine = FakeEngine()

    monkeypatch.setattr(api_main, "make_engine", lambda settings: engine)
    monkeypatch.setattr(document_routes, "DocumentRepository", FakeRepository)

    settings = Settings(app_env="ci")

    async def fake_db():
        yield object()

    with TestClient(create_app(settings)) as test_client:
        test_client.app.state.test_engine = engine
        test_client.app.dependency_overrides[get_db] = fake_db
        yield test_client
