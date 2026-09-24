import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.config import get_settings
from app.db import engine
from app.redis_client import get_redis
from app.routers.attachments import router as attachments_router
from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.kb import router as kb_router
from app.routers.tickets import router as tickets_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
settings.check_prod_safe()

app = FastAPI(title="Ticketing Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(attachments_router)
app.include_router(kb_router)
app.include_router(categories_router)


@app.get("/health")
async def health() -> dict:
    db_ok = False
    redis_ok = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database unreachable")

    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        logger.exception("Health check: redis unreachable")

    status = "ok" if db_ok and redis_ok else "degraded"
    return {"status": status, "db": db_ok, "redis": redis_ok}
