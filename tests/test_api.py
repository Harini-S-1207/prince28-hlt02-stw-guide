"""Tests for the STW Guide API."""

import pytest
from fastapi.testclient import TestClient

from stw_guide.api.main import create_app
from stw_guide.config import Settings


@pytest.fixture
def client(tmp_path):
    """Create a test client with temporary sample data."""

    data_file = tmp_path / "records.json"
    data_file.write_text(
        """
        [
            {
                "id": "001",
                "condition": "Test condition",
                "specialty": "General Medicine"
            }
        ]
        """,
        encoding="utf-8",
    )

    settings = Settings(
        app_name="stw_guide_test",
        app_env="ci",
        log_level="ERROR",
        data_file=data_file,
    )

    app = create_app(settings)

    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_documents(client):
    response = client.get("/v1/documents")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_document(client):
    response = client.get("/v1/documents/001")
    assert response.status_code == 200
    assert response.json()["id"] == "001"


def test_document_not_found(client):
    response = client.get("/v1/documents/999")
    assert response.status_code == 404


def test_invalid_limit(client):
    response = client.get("/v1/documents?limit=0")
    assert response.status_code == 422
