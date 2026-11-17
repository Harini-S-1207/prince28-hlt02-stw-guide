"""FastAPI dependencies shared across routes."""

from fastapi import Request

from stw_guide.store import RecordStore


def get_store(request: Request) -> RecordStore:
    """Return the application's shared record store."""
    return request.app.state.store
