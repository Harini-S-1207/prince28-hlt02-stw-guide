"""Unit tests for the ingestion store module."""

from unittest.mock import AsyncMock

import pytest

from stw_guide.ingest.store import failed_paths


@pytest.mark.asyncio
async def test_failed_paths_returns_all_failed_file_paths():
    session = AsyncMock()
    session.scalars.return_value = [
        "data/file1.pdf",
        "data/file2.pdf",
    ]

    result = await failed_paths(session)

    assert result == {
        "data/file1.pdf",
        "data/file2.pdf",
    }
    session.scalars.assert_awaited_once()
