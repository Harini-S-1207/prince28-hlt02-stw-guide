"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/health")
async def health():
    """Check whether the application is alive."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    """Check whether PostgreSQL is reachable."""

    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "checks": {
                "database": True,
            },
        }

    except (SQLAlchemyError, OSError, TimeoutError):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {
                    "database": False,
                },
            },
        )
