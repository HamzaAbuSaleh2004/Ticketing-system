import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.body_limit import BodySizeLimitMiddleware
from app.config import get_settings
from app.db import engine
from app.request_logging import RequestLoggingMiddleware
from app.routers.admin import router as admin_router
from app.routers.analytics import router as analytics_router
from app.routers.attachments import router as attachments_router
from app.routers.auth import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.internal import router as internal_router
from app.routers.kb import router as kb_router
from app.routers.organizations import router as organizations_router
from app.routers.tickets import router as tickets_router
from app.routers.users import router as users_router
from app.security_headers import SecurityHeadersMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
settings.check_prod_safe()

app = FastAPI(title="Ticketing Portal API")

app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(attachments_router)
app.include_router(kb_router)
app.include_router(categories_router)
app.include_router(organizations_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(analytics_router)
app.include_router(internal_router)


@app.get("/health")
async def health() -> dict:
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("Health check: database unreachable")
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
