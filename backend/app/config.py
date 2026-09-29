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
    DATABASE_URL: str = "postgresql+asyncpg://ticketing:ticketing@db:5432/ticketing"

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

    # Attachments
    ATTACHMENTS_DIR: str = "/data/attachments"
    ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024

    # Demo data: on by default only for local runs (never an implicit prod seed).
    SEED_DEMO: bool | None = None
    DEMO_DATA_PATH: str = "/demo-data/tickets.json"

    def check_prod_safe(self) -> None:
        """Phase 3 follow-up: refuse to start in prod with a weak/default
        JWT secret. Local and test behaviour is unaffected."""
        if self.ENV != "prod":
            return
        if self.JWT_SECRET == Settings.model_fields["JWT_SECRET"].default or len(self.JWT_SECRET) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a random value of at least 32 bytes when ENV=prod"
            )

    @property
    def seed_demo(self) -> bool:
        return self.ENV == "local" if self.SEED_DEMO is None else self.SEED_DEMO


@lru_cache
def get_settings() -> Settings:
    return Settings()
