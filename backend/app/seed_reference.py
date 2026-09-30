"""Seed only the reference data a real deployment needs (SLA policies and
categories): no demo users, organisations or tickets. Idempotent.

    python -m app.seed_reference
"""

import asyncio

from app.db import SessionLocal
from app.seed import seed_categories, seed_sla_policies


async def main() -> None:
    async with SessionLocal() as session:
        await seed_sla_policies(session)
        await seed_categories(session)
    print("Reference data seeded.")


if __name__ == "__main__":
    asyncio.run(main())
