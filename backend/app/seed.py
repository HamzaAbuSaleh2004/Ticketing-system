import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("seed: no tables to seed yet")


if __name__ == "__main__":
    asyncio.run(main())
