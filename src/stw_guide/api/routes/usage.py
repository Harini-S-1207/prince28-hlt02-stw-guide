"""LLM usage statistics endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from stw_guide.api.deps import get_db
from stw_guide.db.llm_calls import UsageRepository

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
async def get_usage(
    days: Annotated[int, Query(ge=1, le=90)] = 7,
    session: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict:
    """Return daily LLM usage totals."""
    repository = UsageRepository(session)

    return {
        "days": days,
        "items": await repository.by_day(days),
    }
