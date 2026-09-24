from typing import Protocol


class AIProvider(Protocol):
    """Embedding capability needed by seed.py. Phase 5 extends this with
    triage and grounded-answer methods and adds GeminiProvider."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
