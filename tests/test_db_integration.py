"""Integration tests using a real PostgreSQL database."""

import os

import pytest
from fastapi.testclient import TestClient

from stw_guide.api.main import create_app
from stw_guide.config import Settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


@pytest.fixture(scope="module")
def integration_client():
    settings = Settings(
        app_env="ci",
        database_url=TEST_DATABASE_URL,
    )

    with TestClient(create_app(settings)) as client:
        yield client


def test_database_connection(integration_client):
    response = integration_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] is True


def test_list_documents_from_postgres(integration_client):
    response = integration_client.get("/v1/documents")

    assert response.status_code == 200
    assert response.json()["total"] > 0


def test_get_document_from_postgres(integration_client):
    response = integration_client.get("/v1/documents/icmr-stw-001")

    assert response.status_code == 200
    assert response.json()["id"] == "icmr-stw-001"
