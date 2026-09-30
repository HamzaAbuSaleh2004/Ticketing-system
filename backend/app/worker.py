"""The worker sweeps, every SWEEP_INTERVAL_SECONDS: auto-close of resolved
tickets past the reopen window, and pruning old login-attempt rows."""

import asyncio
import logging
from datetime import datetime
from functools import partial

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.config import get_settings
from app.db import SessionLocal
from app.domain import clock
from app.services.sweeps import auto_close_sweep, prune_login_attempts

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_sweeps_once(now: datetime) -> dict[str, list[int]]:
    """Returns what each sweep changed, so an HTTP caller (Cloud Scheduler,
    via `POST /internal/sweeps`) gets a real body back, not just a log line.
    A sweep that raises reports an empty list rather than failing the whole
    call — same as the loop below always moving on to the next sweep."""
    cooloff_hours = get_settings().RESOLVED_COOLOFF_HOURS
    sweeps = {
        "auto-close": partial(auto_close_sweep, now=now, cooloff_hours=cooloff_hours),
        "prune-login-attempts": partial(prune_login_attempts, now=now),
    }
    results: dict[str, list[int]] = {}
    for name, sweep in sweeps.items():
        # Separate sessions: one sweep failing doesn't roll back the other.
        try:
            async with SessionLocal() as session:
                changed = await sweep(session)
            results[name] = changed
            if changed:
                logger.info("%s sweep changed tickets %s", name, changed)
        except Exception:
            logger.exception("%s sweep failed", name)
            results[name] = []
    return results


async def main() -> None:
    if get_settings().SWEEPS_MODE == "off":
        logger.info("worker: SWEEPS_MODE=off, exiting without sweeping")
        return
    logger.info("worker: sweeping every %ss", get_settings().SWEEP_INTERVAL_SECONDS)
    while True:
        await run_sweeps_once(clock.now())
        await asyncio.sleep(get_settings().SWEEP_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
