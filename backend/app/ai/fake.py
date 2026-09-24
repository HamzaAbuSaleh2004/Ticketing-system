import math
import re
import zlib
from itertools import pairwise

from app.config import get_settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class FakeProvider:
    """Deterministic, offline stand-in for Gemini so the stack runs with no
    API key. Phase 5 adds keyword-based triage here; embed() is enough for
    seeding and searching the KB today.

    embed() uses feature hashing (word + bigram hashing into signed buckets)
    rather than a per-text hash of the whole string, so it's roughly
    semantic: texts sharing vocabulary end up with positive cosine
    similarity, which is what fake-mode KB search relies on.
    """

    EMBEDDING_MODEL_ID = "fake-hash-v1"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        dim = get_settings().EMBED_DIM
        return [_feature_hash_embedding(text, dim) for text in texts]


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _feature_hash_embedding(text: str, dim: int) -> list[float]:
    tokens = _tokenize(text)
    bigrams = [f"{a}_{b}" for a, b in pairwise(tokens)]

    vector = [0.0] * dim
    for feature in tokens + bigrams:
        digest = zlib.crc32(feature.encode("utf-8"))
        bucket = digest % dim
        sign = 1.0 if (digest // dim) % 2 == 0 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
