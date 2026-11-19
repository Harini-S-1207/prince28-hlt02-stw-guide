from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from stw_guide.api.deps import get_repo
from stw_guide.api.main import create_app
from stw_guide.config import Settings

SAMPLE = [
    {"id": "001", "title": "Alpha guideline", "year": 2023, "kind": "guideline"},
    {"id": "002", "title": "Beta circular", "year": 2024, "kind": "circular"},
    {"id": "003", "title": "Gamma notice", "year": 2025, "kind": "circular"},
]


class FakeRepo:
    """Fake repository that stores documents in memory."""

    def __init__(self, rows):
        self.rows = rows

    async def list(self, *, q, filters, limit, offset):
        rows = [
            row
            for row in self.rows
            if (not q or q.lower() in str(row).lower())
            and all(str(row.get(key)) == value for key, value in filters.items())
        ]
        return len(rows), rows[offset : offset + limit]

    async def get(self, external_id):
        row = next(
            (row for row in self.rows if row["id"] == external_id),
            None,
        )
        if row is None:
            return None
        return {**row, "metadata": row}


class FakeConnection:
    """Simulate a database connection for readiness tests."""

    def __init__(self, state):
        self.state = state

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def execute(self, statement):
        if self.state.fail:
            raise OSError("Simulated database failure")


class FakeEngine:
    """Simulate the database engine used by the readiness endpoint."""

    def __init__(self, state):
        self.state = state

    def connect(self):
        return FakeConnection(self.state)

    async def dispose(self):
        pass


@pytest.fixture
def settings():
    return Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/unused",
        _env_file=None,
    )


@pytest.fixture
def db_state():
    return SimpleNamespace(fail=False)


@pytest.fixture
def client(settings, db_state):
    app = create_app(settings)
    app.state.engine = FakeEngine(db_state)
    app.state.test_engine = db_state

    app.dependency_overrides[get_repo] = lambda: FakeRepo(SAMPLE)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
