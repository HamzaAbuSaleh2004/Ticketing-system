from typing import Protocol

from app.schemas.ai import (
    CategoryOption,
    EmbedTask,
    GroundedAnswer,
    KbContext,
    TriageResult,
)


class AIProvider(Protocol):
    # Identifies which model produced an embedding, so seed.py can tell a
    # stale (e.g. fake-mode) vector apart from a current one and re-embed it,
    # and KB search only compares vectors from the same model.
    EMBEDDING_MODEL_ID: str

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]: ...

    async def triage(
        self, *, subject: str, description: str, categories: list[CategoryOption]
    ) -> TriageResult: ...

    async def answer(self, *, question: str, articles: list[KbContext]) -> GroundedAnswer: ...
