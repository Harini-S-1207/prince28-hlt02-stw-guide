from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from stw_guide.api.middleware import register_middleware


def test_generates_request_id_when_missing(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert float(response.headers["X-Process-Time-Ms"]) >= 0


def test_handles_unexpected_exception(monkeypatch):
    app = FastAPI()
    register_middleware(app)

    mock_exception = Mock()
    monkeypatch.setattr(
        "stw_guide.api.middleware.logger.exception",
        mock_exception,
    )

    @app.get("/fail")
    async def fail():
        raise RuntimeError("Unexpected test error")

    with TestClient(app) as client:
        response = client.get("/fail")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Internal Server Error"
    assert response.json()["detail"] == "An unexpected error occurred."
    assert response.json()["request_id"] == response.headers["X-Request-ID"]

    mock_exception.assert_called_once()
    assert mock_exception.call_args.args[0] == "unhandled request error"
