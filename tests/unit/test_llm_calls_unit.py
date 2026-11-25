"""Unit tests for LLM call recording and usage aggregation."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from stw_guide.db.llm_calls import (
    UsageRepository,
    make_recorder,
    record_llm_call,
)


@pytest.mark.asyncio
async def test_make_recorder_inserts_and_commits():
    session = MagicMock()
    session.commit = AsyncMock()

    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=session)
    manager.__aexit__ = AsyncMock(return_value=False)

    sessionmaker = MagicMock(return_value=manager)
    recorder = make_recorder(sessionmaker)

    row = {
        "request_id": "unit-001",
        "provider": "groq",
        "model": "test-model",
        "status": "ok",
        "tokens_in": 100,
        "tokens_out": 50,
    }

    await recorder(row)

    sessionmaker.assert_called_once()
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_make_recorder_propagates_commit_error():
    session = MagicMock()
    session.commit = AsyncMock(side_effect=RuntimeError("database error"))

    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=session)
    manager.__aexit__ = AsyncMock(return_value=False)

    recorder = make_recorder(MagicMock(return_value=manager))

    with pytest.raises(RuntimeError, match="database error"):
        await recorder(
            {
                "request_id": "unit-002",
                "provider": "groq",
                "model": "test-model",
                "status": "ok",
            }
        )


@pytest.mark.asyncio
async def test_record_llm_call_flushes_and_returns_record():
    session = MagicMock()
    session.flush = AsyncMock()

    call = await record_llm_call(
        session,
        request_id="unit-003",
        provider="gemini",
        model="test-model",
        status="ok",
    )

    session.add.assert_called_once_with(call)
    session.flush.assert_awaited_once()
    assert call.request_id == "unit-003"
    assert call.purpose == "chat"
    assert call.prompt_version == ""
    assert call.tokens_in == 0
    assert call.tokens_out == 0
    assert call.fallback_used is False


@pytest.mark.asyncio
async def test_record_llm_call_rejects_negative_latency():
    session = MagicMock()

    with pytest.raises(ValueError, match="cannot be negative"):
        await record_llm_call(
            session,
            request_id="unit-004",
            provider="groq",
            model="test-model",
            status="ok",
            latency_ms=-1,
        )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_usage_repository_returns_daily_totals():
    session = MagicMock()

    row = SimpleNamespace(
        day=datetime(2026, 11, 25, tzinfo=UTC),
        calls=5,
        errors=1,
        fallbacks=2,
        tokens_in=1000,
        tokens_out=500,
        cost_inr=Decimal("1.234567"),
    )

    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter([row]))
    session.execute = AsyncMock(return_value=result)

    repository = UsageRepository(session)
    usage = await repository.by_day(days=7)

    assert usage == [
        {
            "day": "2026-11-25",
            "calls": 5,
            "errors": 1,
            "fallbacks": 2,
            "tokens_in": 1000,
            "tokens_out": 500,
            "cost_inr": 1.2346,
        }
    ]

    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_repository_handles_empty_results():
    session = MagicMock()

    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter([]))
    session.execute = AsyncMock(return_value=result)

    repository = UsageRepository(session)

    assert await repository.by_day(days=7) == []


@pytest.mark.asyncio
async def test_usage_repository_handles_null_aggregates():
    session = MagicMock()

    row = SimpleNamespace(
        day=datetime(2026, 11, 25, tzinfo=UTC),
        calls=1,
        errors=None,
        fallbacks=None,
        tokens_in=None,
        tokens_out=None,
        cost_inr=None,
    )

    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter([row]))
    session.execute = AsyncMock(return_value=result)

    repository = UsageRepository(session)
    usage = await repository.by_day()

    assert usage[0]["errors"] == 0
    assert usage[0]["fallbacks"] == 0
    assert usage[0]["tokens_in"] == 0
    assert usage[0]["tokens_out"] == 0
    assert usage[0]["cost_inr"] == 0.0


@pytest.mark.asyncio
async def test_usage_repository_rejects_zero_days():
    repository = UsageRepository(MagicMock())

    with pytest.raises(ValueError, match="at least 1"):
        await repository.by_day(days=0)


@pytest.mark.asyncio
async def test_usage_repository_rejects_negative_days():
    repository = UsageRepository(MagicMock())

    with pytest.raises(ValueError, match="at least 1"):
        await repository.by_day(days=-1)
