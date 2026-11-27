"""Tests for asynchronous ingestion API endpoints."""

from fastapi.testclient import TestClient

from stw_guide.api.deps import get_ingest_repo, get_manifest
from stw_guide.api.main import create_app
from stw_guide.config import Settings

TOKEN = {"X-Admin-Token": "test-token"}


def test_start_answers_202_and_queues_new_documents(client, queue, ingest_repo):
    response = client.post("/v1/ingest", json={"limit": 10}, headers=TOKEN)

    assert response.status_code == 202
    body = response.json()
    assert body == {
        "job_id": "job1",
        "queued": 2,
        "status_url": "/v1/ingest/job1",
    }
    assert queue.items == [1, 2]

    urls = [record["url"] for record in ingest_repo.jobs["job1"]]
    assert urls == ["https://x.test/1.pdf", "https://x.test/2.pdf"]


def test_start_needs_admin_token(client, queue):
    assert client.post("/v1/ingest", json={}).status_code == 401

    wrong = client.post(
        "/v1/ingest",
        json={},
        headers={"X-Admin-Token": "guess"},
    )
    assert wrong.status_code == 401
    assert queue.items == []


def test_ingestion_without_token_is_closed_in_production():
    settings = Settings(
        app_env="production",
        database_url="postgresql://localhost:5432/unused",
        _env_file=None,
    )

    with TestClient(create_app(settings)) as public:
        response = public.post("/v1/ingest", json={})
        assert response.status_code == 403


def test_nothing_new_returns_200(client, queue, ingest_repo):
    ingest_repo.known |= {"f-" + "1" * 20, "f-" + "2" * 20}

    response = client.post("/v1/ingest", json={}, headers=TOKEN)

    assert response.status_code == 200
    assert response.json()["queued"] == 0
    assert queue.items == []


def test_limit_source_and_validation(client, queue):
    response = client.post(
        "/v1/ingest",
        json={"limit": 1},
        headers=TOKEN,
    )
    assert response.status_code == 202
    assert response.json()["queued"] == 1

    response = client.post(
        "/v1/ingest",
        json={"source": "somewhere-else"},
        headers=TOKEN,
    )
    assert response.status_code == 200
    assert response.json()["queued"] == 0

    invalid = client.post(
        "/v1/ingest",
        json={"limit": 0},
        headers=TOKEN,
    )
    assert invalid.status_code == 422


def test_retry_failed_queues_dead_letter_records(client, queue, ingest_repo):
    response = client.post(
        "/v1/ingest",
        json={"retry_failed": True},
        headers=TOKEN,
    )

    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert ingest_repo.jobs["job1"][0]["url"] == "https://x.test/bad.pdf"
    assert queue.items == [1]


def test_progress_and_unknown_job(client):
    response = client.post("/v1/ingest", json={}, headers=TOKEN)
    job_id = response.json()["job_id"]

    progress = client.get(f"/v1/ingest/{job_id}")
    assert progress.status_code == 200
    assert progress.json()["job_id"] == job_id
    assert progress.json()["counts"]["queued"] == 2

    missing = client.get("/v1/ingest/no-such-job")
    assert missing.status_code == 404


def test_dead_letter_lists_permanently_failed_items(client):
    response = client.get("/v1/ingest/dead-letter")

    assert response.status_code == 200
    assert response.json() == {
        "count": 1,
        "items": [
            {
                "item": 7,
                "job_id": "old",
                "url": "https://x.test/bad.pdf",
                "path": "data/raw/x/bad.pdf",
                "attempts": 3,
                "error": "parse: corrupt",
            }
        ],
    }


def test_redis_unavailable_returns_503_but_health_still_works(
    settings,
    ingest_repo,
):
    settings.redis_url = "redis://127.0.0.1:1"

    app = create_app(settings)
    app.dependency_overrides[get_ingest_repo] = lambda: ingest_repo
    app.dependency_overrides[get_manifest] = lambda: [
        {
            "url": "https://x.test/9.pdf",
            "sha256": "9" * 64,
            "status": "downloaded",
            "source": "x",
        }
    ]

    with TestClient(app) as lonely:
        response = lonely.post("/v1/ingest", json={}, headers=TOKEN)
        assert response.status_code == 503
        assert "Redis" in response.json()["detail"]

        assert lonely.get("/health").status_code == 200
