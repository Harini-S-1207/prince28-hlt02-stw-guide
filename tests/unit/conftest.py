from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from stw_guide.api.deps import (
    get_ingest_repo,
    get_manifest,
    get_queue,
    get_repo,
)
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


class FakeQueue:
    """Remember queued item IDs without using Redis."""

    def __init__(self):
        self.items = []

    async def put(self, item_ids):
        self.items.extend(item_ids)
        return len(item_ids)

    async def close(self):
        pass


class FakeIngestRepo:
    """Simulate ingestion job database operations."""

    def __init__(self):
        self.known = {"f-" + "a" * 20}
        self.jobs = {}
        self.failed = [
            {
                "item": 7,
                "job_id": "old",
                "url": "https://x.test/bad.pdf",
                "path": "data/raw/x/bad.pdf",
                "attempts": 3,
                "error": "parse: corrupt",
            }
        ]

    async def known_ids(self):
        return self.known

    async def create(self, records):
        job_id = f"job{len(self.jobs) + 1}"
        self.jobs[job_id] = records
        return job_id, list(range(1, len(records) + 1))

    async def progress(self, job_id):
        if job_id not in self.jobs:
            return None

        counts = {
            "queued": len(self.jobs[job_id]),
            "running": 0,
            "done": 0,
            "skipped": 0,
            "failed": 0,
        }

        return {
            "id": job_id,
            "status": "working",
            "counts": counts,
            "pages": 0,
            "seconds": 0,
            "dead_letter": [],
        }

    async def dead_letter(self, job_id=None, limit=50):
        return self.failed[:limit]

    async def failed_records(self):
        return [{"url": item["url"], "path": item["path"]} for item in self.failed]


def manifest_line(n: int, **changes):
    record = {
        "url": f"https://x.test/{n}.pdf",
        "source": "x",
        "licence": "CC BY 4.0",
        "path": f"data/raw/x/{n}.pdf",
        "sha256": str(n) * 64,
        "status": "downloaded",
    }
    return record | changes


MANIFEST = [
    manifest_line(1),
    manifest_line(2),
    manifest_line(3, sha256="a" * 64),
    manifest_line(4, status="failed"),
]


@pytest.fixture
def settings():
    return Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/unused",
        admin_token="test-token",
        _env_file=None,
    )


@pytest.fixture
def db_state():
    return SimpleNamespace(fail=False)


@pytest.fixture
def queue():
    return FakeQueue()


@pytest.fixture
def ingest_repo():
    return FakeIngestRepo()


@pytest.fixture
def client(settings, db_state, queue, ingest_repo):
    app = create_app(settings)
    app.state.engine = FakeEngine(db_state)
    app.state.test_engine = db_state

    app.dependency_overrides[get_repo] = lambda: FakeRepo(SAMPLE)
    app.dependency_overrides[get_queue] = lambda: queue
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_manifest] = lambda: MANIFEST

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
