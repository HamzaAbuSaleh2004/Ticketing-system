from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. All env vars and Gemini model IDs live here —
    never hardcode a Gemini model ID anywhere else."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Core
    ENV: Literal["local", "test", "prod"] = "local"
    JWT_SECRET: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60 * 24

    # Infra
    DATABASE_URL: str = "postgresql+asyncpg://ticketing:ticketing@db:5432/ticketing"
    REDIS_URL: str = "redis://redis:6379/0"

    # AI provider
    AI_PROVIDER: Literal["gemini", "fake"] = "fake"
    GEMINI_API_KEY: str | None = None
    GEMINI_TRIAGE_MODEL: str = "gemini-3.6-flash"
    GEMINI_ANSWER_MODEL: str = "gemini-3.6-flash"
    GEMINI_EMBED_MODEL: str = "gemini-embedding-001"
    EMBED_DIM: int = 768

    # Domain config
    RESOLVED_COOLOFF_HOURS: int = 72
    KB_SIMILARITY_THRESHOLD: float = 0.5

    # Attachments
    ATTACHMENTS_DIR: str = "/data/attachments"
    ATTACHMENT_MAX_BYTES: int = 10 * 1024 * 1024

    # Demo data
    SEED_DEMO: bool = True

    def check_prod_safe(self) -> None:
        """Phase 3 follow-up: refuse to start in prod with a weak/default
        JWT secret. Local and test behaviour is unaffected."""
        if self.ENV != "prod":
            return
        if self.JWT_SECRET == Settings.model_fields["JWT_SECRET"].default or len(self.JWT_SECRET) < 32:
            raise RuntimeError(
                "JWT_SECRET must be set to a random value of at least 32 bytes when ENV=prod"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
