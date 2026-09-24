from typing import ClassVar, Protocol


class AIProvider(Protocol):
    """Embedding capability needed by seed.py. Phase 5 extends this with
    triage and grounded-answer methods and adds GeminiProvider."""

    # Identifies which model produced an embedding, so seed.py can tell a
    # stale (e.g. fake-mode) vector apart from a current one and re-embed it.
    EMBEDDING_MODEL_ID: ClassVar[str]

    async def embed(self, texts: list[str]) -> list[list[float]]: ...
