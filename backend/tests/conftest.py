"""Test bootstrap.

Runs against a real Postgres database (`ticketing_test`, on the same server
as the dev `ticketing` database — see docker-compose's `db` service), not
mocks or SQLite, so async SQLAlchemy and full-text search behave as in prod.
The DATABASE_URL override below must happen before anything imports
`app.db` (which builds the async engine at import time), so it's done here
at module scope, before pytest imports any test module.
"""

import os

_DEV_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://ticketing:ticketing@db:5432/ticketing"
)
_base, _, _ = _DEV_DATABASE_URL.rpartition("/")
TEST_DATABASE_URL = f"{_base}/ticketing_test"
MAINTENANCE_DATABASE_URL = f"{_base}/postgres".replace("+asyncpg", "")

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-prod-32-bytes-min")
# Most tests still self-register via tests.helpers.register()/register_full();
# the "closed by default" behavior itself is covered directly by the test
# that overrides this back to false.
os.environ.setdefault("ALLOW_REGISTRATION", "true")

import asyncio
import subprocess
import sys
from pathlib import Path

import asyncpg
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

BACKEND_DIR = Path(__file__).resolve().parent.parent


async def _ensure_test_database() -> None:
    conn = await asyncpg.connect(MAINTENANCE_DATABASE_URL)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = 'ticketing_test'")
        if not exists:
            await conn.execute('CREATE DATABASE "ticketing_test"')
    finally:
        await conn.close()


def _run_migrations() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ,
        check=True,
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database() -> None:
    await _ensure_test_database()
    await asyncio.to_thread(_run_migrations)


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    yield
    from app.db import engine

    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename != 'alembic_version'"
            )
        )
        tables = [r[0] for r in rows]
        if tables:
            await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    from app.db import SessionLocal

    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
