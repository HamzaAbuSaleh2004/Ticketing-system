import math
import re
import zlib
from collections import Counter
from itertools import pairwise

from app.config import get_settings
from app.models.enums import TicketPriority
from app.schemas.ai import (
    CategoryOption,
    EmbedTask,
    GroundedAnswer,
    KbContext,
    TriageResult,
    TriageSuggestion,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORD_TEXT = (
    "a an the and or but if of to in on at for from by with about as is are was were be been being "
    "am do does did doing have has had having i me my we our you your he she it its they them their "
    "this that these those what which who whom how why when where there here can could should would "
    "will shall may might must not no so than too very just also into out up down over under again "
    "then once any all each few more most other some such only own same s t don now get got re ve ll "
    "d m let us"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())
_SUFFIXES = ("ing", "ed", "es", "s", "e")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Checked in order; the first category with a keyword hit wins.
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    (
        "data-privacy",
        (
            "privacy",
            "gdpr",
            "personal data",
            "delete my data",
            "export my data",
            "data export",
        ),
    ),
    (
        "account-login",
        (
            "password",
            "log in",
            "login",
            "sign in",
            "signin",
            "locked out",
            "2fa",
            "two-factor",
        ),
    ),
    (
        "billing",
        (
            "invoice",
            "charge",
            "charged",
            "bill",
            "refund",
            "payment",
            "card",
            "subscription",
        ),
    ),
    (
        "technical-issue",
        ("error", "slow", "crash", "bug", "broken", "not loading", "timeout", "500"),
    ),
]

_PRIORITY_KEYWORDS: list[tuple[TicketPriority, tuple[str, ...]]] = [
    (
        TicketPriority.urgent,
        (
            "urgent",
            "outage",
            "security",
            "breach",
            "hacked",
            "everyone",
            "all users",
            "asap",
        ),
    ),
    (
        TicketPriority.high,
        ("locked out", "cannot", "can't", "unable", "charged twice", "error", "down"),
    ),
    (
        TicketPriority.low,
        (
            "question",
            "how do i",
            "how can i",
            "feature request",
            "wondering",
            "curious",
        ),
    ),
]

_DRAFTS = {
    "account-login": (
        "Thanks for reaching out. I'm sorry you're having trouble getting into your account. "
        "I'm looking into it now and will follow up shortly with next steps."
    ),
    "billing": (
        "Thanks for getting in touch about your bill. I'm reviewing the charges on your account "
        "and will reply with what I find."
    ),
    "technical-issue": (
        "Thanks for reporting this. I'm sorry for the disruption. I'm investigating now; if you "
        "have an error reference code, please reply with it so I can trace the request."
    ),
    "data-privacy": (
        "Thanks for your message about your data. I've received your request and will confirm "
        "exactly what happens next."
    ),
}
_DEFAULT_DRAFT = (
    "Thanks for reaching out. I'm looking into your request and will follow up shortly."
)


class FakeProvider:
    """Deterministic, offline stand-in for Gemini so the stack runs with no
    API key and tests are reproducible.

    embed() uses feature hashing (stemmed content words + bigrams hashed into
    signed buckets, sublinear term frequency) rather than a per-text hash of
    the whole string, so it's roughly semantic: texts sharing vocabulary end
    up with positive cosine similarity and unrelated texts score ~0, which
    is what fake-mode KB search and its threshold rely on.
    """

    EMBEDDING_MODEL_ID = "fake-hash-v2"

    async def embed(self, texts: list[str], *, task: EmbedTask) -> list[list[float]]:
        dim = get_settings().EMBED_DIM
        return [_feature_hash_embedding(text, dim) for text in texts]

    async def triage(
        self, *, subject: str, description: str, categories: list[CategoryOption]
    ) -> TriageResult:
        return TriageResult(
            suggestion=fake_triage(
                subject=subject, description=description, categories=categories
            ),
            model="fake",
        )

    async def answer(
        self, *, question: str, articles: list[KbContext]
    ) -> GroundedAnswer:
        return fake_answer(question=question, articles=articles)


def fake_triage(
    *, subject: str, description: str, categories: list[CategoryOption]
) -> TriageSuggestion:
    text = f"{subject}\n{description}".lower()
    allowed = {c.slug for c in categories}

    category = next(
        (
            slug
            for slug, words in _CATEGORY_KEYWORDS
            if slug in allowed and _mentions(text, words)
        ),
        None,
    )
    if category is None:
        # With no active categories at all, "other" is still a safe value:
        # triage only applies a category that's in the allowed set.
        category = min(allowed) if allowed and "other" not in allowed else "other"

    priority = next(
        (p for p, words in _PRIORITY_KEYWORDS if _mentions(text, words)),
        TicketPriority.normal,
    )

    summary = " ".join(subject.split())
    if len(summary) > 120:
        summary = summary[:117].rstrip() + "..."

    return TriageSuggestion(
        category=category,
        priority=priority,
        one_line_summary=summary,
        suggested_response_draft=_DRAFTS.get(category, _DEFAULT_DRAFT),
    )


def fake_answer(*, question: str, articles: list[KbContext]) -> GroundedAnswer:
    """Extractive: the two sentences of the top article that share the most
    words with the question, cited by its id like the real model does."""
    if not articles:
        return GroundedAnswer(answer="", cited_article_ids=[])
    top = articles[0]
    query_tokens = set(_tokenize(question))
    sentences = [s.strip() for s in _SENTENCE_RE.split(top.body) if s.strip()]
    scored = sorted(
        enumerate(sentences),
        key=lambda item: (-len(query_tokens & set(_tokenize(item[1]))), item[0]),
    )
    picked = sorted(idx for idx, _ in scored[:2])
    answer = " ".join(sentences[i] for i in picked)
    return GroundedAnswer(answer=f"{answer} [{top.id}]", cited_article_ids=[top.id])


def _mentions(text: str, phrases: tuple[str, ...]) -> bool:
    # Whole words only, so "download" doesn't match "down".
    return any(re.search(rf"\b{re.escape(p)}\b", text) for p in phrases)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if len(word) - len(suffix) >= 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _feature_hash_embedding(text: str, dim: int) -> list[float]:
    terms = [_stem(w) for w in _tokenize(text) if w not in _STOPWORDS]
    counts: Counter[str] = Counter(terms)
    bigram_weights = {f"{a}_{b}": 0.5 for a, b in pairwise(terms)}

    vector = [0.0] * dim
    features = [(f, 1 + math.log(n)) for f, n in counts.items()] + list(
        bigram_weights.items()
    )
    for feature, weight in features:
        digest = zlib.crc32(feature.encode("utf-8"))
        sign = 1.0 if (digest // dim) % 2 == 0 else -1.0
        vector[digest % dim] += sign * weight

    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]
