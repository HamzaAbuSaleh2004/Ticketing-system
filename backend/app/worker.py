import asyncio
import logging
import socket
import time
from datetime import datetime
from functools import partial

from redis.exceptions import RedisError, ResponseError

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.ai import get_ai_provider
from app.config import get_settings
from app.db import SessionLocal
from app.domain import clock
from app.redis_client import get_redis
from app.services.sweeps import auto_close_sweep, sla_risk_sweep
from app.services.triage import triage_ticket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STREAM = "ticket.created"
GROUP = "triage"
CONSUMER = socket.gethostname()
# Entries left unacked this long (a failed triage, or a consumer that died,
# e.g. a recreated container with a new hostname) are claimed and retried.
RECLAIM_IDLE_MS = 60_000
RECLAIM_EVERY_SECONDS = 30


async def handle_ticket_created(fields: dict) -> None:
    ticket_id = int(fields["ticket_id"])
    async with SessionLocal() as session:
        await triage_ticket(session, ticket_id, get_ai_provider())


async def _process(entries: list) -> None:
    redis = get_redis()
    for message_id, fields in entries:
        try:
            await handle_ticket_created(fields)
        except Exception:
            # Left unacked: reclaimed and retried after RECLAIM_IDLE_MS.
            logger.exception("triage failed for %s %s", message_id, fields)
            continue
        await redis.xack(STREAM, GROUP, message_id)


async def _reclaim_stale() -> None:
    redis = get_redis()
    cursor = "0-0"
    while True:
        cursor, entries, _deleted = await redis.xautoclaim(
            STREAM, GROUP, CONSUMER, min_idle_time=RECLAIM_IDLE_MS, start_id=cursor, count=50
        )
        if entries:
            logger.info("reclaimed %d stale %s entries", len(entries), STREAM)
            await _process(entries)
        if cursor in ("0-0", b"0-0"):
            return


async def consume_ticket_created() -> None:
    redis = get_redis()
    try:
        await redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    last_reclaim = 0.0
    while True:
        try:
            if time.monotonic() - last_reclaim >= RECLAIM_EVERY_SECONDS:
                await _reclaim_stale()
                last_reclaim = time.monotonic()
            # Block well under redis-py's default 5s socket_timeout, or an
            # idle read raises TimeoutError.
            response = await redis.xreadgroup(GROUP, CONSUMER, {STREAM: ">"}, count=10, block=2000)
        except RedisError:
            logger.exception("reading %s failed; retrying", STREAM)
            await asyncio.sleep(1)
            continue
        if response:
            await _process(response[0][1])


async def run_sweeps_once(now: datetime) -> None:
    cooloff_hours = get_settings().RESOLVED_COOLOFF_HOURS
    sweeps = {
        "sla-risk": partial(sla_risk_sweep, now=now),
        "auto-close": partial(auto_close_sweep, now=now, cooloff_hours=cooloff_hours),
    }
    for name, sweep in sweeps.items():
        # Separate sessions: one sweep failing doesn't roll back the other.
        try:
            async with SessionLocal() as session:
                changed = await sweep(session)
            if changed:
                logger.info("%s sweep changed tickets %s", name, changed)
        except Exception:
            logger.exception("%s sweep failed", name)


async def run_sweeps_forever() -> None:
    while True:
        await run_sweeps_once(clock.now())
        await asyncio.sleep(get_settings().SWEEP_INTERVAL_SECONDS)


async def main() -> None:
    await get_redis().ping()
    logger.info("worker %s: consuming %s and sweeping", CONSUMER, STREAM)
    await asyncio.gather(consume_ticket_created(), run_sweeps_forever())


if __name__ == "__main__":
    asyncio.run(main())
