"""The SLA sweeps, every SWEEP_INTERVAL_SECONDS: auto-escalation of at-risk
urgent/high tickets, and auto-close of resolved tickets past the reopen window."""

import asyncio
import logging
from datetime import datetime
from functools import partial

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.config import get_settings
from app.db import SessionLocal
from app.domain import clock
from app.services.sweeps import auto_close_sweep, prune_login_attempts, sla_risk_sweep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_sweeps_once(now: datetime) -> None:
    cooloff_hours = get_settings().RESOLVED_COOLOFF_HOURS
    sweeps = {
        "sla-risk": partial(sla_risk_sweep, now=now),
        "auto-close": partial(auto_close_sweep, now=now, cooloff_hours=cooloff_hours),
        "prune-login-attempts": partial(prune_login_attempts, now=now),
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


async def main() -> None:
    logger.info("worker: sweeping every %ss", get_settings().SWEEP_INTERVAL_SECONDS)
    while True:
        await run_sweeps_once(clock.now())
        await asyncio.sleep(get_settings().SWEEP_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
