"""Standardized API error responses using RFC 9457."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
) -> JSONResponse:
    """Create an RFC 9457-style problem response."""

    body = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
    }

    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle HTTP exceptions."""

    titles = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        422: "Unprocessable Content",
        500: "Internal Server Error",
    }

    return problem_response(
        request=request,
        status=exc.status_code,
        title=titles.get(exc.status_code, "HTTP Error"),
        detail=str(exc.detail),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle invalid request data."""

    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
        }
        for error in exc.errors()
    ]

    body = {
        "type": "about:blank",
        "title": "Validation Error",
        "status": 422,
        "detail": "Request validation failed.",
        "instance": request.url.path,
        "request_id": getattr(request.state, "request_id", None),
        "errors": errors,
    }

    return JSONResponse(
        status_code=422,
        content=body,
        media_type="application/problem+json",
    )
