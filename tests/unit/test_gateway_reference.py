# ---- 11 additional gateway tests ----
import json

import httpx
import pytest

from stw_guide.config import Settings
from stw_guide.llm.gateway import (
    CircuitBreaker,
    FakeLLM,
    LLMError,
    LLMGateway,
    LLMResult,
    LLMUnavailable,
    OpenAICompatProvider,
    Reply,
    build_gateway,
    cost_inr,
)

ASK = [{"role": "user", "content": "What is a path parameter?"}]


def busy(retry_after=None):
    return LLMError(
        "HTTP 429: slow down",
        retryable=True,
        retry_after=retry_after,
    )


def bad_key():
    return LLMError(
        "HTTP 401: invalid API key",
        retryable=False,
    )


class Harness:
    def __init__(self, *providers, **options):
        self.now = 0.0
        self.slept = []
        self.rows = []

        self.gateway = LLMGateway(
            list(providers),
            recorder=self.record,
            sleep=self.sleep,
            clock=lambda: self.now,
            **options,
        )

    async def sleep(self, seconds):
        self.slept.append(seconds)

    async def record(self, row):
        self.rows.append(row)


async def collect(stream):
    pieces = [item async for item in stream]
    return "".join(pieces[:-1]), pieces[-1]


async def test_successful_primary_does_not_call_backup():
    primary = FakeLLM("gemini", script=["Primary answer"])
    backup = FakeLLM("groq", script=["Backup answer"])
    h = Harness(primary, backup)

    result = await h.gateway.generate(ASK)

    assert result.provider == "gemini"
    assert primary.calls == 1
    assert backup.calls == 0


async def test_fallback_records_provider_attempts():
    primary = FakeLLM("gemini", script=[bad_key()])
    backup = FakeLLM("groq", script=["Backup answer"])
    h = Harness(primary, backup)

    await h.gateway.generate(ASK)

    assert len(h.rows) == 2
    assert h.rows[0]["status"] == "error"
    assert h.rows[1]["status"] == "ok"


async def test_retry_limit_prevents_unlimited_attempts():
    primary = FakeLLM("gemini", script=[busy()] * 10)
    h = Harness(primary, max_attempts=2)

    with pytest.raises(LLMUnavailable):
        await h.gateway.generate(ASK)

    assert primary.calls == 2


async def test_non_retryable_error_moves_to_fallback():
    primary = FakeLLM("gemini", script=[bad_key()])
    backup = FakeLLM("groq", script=["Backup answer"])
    h = Harness(primary, backup)

    result = await h.gateway.generate(ASK)

    assert result.provider == "groq"
    assert primary.calls == 1


async def test_success_resets_circuit_breaker():
    breaker = CircuitBreaker(threshold=2, cooldown=10)

    breaker.failure()
    breaker.success()

    assert breaker.state == "closed"
    assert breaker.failures == 0


async def test_circuit_breaker_reopens_after_half_open_failure():
    now = [0.0]
    breaker = CircuitBreaker(
        threshold=1,
        cooldown=5,
        clock=lambda: now[0],
    )

    breaker.failure()
    assert breaker.state == "open"

    now[0] = 6
    assert breaker.allow()
    assert breaker.state == "half-open"

    breaker.failure()
    assert breaker.state == "open"


async def test_stream_success_records_usage():
    h = Harness(FakeLLM("gemini", script=["Streaming answer"]))

    text, result = await collect(h.gateway.stream(ASK))

    assert "Streaming answer" in text
    assert isinstance(result, LLMResult)
    assert h.rows[0]["status"] == "ok"


async def test_stream_without_providers_raises_error():
    h = Harness()

    with pytest.raises(LLMUnavailable):
        async for _ in h.gateway.stream(ASK):
            pass


async def test_empty_user_message_list_is_handled():
    h = Harness(FakeLLM("gemini", script=["Answer"]))

    result = await h.gateway.generate([])

    assert result.text == "Answer"


async def test_unknown_model_cost_is_zero():
    assert cost_inr("unknown-model", 5000, 5000, 95.0) == 0.0


async def test_estimate_tokens_returns_nonzero_for_text():
    from stw_guide.llm.gateway import estimate_tokens

    assert estimate_tokens("This is a test sentence.") > 0


async def test_generate_returns_the_answer_with_tokens_and_cost():
    h = Harness(
        FakeLLM("gemini", "gemini-3.8-flash", ["A path parameter is part of the URL."])
    )
    result = await h.gateway.generate(ASK)

    assert result.text == "A path parameter is part of the URL."
    assert (result.provider, result.attempts, result.fallback_used) == (
        "gemini",
        1,
        False,
    )
    assert result.tokens_in == 12 and result.tokens_out == 8
    assert result.cost_inr == cost_inr("gemini-3.8-flash", 12, 8, 95.0) > 0


async def test_a_429_is_retried_after_waiting_at_least_retry_after():
    primary = FakeLLM("gemini", script=[busy(retry_after=3), "Second try worked."])
    h = Harness(primary)

    result = await h.gateway.generate(ASK)

    assert result.text == "Second try worked."
    assert result.attempts == 2
    assert primary.calls == 2
    assert h.slept[0] >= 3


