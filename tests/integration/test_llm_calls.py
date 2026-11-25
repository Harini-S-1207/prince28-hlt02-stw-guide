"""Integration tests for LLM call persistence."""

import pytest
from sqlalchemy import select

from stw_guide.config import Settings
from stw_guide.db.llm_calls import record_llm_call
from stw_guide.db.models import LlmCall
from stw_guide.db.session import make_engine, make_sessionmaker


@pytest.fixture
async def llm_session(database_url):
    settings = Settings(
        app_env="ci",
        database_url=database_url,
    )
    engine = make_engine(settings)
    session_factory = make_sessionmaker(engine)

    try:
        async with session_factory() as session:
            yield session
            await session.rollback()
    finally:
        await engine.dispose()


async def test_record_successful_llm_call(llm_session):
    call = await record_llm_call(
        llm_session,
        request_id="test-request-001",
        provider="groq",
        model="openai/gpt-oss-20b",
        status="ok",
        purpose="chat",
        prompt_version="chat_system_v1",
        tokens_in=100,
        tokens_out=50,
        latency_ms=850,
        cost_inr=0.012345,
        fallback_used=True,
    )

    await llm_session.commit()

    result = await llm_session.execute(
        select(LlmCall).where(LlmCall.request_id == "test-request-001")
    )
    saved = result.scalar_one()

    assert saved.id == call.id
    assert saved.provider == "groq"
    assert saved.model == "openai/gpt-oss-20b"
    assert saved.status == "ok"
    assert saved.tokens_in == 100
    assert saved.tokens_out == 50
    assert saved.latency_ms == 850
    assert saved.fallback_used is True
    assert str(saved.cost_inr) == "0.012345"


async def test_record_failed_llm_call(llm_session):
    await record_llm_call(
        llm_session,
        request_id="test-request-002",
        provider="gemini",
        model="gemini-3.8-flash",
        status="error",
        error="Provider unavailable",
    )

    await llm_session.commit()

    result = await llm_session.execute(
        select(LlmCall).where(LlmCall.request_id == "test-request-002")
    )
    saved = result.scalar_one()

    assert saved.status == "error"
    assert saved.error == "Provider unavailable"
    assert saved.tokens_in == 0
    assert saved.tokens_out == 0


async def test_record_llm_call_rejects_invalid_status(llm_session):
    with pytest.raises(ValueError, match="status must be"):
        await record_llm_call(
            llm_session,
            request_id="test-request-003",
            provider="groq",
            model="test-model",
            status="pending",
        )


async def test_record_llm_call_rejects_negative_tokens(llm_session):
    with pytest.raises(ValueError, match="cannot be negative"):
        await record_llm_call(
            llm_session,
            request_id="test-request-004",
            provider="groq",
            model="test-model",
            status="ok",
            tokens_in=-1,
        )
