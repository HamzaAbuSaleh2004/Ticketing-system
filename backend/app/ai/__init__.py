from app.ai.provider import AIProvider
from app.config import get_settings


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    if settings.AI_PROVIDER == "fake":
        from app.ai.fake import FakeProvider

        return FakeProvider()
    raise NotImplementedError("GeminiProvider lands in Phase 5; set AI_PROVIDER=fake for now.")
