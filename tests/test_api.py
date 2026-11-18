import pytest
from pydantic import ValidationError

from stw_guide.config import Settings


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_when_database_is_available(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True


def test_ready_is_503_when_database_fails(client):
    client.app.state.test_engine.fail = True
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})
    assert [item["id"] for item in response.json()["items"]] == ["002"]


def test_get_document_found(client):
    response = client.get("/v1/documents/001")
    assert response.status_code == 200
    assert response.json()["title"] == "Alpha guideline"


def test_missing_document_is_problem_details(client):
    response = client.get("/v1/documents/999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_bad_limit_is_422_problem(client):
    response = client.get("/v1/documents", params={"limit": 0})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "query.limit"


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_list_documents_default_limit(client):
    response = client.get("/v1/documents")
    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_search_by_external_id(client):
    response = client.get("/v1/documents", params={"q": "002"})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == ["002"]


def test_search_with_no_matches(client):
    response = client.get("/v1/documents", params={"q": "unknown"})
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_maximum_limit_is_accepted(client):
    response = client.get("/v1/documents", params={"limit": 100})
    assert response.status_code == 200


def test_limit_above_maximum_is_422(client):
    response = client.get("/v1/documents", params={"limit": 101})
    assert response.status_code == 422


def test_document_response_includes_metadata(client):
    response = client.get("/v1/documents/001")
    assert response.status_code == 200
    assert response.json()["metadata"]["id"] == "001"
