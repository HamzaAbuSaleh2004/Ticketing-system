from typing import Protocol

from app.redis_client import get_redis


class EventBus(Protocol):
    async def publish(self, stream: str, payload: dict) -> None: ...


class RedisStreamBus:
    """Redis Streams today; swap the implementation for Pub/Sub in
    iteration 2 without touching call sites (PLAN.md §5)."""

    async def publish(self, stream: str, payload: dict) -> None:
        redis = get_redis()
        # XADD requires flat string fields; nested values (e.g. a ticket id
        # that's an int) are stringified rather than json-dumping the whole
        # payload, so consumers can read individual fields without a parse.
        fields = {k: str(v) for k, v in payload.items()}
        await redis.xadd(stream, fields)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is None:
        _bus = RedisStreamBus()
    return _bus
