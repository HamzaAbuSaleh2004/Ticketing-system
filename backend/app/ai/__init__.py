import logging
from functools import lru_cache

from app.ai.provider import AIProvider
from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.use_gemini:
        from app.ai.gemini import GeminiProvider

        return GeminiProvider(settings)

    if settings.AI_PROVIDER == "gemini":
        logger.warning("AI_PROVIDER=gemini but GEMINI_API_KEY is not set; using the fake provider")
    from app.ai.fake import FakeProvider

    return FakeProvider()
