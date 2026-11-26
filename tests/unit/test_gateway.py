"""Unit tests for the LLM gateway foundation."""

import json
from decimal import Decimal

import httpx
import pytest

from stw_guide.llm.gateway import (
    CircuitBreaker,
    FakeLLM,
    LLMError,
    OpenAICompatProvider,
    calculate_cost_inr,
)


def test_cost_calculation():
    cost = calculate_cost_inr(
        tokens_in=1000,
        tokens_out=500,
        input_price_per_million=0.10,
        output_price_per_million=0.20,
        usd_inr=95.0,
    )
    assert cost == Decimal("0.019000")


def test_cost_calculation_with_zero_tokens():
    cost = calculate_cost_inr(
        tokens_in=0,
        tokens_out=0,
        input_price_per_million=0.10,
        output_price_per_million=0.20,
        usd_inr=95.0,
    )
    assert cost == Decimal("0.000000")


def test_circuit_breaker_starts_closed():
    breaker = CircuitBreaker()
    assert breaker.is_open is False


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=3)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open is False
    breaker.record_failure()
    assert breaker.is_open is True


def test_circuit_breaker_resets_after_success():
    breaker = CircuitBreaker(failure_threshold=2)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.is_open is True
    breaker.record_success()
    assert breaker.is_open is False
    assert breaker.failures == 0


def test_circuit_breaker_closes_after_reset_period(monkeypatch):
    breaker = CircuitBreaker(failure_threshold=1, reset_seconds=30)
    monkeypatch.setattr(
        "stw_guide.llm.gateway.time.monotonic",
        lambda: 100.0,
    )
    breaker.record_failure()
    assert breaker.is_open is True
    monkeypatch.setattr(
        "stw_guide.llm.gateway.time.monotonic",
        lambda: 131.0,
    )
    assert breaker.is_open is False


@pytest.mark.asyncio
async def test_fake_llm_records_messages_and_options():
    fake = FakeLLM()
    messages = [{"role": "user", "content": "Hello"}]
    response_format = {"type": "json_object"}

    result = await fake.generate(
        messages,
        temperature=0,
        response_format=response_format,
    )

    assert result.text == "A fake answer."
    assert fake.calls == 1
    assert fake.seen[0]["messages"] == messages
    assert fake.seen[0]["temperature"] == 0
    assert fake.seen[0]["response_format"] == response_format


@pytest.mark.asyncio
async def test_fake_llm_raises_scripted_exception():
    error = RuntimeError("simulated provider failure")
    fake = FakeLLM(script=[error])

    with pytest.raises(RuntimeError, match="simulated provider failure"):
        await fake.generate([{"role": "user", "content": "Hello"}])

    assert fake.calls == 1


def test_provider_body_includes_response_format():
    provider = OpenAICompatProvider(
        "test",
        "https://api.example.test/v1",
        "test-key",
        "test-model",
    )
    response_format = {"type": "json_object"}

    body = provider._body(
        [{"role": "user", "content": "Hello"}],
        temperature=0,
        stream=False,
        response_format=response_format,
    )

    assert body["response_format"] == response_format
    assert body["temperature"] == 0


def test_provider_body_omits_response_format_by_default():
    provider = OpenAICompatProvider(
        "test",
        "https://api.example.test/v1",
        "test-key",
        "test-model",
    )

    body = provider._body(
        [{"role": "user", "content": "Hello"}],
        temperature=0.2,
        stream=False,
    )

    assert "response_format" not in body


@pytest.mark.asyncio
async def test_provider_generate_parses_response():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Hello from provider"}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatProvider(
        "test",
        "https://api.example.test/v1",
        "test-key",
        "test-model",
        client=client,
    )

    try:
        result = await provider.generate(
            [{"role": "user", "content": "Hello"}],
            temperature=0,
            response_format={"type": "json_object"},
        )
    finally:
        await client.aclose()

    assert result.text == "Hello from provider"
    assert result.tokens_in == 10
    assert result.tokens_out == 5
    assert captured["url"] == ("https://api.example.test/v1/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["body"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_provider_generate_handles_rate_limit():
    def handler(request):
        return httpx.Response(
            429,
            json={"error": "rate limit"},
            headers={"retry-after": "2"},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatProvider(
        "test",
        "https://api.example.test/v1",
        "test-key",
        "test-model",
        client=client,
    )

    try:
        with pytest.raises(LLMError) as exc_info:
            await provider.generate([{"role": "user", "content": "Hello"}])
    finally:
        await client.aclose()

    assert exc_info.value.retryable is True
    assert exc_info.value.retry_after == 2.0
