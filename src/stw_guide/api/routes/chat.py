"""Chat endpoint supporting streaming SSE and non-streaming JSON."""

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from stw_guide.llm.gateway import LLMResult, LLMUnavailable
from stw_guide.logging_setup import request_id_ctx

logger = logging.getLogger("stw_guide")

router = APIRouter(prefix="/chat", tags=["chat"])
PROMPT_VERSION = "chat_system_v1"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    message: str | None = Field(default=None, min_length=1, max_length=4000)
    messages: list[ChatMessage] | None = Field(
        default=None, min_length=1, max_length=20
    )
    stream: bool = True

    @model_validator(mode="after")
    def validate_input(self):
        if bool(self.message) == bool(self.messages):
            raise ValueError("Provide either message or messages, but not both.")
        return self

    def to_messages(self) -> list[dict[str, str]]:
        if self.message is not None:
            return [{"role": "user", "content": self.message}]
        return [message.model_dump() for message in self.messages or []]


def load_prompt(directory: Path) -> str:
    """Load the versioned system prompt."""
    return (directory / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8").strip()


def _sse(event: str, data: dict) -> str:
    """Format one Server-Sent Event."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _result_data(result: LLMResult, request_id: str) -> dict:
    """Return usage metadata without exposing internal model text."""
    return {
        "provider": result.provider,
        "model": result.model,
        "tokens_in": result.tokens_in,
        "tokens_out": result.tokens_out,
        "latency_ms": result.latency_ms,
        "attempts": result.attempts,
        "fallback_used": result.fallback_used,
        "cost_inr": result.cost_inr,
        "request_id": request_id,
    }


@router.post("")
async def chat(body: ChatRequest, request: Request):
    """Generate a JSON answer or stream answer tokens using SSE."""
    system_prompt = request.app.state.system_prompt
    messages = [
        {"role": "system", "content": system_prompt},
        *body.to_messages(),
    ]
    gateway = request.app.state.gateway
    request_id = request.state.request_id

    if not body.stream:
        token = request_id_ctx.set(request_id)
        try:
            result = await gateway.generate(
                messages,
                purpose="chat",
                prompt_version=PROMPT_VERSION,
            )
            return {
                "answer": result.text,
                **_result_data(result, request_id),
            }
        except LLMUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail="The language model is temporarily unavailable.",
            ) from exc
        finally:
            request_id_ctx.reset(token)

    # Fetch the first item before returning HTTP 200. This lets us report
    # provider failures as a proper HTTP 503 response.
    token = request_id_ctx.set(request_id)
    stream = gateway.stream(
        messages,
        purpose="chat",
        prompt_version=PROMPT_VERSION,
    )

    try:
        first = await anext(stream)
    except StopAsyncIteration as exc:
        request_id_ctx.reset(token)
        raise HTTPException(
            status_code=502,
            detail="The language model returned an empty stream.",
        ) from exc
    except LLMUnavailable as exc:
        request_id_ctx.reset(token)
        raise HTTPException(
            status_code=503,
            detail="The language model is temporarily unavailable.",
        ) from exc
    except Exception:
        request_id_ctx.reset(token)
        logger.exception("Failed before the first chat stream event")
        raise

    request_id_ctx.reset(token)

    async def event_stream() -> AsyncIterator[str]:
        stream_token = request_id_ctx.set(request_id)
        try:
            item = first

            while True:
                if isinstance(item, str):
                    yield _sse("token", {"text": item})
                elif isinstance(item, LLMResult):
                    yield _sse("result", _result_data(item, request_id))
                    return

                try:
                    item = await anext(stream)
                except StopAsyncIteration:
                    return

        except LLMUnavailable:
            logger.exception("LLM provider failed during chat streaming")
            yield _sse(
                "error",
                {"detail": "The language model is temporarily unavailable."},
            )
        except Exception:
            logger.exception("Unexpected error during chat streaming")
            yield _sse(
                "error",
                {"detail": "An unexpected error occurred while generating the answer."},
            )
        finally:
            await stream.aclose()
            request_id_ctx.reset(stream_token)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
