import asyncio
import logging

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.redis_client import get_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    redis = get_redis()
    await redis.ping()
    logger.info("worker: connected to redis, idling")
    while True:
        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
