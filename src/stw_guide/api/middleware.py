"""Request ID, timing and crash-handling middleware."""

import logging
import time
import uuid

from fastapi import FastAPI, Request

from stw_guide.api.errors import problem_response

logger = logging.getLogger(__name__)


def register_middleware(app: FastAPI) -> None:
    """Register application middleware."""

    @app.middleware("http")
    async def request_middleware(request: Request, call_next):
        # 1. Generate or reuse request ID
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        # 2. Start request timer
        start_time = time.perf_counter()

        try:
            response = await call_next(request)

        except Exception:
            # 3. Handle unexpected application errors
            logger.exception(
                "unhandled request error",
                extra={"request_id": request_id},
            )

            response = problem_response(
                request=request,
                status=500,
                title="Internal Server Error",
                detail="An unexpected error occurred.",
            )

        # Calculate processing time
        duration_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        # Add request information to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)

        logger.info(
            "request completed",
            extra={"request_id": request_id},
        )

        return response
