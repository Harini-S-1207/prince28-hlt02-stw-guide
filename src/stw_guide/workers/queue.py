"""A small ARQ wrapper for submitting ingestion jobs."""

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

JOB = "ingest_document"


def redis_settings(url: str) -> RedisSettings:
    """Build Redis connection settings from the configured URL."""
    settings = RedisSettings.from_dsn(url)
    settings.conn_retries = 1
    settings.conn_retry_delay = 0
    return settings


class Queue:
    """Submit document item IDs to the Redis-backed ARQ queue."""

    def __init__(self, pool: ArqRedis) -> None:
        self.pool = pool

    @classmethod
    async def connect(cls, url: str) -> "Queue":
        """Connect to Redis and create the queue wrapper."""
        return cls(await create_pool(redis_settings(url)))

    async def put(self, item_ids: list[int]) -> int:
        """Enqueue items, skipping IDs that are already queued."""
        added = 0

        for item_id in item_ids:
            job = await self.pool.enqueue_job(
                JOB,
                item_id,
                _job_id=f"ingest:{item_id}",
            )
            added += job is not None

        return added

    async def close(self) -> None:
        """Close the Redis connection."""
        await self.pool.aclose()
