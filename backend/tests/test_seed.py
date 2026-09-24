from sqlalchemy import select

from app import seed as seed_module
from app.ai import fake as fake_module
from app.models import KnowledgeBaseArticle


async def test_seed_kb_articles_idempotent_then_reembeds_on_model_change(db_session, monkeypatch):
    await seed_module.seed_kb_articles(db_session)

    articles = (await db_session.scalars(select(KnowledgeBaseArticle))).all()
    assert len(articles) == 5
    assert all(a.embedding_model == "fake-hash-v1" for a in articles)
    first_pass = {a.slug: list(a.embedding) for a in articles}

    # Re-seeding with the same provider/model id is a no-op.
    original_embed = fake_module.FakeProvider.embed
    calls: list[list[str]] = []

    async def counting_embed(self, texts):
        calls.append(texts)
        return await original_embed(self, texts)

    monkeypatch.setattr(fake_module.FakeProvider, "embed", counting_embed)

    await seed_module.seed_kb_articles(db_session)
    assert calls == []
    unchanged = (await db_session.scalars(select(KnowledgeBaseArticle))).all()
    assert {a.slug: list(a.embedding) for a in unchanged} == first_pass

    # PLAN.md Phase 3 follow-up: changing the provider's model id (e.g.
    # switching fake -> gemini) must re-embed every stale article.
    monkeypatch.setattr(fake_module.FakeProvider, "EMBEDDING_MODEL_ID", "fake-hash-v2")

    await seed_module.seed_kb_articles(db_session)
    assert len(calls) == 5

    reembedded = (await db_session.scalars(select(KnowledgeBaseArticle))).all()
    assert len(reembedded) == 5
    assert all(a.embedding_model == "fake-hash-v2" for a in reembedded)
