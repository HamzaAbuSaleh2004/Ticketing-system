from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration: every env var lives here."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    ENV: Literal["local", "test", "prod"] = "local"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24

    # Infra
    # Cloud Run's Cloud SQL Unix socket form also works here, unchanged:
    # postgresql+asyncpg://USER:PASS@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE
    # Verified by reading SQLAlchemy's installed asyncpg dialect source
    # (dialects/postgresql/asyncpg.py `create_connect_args`, base.py
    # `_split_multihost_from_url`): every URL query param is forwarded to
    # asyncpg.connect(**opts), and asyncpg's own `host` accepts "an absolute
    # path to the directory containing the database server Unix-domain
    # socket" — exactly what the Cloud SQL Auth proxy mounts at /cloudsql/...
    DATABASE_URL: str = "postgresql+asyncpg://ticketing:ticketing@db:5432/ticketing"
    # db-f1-micro allows few connections; kept small on purpose.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 2

    # Two-factor authentication (TOTP, mandatory for every account)
    TOTP_ISSUER: str = "LiverX Help Desk"
    # The password step's short-lived token, exchanged for an access token
    # once the code is verified (or 2FA is enrolled).
    MFA_TOKEN_EXPIRES_MINUTES: int = 5
    MFA_MAX_FAILED_ATTEMPTS: int = 5
    MFA_LOCKOUT_MINUTES: int = 15
    MFA_RECOVERY_CODE_COUNT: int = 10

    # Domain config
    RESOLVED_COOLOFF_HOURS: int = 72
    KB_SEARCH_LIMIT: int = 5

    # Worker
    SWEEP_INTERVAL_SECONDS: int = 60
    # "loop": the worker container's while-True loop (local dev, and any
    # deploy that still runs a worker). "off": the worker process exits
    # immediately without sweeping — for a prod deploy where Cloud Scheduler
    # drives POST /internal/sweeps instead and no worker container is run at
    # all, this is a safety net against a worker accidentally left in place.
    SWEEPS_MODE: Literal["loop", "off"] = "loop"

    # Attachments
    ATTACHMENTS_DIR: str = "/data/attachments"
    ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024
    ATTACHMENTS_BACKEND: Literal["local", "gcs"] = "local"
    ATTACHMENTS_BUCKET: str = ""

    # Demo data: on by default only for local runs (never an implicit prod seed).
    SEED_DEMO: bool | None = None
    DEMO_DATA_PATH: str = "/demo-data/tickets.json"

    # Phase 13: admin bootstrap & production hardening
    STAFF_EMAIL_DOMAINS: str = "liverx.me"
    ALLOW_REGISTRATION: bool = True
    LOGIN_MAX_FAILED_ATTEMPTS: int = 10
    LOGIN_ATTEMPT_WINDOW_MINUTES: int = 15
    # Only the first hop of X-Forwarded-For is trusted, and only when this is
    # set — Cloud Run terminates TLS and sets it itself; a bare uvicorn behind
    # nothing must not trust a client-supplied header for its own IP.
    TRUST_PROXY: bool = False
    # Comma-separated; empty in prod, where the SPA is served same-origin
    # (Phase 16) and needs no CORS headers at all.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Phase 16: cloud-ready application (still local)
    # POST /internal/sweeps (Cloud Scheduler's replacement for the worker's
    # loop in prod) accepts only a Google-signed OIDC token whose audience is
    # this service's own URL and whose caller is this exact service account.
    SWEEP_AUDIENCE: str = ""
    SWEEP_INVOKER_EMAIL: str = ""

    def check_prod_safe(self) -> None:
        """Phase 3 follow-up: refuse to start in prod with a weak/default
        JWT secret. Phase 13 follow-up: also refuse ENV=prod with SEED_DEMO
        explicitly on, which would create the published-password demo
        accounts in a real deployment. Local and test behaviour is unaffected."""
        if self.ENV != "prod":
            return
        if self.JWT_SECRET == Settings.model_fields["JWT_SECRET"].default or len(self.JWT_SECRET) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a random value of at least 32 bytes when ENV=prod"
            )
        if self.seed_demo:
            raise RuntimeError("SEED_DEMO must not be enabled when ENV=prod")
        if self.ATTACHMENTS_BACKEND == "gcs" and not self.ATTACHMENTS_BUCKET:
            raise RuntimeError("ATTACHMENTS_BUCKET must be set when ATTACHMENTS_BACKEND=gcs")
        if not self.SWEEP_AUDIENCE or not self.SWEEP_INVOKER_EMAIL:
            raise RuntimeError("SWEEP_AUDIENCE and SWEEP_INVOKER_EMAIL must both be set when ENV=prod")

    @property
    def seed_demo(self) -> bool:
        return self.ENV == "local" if self.SEED_DEMO is None else self.SEED_DEMO

    @property
    def staff_email_domains(self) -> list[str]:
        return [d.strip().lower() for d in self.STAFF_EMAIL_DOMAINS.split(",") if d.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
