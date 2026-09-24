from app.ai.fake import FakeProvider
from app.seed import KB_ARTICLES


async def test_fake_embedding_ranks_password_article_first():
    """PLAN.md Phase 3 follow-up: fake-mode embeddings must be roughly
    semantic, or fake-mode KB search can never return the right article."""
    provider = FakeProvider()
    article_texts = [f"{a['title']}\n\n{a['body']}" for a in KB_ARTICLES]
    *article_embeddings, query_embedding = await provider.embed([*article_texts, "forgot my password"], task="query")

    similarities = [
        (article["slug"], sum(x * y for x, y in zip(query_embedding, embedding, strict=True)))
        for article, embedding in zip(KB_ARTICLES, article_embeddings, strict=True)
    ]
    best_slug, _ = max(similarities, key=lambda item: item[1])

    assert best_slug == "resetting-your-password"
