import hashlib
import math

from app.config import get_settings


class FakeProvider:
    """Deterministic, offline stand-in for Gemini so the stack runs with no
    API key. Phase 5 adds keyword-based triage here; embed() is enough for
    seeding KB articles today."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = get_settings().EMBED_DIM
        return [_hash_embedding(text, dim) for text in texts]


def _hash_embedding(text: str, dim: int) -> list[float]:
    values: list[float] = []
    counter = 0
    while len(values) < dim:
        digest = hashlib.sha256(f"{text}:{counter}".encode()).digest()
        values.extend(byte / 255.0 - 0.5 for byte in digest)
        counter += 1
    values = values[:dim]
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]
