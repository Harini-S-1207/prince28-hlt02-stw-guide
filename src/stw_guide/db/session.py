"""Create the async PostgreSQL engine and session factory."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from stw_guide.config import Settings


def make_engine(settings: Settings):
    """Create the database connection pool."""
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        echo=settings.log_level == "DEBUG",
    )


def make_sessionmaker(engine):
    """Create sessions for database operations."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