async def test_falls_back_when_the_primary_keeps_failing():
    primary = FakeLLM("gemini", script=[busy(), busy()])
    backup = FakeLLM("groq", script=["Hi."])
    h = Harness(primary, backup)

    result = await h.gateway.generate(ASK)

    assert (result.provider, result.fallback_used) == ("groq", True)
    assert primary.calls == 2 and backup.calls == 1
    assert [row["status"] for row in h.rows] == ["error", "ok"]


async def test_a_wrong_api_key_is_not_retried():
    primary = FakeLLM("gemini", script=[bad_key()])
    backup = FakeLLM("groq", script=["Hi."])
    h = Harness(primary, backup)

    result = await h.gateway.generate(ASK)

    assert primary.calls == 1
    assert h.slept == []
    assert result.provider == "groq"


async def test_all_providers_down_raises_llm_unavailable():
    h = Harness(
        FakeLLM("gemini", script=[bad_key()]), FakeLLM("groq", script=[bad_key()])
    )

    with pytest.raises(LLMUnavailable, match="gemini.*groq"):
        await h.gateway.generate(ASK)


async def test_no_provider_configured_raises_llm_unavailable():
    with pytest.raises(LLMUnavailable, match="no LLM provider"):
        await Harness().gateway.generate(ASK)


async def test_the_circuit_opens_then_tests_the_provider_again_after_the_cooldown():
    primary = FakeLLM("gemini", script=[bad_key()] * 3 + ["Back again."])
    backup = FakeLLM("groq")
    h = Harness(primary, backup, breaker_threshold=3, breaker_cooldown=30)

    for _ in range(3):
        await h.gateway.generate(ASK)

    assert h.gateway.breakers["gemini"].state == "open"

    await h.gateway.generate(ASK)
    assert primary.calls == 3

    h.now += 31
    result = await h.gateway.generate(ASK)

    assert result.provider == "gemini"
    assert h.gateway.breakers["gemini"].state == "closed"


def test_circuit_breaker_states():
    now = [0.0]
    breaker = CircuitBreaker(threshold=2, cooldown=10, clock=lambda: now[0])

    breaker.failure()
    assert breaker.state == "closed" and breaker.allow()

    breaker.failure()
    assert breaker.state == "open" and not breaker.allow()

    now[0] = 11
    assert breaker.state == "half-open" and breaker.allow()

    breaker.failure()
    assert breaker.state == "open"

    now[0] = 22
    breaker.success()

    assert breaker.state == "closed"
    assert breaker.failures == 0


async def test_stream_yields_pieces_and_then_one_result():
    h = Harness(FakeLLM("gemini", script=["Declare it in the path string."]))

    text, result = await collect(h.gateway.stream(ASK, prompt_version="chat_system_v1"))

    assert text.strip() == "Declare it in the path string."
    assert isinstance(result, LLMResult)
    assert result.tokens_out == 6
    assert h.rows[0]["prompt_version"] == "chat_system_v1"
    assert h.rows[0]["status"] == "ok"


async def test_stream_falls_back_if_nothing_was_sent_yet():
    h = Harness(
        FakeLLM("gemini", script=[busy()]), FakeLLM("groq", script=["From the backup."])
    )

    text, result = await collect(h.gateway.stream(ASK))

    assert text.strip() == "From the backup."
    assert result.fallback_used


async def test_stream_does_not_switch_models_in_the_middle_of_an_answer():
    primary = FakeLLM("gemini", script=[("partial", busy())])
    backup = FakeLLM("groq")
    h = Harness(primary, backup)
    seen = []

    with pytest.raises(LLMUnavailable, match="mid-answer"):
        async for item in h.gateway.stream(ASK):
            seen.append(item)

    assert "".join(seen).strip() == "Half an answer"
    assert backup.calls == 0


async def test_a_broken_recorder_never_breaks_an_answer():
    async def broken(row):
        raise RuntimeError("database is down")

    gateway = LLMGateway([FakeLLM(script=["Still answered."])], recorder=broken)

    result = await gateway.generate(ASK)

    assert result.text == "Still answered."


def test_cost_uses_the_price_table_and_is_zero_for_unknown_models():
    assert cost_inr("gemini-3.8-flash", 1_000_000, 1_000_000, 95.0) == 427.5

    assert cost_inr("some-new-model", 1000, 1000, 95.0) == 0.0


class NoUsage(FakeLLM):
    async def generate(self, messages, *, temperature=0.2):
        return Reply("x" * 40)


async def test_missing_token_counts_are_estimated_from_the_text():
    h = Harness(NoUsage("gemini", "gemini-3.8-flash"))

    result = await h.gateway.generate([{"role": "user", "content": "y" * 400}])

    assert (result.tokens_in, result.tokens_out) == (100, 10)


def provider_with(handler):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAICompatProvider(
        "gemini", "https://llm.test/v1/", "k-123", "m-1", client=client
    )


