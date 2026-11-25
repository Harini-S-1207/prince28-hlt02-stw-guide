"""Unit tests for the LLM gateway foundation."""

from decimal import Decimal

from stw_guide.llm.gateway import (
    CircuitBreaker,
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
