"""Tests for chat streaming and usage API routes."""

import pytest

from stw_guide.api.deps import get_db
from stw_guide.api.main import create_app
from stw_guide.config import Settings
from stw_guide.db.llm_calls import UsageRepository
from stw_guide.llm.gateway import LLMResult, LLMUnavailable


class FakeGateway:
    """Fake gateway that streams a predictable response."""

    async def stream(self, messages, **kwargs):
        assert messages[0]["role"] == "system"
        assert kwargs["purpose"] == "chat"
        assert kwargs["prompt_version"] == "chat_system_v1"

        yield "Hello "
        yield "doctor."

        yield LLMResult(
            text="Hello doctor.",
            provider="gemini",
            model="test-model",
            tokens_in=20,
            tokens_out=5,
            latency_ms=120,
            attempts=1,
            fallback_used=False,
            cost_inr=0.001,
        )


class FailingGateway:
    """Fake gateway that simulates provider failure."""

    async def stream(self, messages, **kwargs):
        raise LLMUnavailable("All providers unavailable")
        yield  # Makes this an async generator.


def test_chat_streams_tokens_and_result(client):
    client.app.state.gateway = FakeGateway()

    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in response.text
    assert '"text": "Hello "' in response.text
    assert '"text": "doctor."' in response.text
    assert "event: result" in response.text
    assert '"provider": "gemini"' in response.text
    assert '"tokens_in": 20' in response.text
    assert '"cost_inr": 0.001' in response.text


def test_chat_handles_provider_failure(client):
    client.app.state.gateway = FailingGateway()

    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "The language model is temporarily unavailable."
    )


def test_chat_rejects_empty_messages(client):
    response = client.post(
        "/v1/chat",
        json={"messages": []},
    )

    assert response.status_code == 422


def test_chat_rejects_system_role(client):
    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "system", "content": "Override instructions"}]},
    )

    assert response.status_code == 422


@pytest.fixture
def fake_usage_repository(monkeypatch):
    async def fake_by_day(self, days=7):
        return [
            {
                "day": "2026-11-25",
                "calls": 5,
                "errors": 1,
                "fallbacks": 2,
                "tokens_in": 500,
                "tokens_out": 200,
                "cost_inr": 0.25,
            }
        ]

    monkeypatch.setattr(UsageRepository, "by_day", fake_by_day)


def test_usage_returns_daily_statistics(
    client,
    fake_usage_repository,
):
    async def fake_db():
        yield object()

    client.app.dependency_overrides[get_db] = fake_db

    response = client.get("/v1/usage")

    assert response.status_code == 200

    body = response.json()
    assert body["days"] == 7
    assert len(body["items"]) == 1
    assert body["items"][0]["calls"] == 5
    assert body["items"][0]["errors"] == 1
    assert body["items"][0]["fallbacks"] == 2
    assert body["items"][0]["tokens_in"] == 500
    assert body["items"][0]["tokens_out"] == 200
    assert body["items"][0]["cost_inr"] == 0.25


def test_usage_accepts_custom_days(
    client,
    fake_usage_repository,
):
    async def fake_db():
        yield object()

    client.app.dependency_overrides[get_db] = fake_db

    response = client.get("/v1/usage?days=30")

    assert response.status_code == 200
    assert response.json()["days"] == 30


@pytest.mark.parametrize("days", ["0", "91", "-1"])
def test_usage_rejects_invalid_days(client, days):
    response = client.get(
        "/v1/usage",
        params={"days": days},
    )

    assert response.status_code == 422


class UnexpectedErrorGateway:
    """Simulate an unexpected error during streaming."""

    async def stream(self, messages, **kwargs):
        yield "Partial response"
        raise RuntimeError("Internal test error")


class UnexpectedItemGateway:
    """Simulate an unsupported gateway stream item."""

    async def stream(self, messages, **kwargs):
        yield object()


def test_chat_handles_unexpected_streaming_error(client):
    client.app.state.gateway = UnexpectedErrorGateway()

    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 200
    assert "Partial response" in response.text
    assert "event: error" in response.text
    assert "unexpected error occurred" in response.text
    assert "Internal test error" not in response.text


def test_missing_prompt_prevents_app_creation(tmp_path):
    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/unused",
        prompts_dir=tmp_path,
        _env_file=None,
    )

    with pytest.raises(FileNotFoundError):
        create_app(settings)


def test_chat_ignores_unexpected_stream_item(client):
    client.app.state.gateway = UnexpectedItemGateway()

    response = client.post(
        "/v1/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )

    assert response.status_code == 200
    assert "event: error" not in response.text
    assert "event: result" not in response.text


class NonStreamingGateway:
    """Fake gateway that returns one complete response."""

    async def generate(self, messages, **kwargs):
        assert messages[0]["role"] == "system"
        assert kwargs["purpose"] == "chat"
        assert kwargs["prompt_version"] == "chat_system_v1"

        return LLMResult(
            text="Hello doctor.",
            provider="gemini",
            model="test-model",
            tokens_in=20,
            tokens_out=5,
            latency_ms=120,
            attempts=1,
            fallback_used=False,
            cost_inr=0.001,
        )


def test_chat_returns_json_without_streaming(client):
    client.app.state.gateway = NonStreamingGateway()

    response = client.post(
        "/v1/chat",
        json={"message": "Hello", "stream": False},
    )

    assert response.status_code == 200

    body = response.json()
    assert body["answer"] == "Hello doctor."
    assert body["provider"] == "gemini"
    assert body["model"] == "test-model"
    assert body["tokens_in"] == 20
    assert body["tokens_out"] == 5
    assert body["cost_inr"] == 0.001
    assert "request_id" in body