async def test_provider_sends_an_openai_style_request_and_reads_the_reply():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)

        reply = {
            "choices": [{"message": {"role": "assistant", "content": "Hello."}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 2},
        }
        return httpx.Response(200, json=reply)

    reply = await provider_with(handler).generate(ASK)

    assert reply == Reply("Hello.", 9, 2)
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer k-123"
    assert seen["body"]["model"] == "m-1"
    assert seen["body"]["messages"] == ASK


async def test_provider_turns_http_errors_into_llm_errors():
    def handler(request):
        return httpx.Response(
            429, headers={"retry-after": "7"}, json={"error": "rate limit"}
        )

    with pytest.raises(LLMError) as error:
        await provider_with(handler).generate(ASK)

    assert error.value.retryable
    assert error.value.retry_after == 7.0

    def unauthorized(request):
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(LLMError) as error:
        await provider_with(unauthorized).generate(ASK)

    assert not error.value.retryable


async def test_provider_reads_a_server_sent_event_stream():
    def chunk(text):
        return (
            "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"
        )

    usage = {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 3}}

    body = (
        chunk("Path ")
        + chunk("parameters ")
        + chunk("rock.")
        + "data: "
        + json.dumps(usage)
        + "\n\ndata: [DONE]\n\n"
    )

    def handler(request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    counted = Reply()
    pieces = [piece async for piece in provider_with(handler).stream(ASK, counted)]

    assert "".join(pieces) == "Path parameters rock."
    assert (counted.tokens_in, counted.tokens_out) == (9, 3)


async def test_a_stream_that_stops_without_saying_done_is_an_error():
    cut_off = 'data: {"choices": [{"delta": {"content": "Half an "}}]}\n\n'

    def handler(request):
        return httpx.Response(
            200, text=cut_off, headers={"content-type": "text/event-stream"}
        )

    pieces = []

    with pytest.raises(LLMError, match="ended early"):
        async for piece in provider_with(handler).stream(ASK, Reply()):
            pieces.append(piece)

    assert pieces == ["Half an "]

    def finished(request):
        last = '{"choices": [{"delta": {"content": "Done."}, "finish_reason": "stop"}]}'
        return httpx.Response(200, text=f"data: {last}\n\n")

    assert [p async for p in provider_with(finished).stream(ASK, Reply())] == ["Done."]


async def test_a_timeout_moves_on_but_a_dropped_connection_is_worth_one_retry():
    def hangs(request):
        raise httpx.ReadTimeout("no answer in 30 s")

    def refuses(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMError) as slow:
        await provider_with(hangs).generate(ASK)

    with pytest.raises(LLMError) as dropped:
        await provider_with(refuses).generate(ASK)

    assert not slow.value.retryable
    assert "ReadTimeout" in str(slow.value)
    assert dropped.value.retryable


# ---- Additional streaming and gateway edge-case tests ----


async def test_stream_provider_rejects_http_error_response():
    def handler(request):
        return httpx.Response(
            503,
            json={"error": "service unavailable"},
        )

    with pytest.raises(LLMError) as error:
        async for _ in provider_with(handler).stream(ASK, Reply()):
            pass

    assert error.value.retryable


async def test_stream_provider_skips_empty_content_chunks():
    body = (
        'data: {"choices": [{"delta": {"content": ""}}]}\n\n'
        'data: {"choices": [{"delta": {"content": "Hello"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request):
        return httpx.Response(
            200,
            text=body,
            headers={"content-type": "text/event-stream"},
        )

    pieces = [piece async for piece in provider_with(handler).stream(ASK, Reply())]

    assert pieces == ["Hello"]


async def test_stream_provider_converts_transport_errors():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with pytest.raises(LLMError):
        async for _ in provider_with(handler).stream(ASK, Reply()):
            pass


async def test_gateway_works_without_a_recorder():
    gateway = LLMGateway([FakeLLM("gemini", script=["Answer without logging."])])

    result = await gateway.generate(ASK)

    assert result.text == "Answer without logging."


async def test_stream_skips_provider_when_circuit_is_open():
    h = Harness(FakeLLM("gemini", script=["Should not be called."]))
    breaker = h.gateway.breakers["gemini"]

    for _ in range(3):
        breaker.failure()

    with pytest.raises(LLMUnavailable, match="circuit open"):
        async for _ in h.gateway.stream(ASK):
            pass

    assert h.gateway.providers[0].calls == 0


@pytest.mark.parametrize(
    ("gemini_key", "groq_key", "expected"),
    [
        ("gemini-test", "groq-test", ["gemini", "groq"]),
        ("gemini-test", "", ["gemini"]),
        ("", "groq-test", ["groq"]),
        ("", "", []),
    ],
)
def test_build_gateway_includes_only_configured_providers(
    gemini_key, groq_key, expected
):
    settings = Settings(
        app_env="ci",
        database_url="postgresql://localhost:5432/test",
        gemini_api_key=gemini_key,
        groq_api_key=groq_key,
        usd_inr=95.0,
    )

    gateway = build_gateway(settings)

    assert [provider.name for provider in gateway.providers] == expected
    assert gateway._usd_inr == 95.0


def test_gateway_rejects_zero_max_attempts():
    with pytest.raises(ValueError, match="max_attempts must be at least 1"):
        LLMGateway([], max_attempts=0)
