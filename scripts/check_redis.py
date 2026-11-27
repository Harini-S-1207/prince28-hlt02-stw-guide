import asyncio

from stw_guide.config import get_settings
from stw_guide.workers.queue import Queue


async def main():
    settings = get_settings()
    queue = await Queue.connect(settings.redis_url)

    try:
        print("Redis queue connection: OK")
    finally:
        await queue.close()


if __name__ == "__main__":
    asyncio.run(main())
