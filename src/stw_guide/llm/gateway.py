"""One door to every LLM provider."""

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal

import httpx

from stw_guide.config import Settings
from stw_guide.logging_setup import request_id_ctx

logger = logging.getLogger("stw_guide.llm")

PRICES_USD = {
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
}
MAX_WAIT = 20.0

Message = dict[str, str]
Recorder = Callable[[dict], Awaitable[None]]


class LLMError(Exception):
    """One provider call failed."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class LLMUnavailable(Exception):
    """No provider could answer."""


@dataclass
class Reply:
    """A provider response."""

    text: str = ""
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    attempts: int
    fallback_used: bool
    cost_inr: float


def cost_inr(model: str, tokens_in: int, tokens_out: int, usd_inr: float) -> float:
    """Calculate estimated cost in Indian rupees."""
    price_in, price_out = PRICES_USD.get(model, (0.0, 0.0))
    return round(
        (tokens_in * price_in + tokens_out * price_out) / 1_000_000 * usd_inr,
        6,
    )


def estimate_tokens(text: str) -> int:
    """Estimate tokens using approximately four characters per token."""
    return max(1, len(text) // 4)


class OpenAICompatProvider:
    """Provider using the OpenAI chat-completions API."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.name, self.model = name, model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0)
        )

    def _body(
        self,
        messages: list[Message],
        temperature: float,
        stream: bool,
        response_format: dict | None = None,
    ) -> dict:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if stream:
            body |= {
                "stream": True,
                "stream_options": {"include_usage": True},
            }
        return body

    @staticmethod
    def _error(response: httpx.Response) -> LLMError:
        code = response.status_code
        wait = response.headers.get("retry-after", "")
        return LLMError(
            f"HTTP {code}: {response.text[:200]}",
            retryable=code in {408, 429} or code >= 500,
            retry_after=(float(wait) if wait.replace(".", "", 1).isdigit() else None),
        )

    @staticmethod
    def _network_error(exc: httpx.TransportError) -> LLMError:
        timed_out = isinstance(exc, httpx.TimeoutException)
        return LLMError(
            type(exc).__name__,
            retryable=not timed_out,
        )

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> Reply:
        body = self._body(
            messages,
            temperature,
            stream=False,
            response_format=response_format,
        )
        try:
            response = await self._client.post(
                self._url,
                headers=self._headers,
                json=body,
            )
        except httpx.TransportError as exc:
            raise self._network_error(exc) from exc

        if response.status_code != 200:
            raise self._error(response)

        data = response.json()
        usage = data.get("usage") or {}
        text = data["choices"][0]["message"].get("content") or ""
        return Reply(
            text,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )

    async def stream(
        self,
        messages: list[Message],
        usage: Reply,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        """Yield text pieces from a server-sent event stream."""
        body = self._body(messages, temperature, stream=True)

        try:
            async with self._client.stream(
                "POST",
                self._url,
                headers=self._headers,
                json=body,
            ) as response:
                if response.status_code != 200:
                    await response.aread()
                    raise self._error(response)

                finished = False

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue

                    payload = line[5:].strip()

                    if payload == "[DONE]":
                        finished = True
                        break

                    chunk = json.loads(payload)

                    if chunk.get("usage"):
                        usage.tokens_in = chunk["usage"].get("prompt_tokens", 0)
                        usage.tokens_out = chunk["usage"].get("completion_tokens", 0)

                    for choice in chunk.get("choices") or []:
                        finished = finished or bool(choice.get("finish_reason"))
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            yield piece

                if not finished:
                    raise LLMError(
                        "the stream ended early",
                        retryable=True,
                    )

        except httpx.TransportError as exc:
            raise self._network_error(exc) from exc


class FakeLLM:
    """Scripted provider for tests without network calls or API costs."""

    def __init__(
        self,
        name: str = "fake",
        model: str = "fake-1",
        script: list | None = None,
    ):
        self.name, self.model = name, model
        self.script = list(script or [])
        self.calls = 0
        self.seen: list[dict] = []

    def _next(self) -> object:
        self.calls += 1
        return self.script.pop(0) if self.script else "A fake answer."

    async def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> Reply:
        self.seen.append(
            {
                "messages": messages,
                "temperature": temperature,
                "response_format": response_format,
            }
        )
        item = self._next()
        if isinstance(item, Exception):
            raise item
        return Reply(
            str(item),
            tokens_in=12,
            tokens_out=len(str(item).split()),
        )

    async def stream(
        self,
        messages: list[Message],
        usage: Reply,
        *,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        item = self._next()
        if isinstance(item, Exception):
            raise item
        error = item[1] if isinstance(item, tuple) else None
        words = ("Half an answer" if error else str(item)).split()
        for word in words:
            yield word + " "
        if error:
            raise error
        usage.tokens_in = 12
        usage.tokens_out = len(words)


class CircuitBreaker:
    def __init__(
        self,
        threshold=5,
        cooldown=30,
        clock=None,
        *,
        failure_threshold=None,
        reset_seconds=None,
    ):
        self.threshold = (
            failure_threshold if failure_threshold is not None else threshold
        )
        self.cooldown = reset_seconds if reset_seconds is not None else cooldown
        self.clock = clock
        self.failures = 0
        self.opened_at = None

    def _now(self) -> float:
        return self.clock() if self.clock is not None else time.monotonic()

    @property
    def state(self):
        if self.opened_at is None:
            return "closed"

        if self._now() - self.opened_at >= self.cooldown:
            return "half-open"

        return "open"

    @property
    def is_open(self):
        return self.state == "open"

    def allow(self):
        return self.state != "open"

    def failure(self):
        self.failures += 1

        if self.failures >= self.threshold:
            self.opened_at = self._now()

    def success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self):
        self.failure()

    def record_success(self):
        self.success()


class LLMGateway:
    """Routes requests through providers with retries and fallback."""

    def __init__(
        self,
        providers: list,
        *,
        recorder: Recorder | None = None,
        usd_inr: float = 95.0,
        max_attempts: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
        breaker_threshold: int = 3,
        breaker_cooldown: float = 30.0,
    ) -> None:
        self.providers = providers

        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        self.breakers = {
            provider.name: CircuitBreaker(
                breaker_threshold,
                breaker_cooldown,
                clock,
            )
            for provider in providers
        }
        self._recorder = recorder
        self._usd_inr = usd_inr
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._clock = clock

    async def _record(
        self,
        provider,
        purpose: str,
        prompt_version: str,
        **fields,
    ) -> None:
        row = {
            "request_id": request_id_ctx.get(),
            "provider": provider.name,
            "model": provider.model,
            "purpose": purpose,
            "prompt_version": prompt_version,
            **fields,
        }

        logger.info(
            "llm call %s %s %s",
            provider.name,
            provider.model,
            fields.get("status"),
        )

        if self._recorder:
            try:
                await self._recorder(row)
            except Exception:
                logger.exception("could not record the llm call")

    def _result(
        self,
        provider,
        messages,
        reply: Reply,
        started: float,
        attempts: int,
        index: int,
    ) -> LLMResult:
        prompt = " ".join(message["content"] for message in messages)
        tokens_in = reply.tokens_in or estimate_tokens(prompt)
        tokens_out = reply.tokens_out or estimate_tokens(reply.text)

        return LLMResult(
            text=reply.text,
            provider=provider.name,
            model=provider.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=int((self._clock() - started) * 1000),
            attempts=attempts,
            fallback_used=index > 0,
            cost_inr=cost_inr(
                provider.model,
                tokens_in,
                tokens_out,
                self._usd_inr,
            ),
        )

    @staticmethod
    def _fields(result: LLMResult) -> dict:
        return {
            "status": "ok",
            "tokens_in": result.tokens_in,
            "tokens_out": result.tokens_out,
            "latency_ms": result.latency_ms,
            "cost_inr": result.cost_inr,
            "fallback_used": result.fallback_used,
        }

    async def generate(
        self,
        messages: list[Message],
        *,
        purpose: str = "chat",
        prompt_version: str = "",
        **options,
    ) -> LLMResult:
        """Retry retryable failures and fall back to the next provider."""
        started = self._clock()
        problems = []

        for index, provider in enumerate(self.providers):
            breaker = self.breakers[provider.name]

            if not breaker.allow():
                problems.append(f"{provider.name}: circuit open")
                continue

            error: LLMError | None = None

            for attempt in range(1, self._max_attempts + 1):  # pragma: no branch
                try:
                    reply = await provider.generate(messages, **options)
                except LLMError as exc:
                    error = exc

                    if not exc.retryable or attempt == self._max_attempts:
                        break

                    wait = max(
                        random.uniform(0, 2**attempt),
                        exc.retry_after or 0.0,
                    )
                    await self._sleep(min(wait, MAX_WAIT))
                    continue

                breaker.success()
                result = self._result(
                    provider,
                    messages,
                    reply,
                    started,
                    attempt,
                    index,
                )
                await self._record(
                    provider,
                    purpose,
                    prompt_version,
                    **self._fields(result),
                )
                return result

            breaker.failure()
            problems.append(f"{provider.name}: {error}")

            await self._record(
                provider,
                purpose,
                prompt_version,
                status="error",
                error=str(error)[:300],
            )

        raise LLMUnavailable("; ".join(problems) or "no LLM provider is configured")

    async def stream(
        self,
        messages: list[Message],
        *,
        purpose: str = "chat",
        prompt_version: str = "",
        **options,
    ) -> AsyncIterator[str | LLMResult]:
        """Yield text pieces and then one result; fallback only before output."""
        started = self._clock()
        problems = []

        for index, provider in enumerate(self.providers):
            breaker = self.breakers[provider.name]

            if not breaker.allow():
                problems.append(f"{provider.name}: circuit open")
                continue

            usage = Reply()
            pieces = []

            try:
                async for piece in provider.stream(
                    messages,
                    usage,
                    **options,
                ):
                    pieces.append(piece)
                    yield piece

            except LLMError as exc:
                breaker.failure()

                await self._record(
                    provider,
                    purpose,
                    prompt_version,
                    status="error",
                    error=str(exc)[:300],
                )

                if pieces:
                    raise LLMUnavailable(
                        f"{provider.name} failed mid-answer: {exc}"
                    ) from exc

                problems.append(f"{provider.name}: {exc}")
                continue

            breaker.success()
            usage.text = "".join(pieces)

            result = self._result(
                provider,
                messages,
                usage,
                started,
                1,
                index,
            )

            await self._record(
                provider,
                purpose,
                prompt_version,
                **self._fields(result),
            )

            yield result
            return

        raise LLMUnavailable("; ".join(problems) or "no LLM provider is configured")


def build_gateway(
    settings: Settings,
    recorder: Recorder | None = None,
) -> LLMGateway:
    """Build Gemini primary and Groq fallback, omitting unconfigured keys."""
    wanted = [
        (
            "gemini",
            settings.llm_primary_base_url,
            settings.gemini_api_key,
            settings.llm_primary_model,
        ),
        (
            "groq",
            settings.llm_fallback_base_url,
            settings.groq_api_key,
            settings.llm_fallback_model,
        ),
    ]

    providers = [
        OpenAICompatProvider(
            name,
            url,
            key,
            model,
            timeout=settings.llm_timeout_seconds,
        )
        for name, url, key, model in wanted
        if key
    ]

    return LLMGateway(
        providers,
        recorder=recorder,
        usd_inr=settings.usd_inr,
    )


def calculate_cost_inr(
    tokens_in: int,
    tokens_out: int,
    input_price_per_million: float,
    output_price_per_million: float,
    usd_inr: float,
) -> Decimal:
    input_cost = (
        Decimal(tokens_in) * Decimal(str(input_price_per_million)) / Decimal(1000000)
    )

    output_cost = (
        Decimal(tokens_out) * Decimal(str(output_price_per_million)) / Decimal(1000000)
    )

    total = (input_cost + output_cost) * Decimal(str(usd_inr))

    return total.quantize(Decimal("0.000001"))
