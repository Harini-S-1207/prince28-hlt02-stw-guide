import pytest
from pydantic import ValidationError

from stw_guide.config import Settings, get_settings


def test_health_is_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "dev"


def test_git_sha_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "3f2c1ab")

    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost/db",
        _env_file=None,
    )

    assert settings.git_sha == "3f2c1ab"


def test_ready_when_database_is_available(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["database"] is True


def test_ready_is_503_when_database_fails(client):
    client.app.state.test_engine.fail = True

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["database"] is False


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["id"] == "002"


def test_get_document_found(client):
    response = client.get("/v1/documents/001")

    assert response.status_code == 200
    assert response.json()["id"] == "001"
    assert response.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    response = client.get("/v1/documents/999")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Not Found"
    assert "request_id" in response.json()


def test_bad_limit_is_422_problem(client):
    response = client.get("/v1/documents", params={"limit": 0})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_request_id_is_echoed(client):
    request_id = "test-request-123"

    response = client.get(
        "/health",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_settings_requires_app_env():
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_list_documents_default_limit(client):
    response = client.get("/v1/documents")
    body = response.json()

    assert response.status_code == 200
    assert body["limit"] == 20
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_search_by_external_id(client):
    response = client.get("/v1/documents", params={"q": "002"})

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["id"] == "002"


def test_search_with_no_matches(client):
    response = client.get(
        "/v1/documents",
        params={"q": "nonexistent"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    assert response.json()["items"] == []


def test_maximum_limit_is_accepted(client):
    response = client.get("/v1/documents", params={"limit": 100})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_limit_above_maximum_is_422(client):
    response = client.get("/v1/documents", params={"limit": 101})

    assert response.status_code == 422


def test_document_response_includes_metadata(client):
    response = client.get("/v1/documents/001")

    assert response.status_code == 200
    assert response.json()["metadata"]["id"] == "001"


def test_get_settings_is_cached(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/db")

    get_settings.cache_clear()

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.app_env == "ci"

    get_settings.cache_clear()
