import pytest
import pytest_asyncio

from app import seed as seed_module
from tests.helpers import auth, register


@pytest_asyncio.fixture(autouse=True)
async def _kb(db_session):
    await seed_module.seed_kb_articles(db_session)


@pytest.mark.parametrize(
    ("query", "slug"),
    [
        ("forgot my password", "resetting-your-password"),
        ("why was I charged twice on my invoice", "understanding-your-monthly-invoice"),
        ("the page is really slow and shows an error", "troubleshooting-slow-load-times"),
        ("can I delete my data", "how-we-handle-your-data"),
    ],
)
async def test_search_returns_grounded_answer_with_source_link(client, query, slug):
    token = await register(client, f"kb-{slug}@example.com")
    resp = await client.get("/kb/search", params={"q": query}, headers=auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] and "[1]" in body["answer"]
    assert body["sources"][0]["slug"] == slug
    assert body["sources"][0]["title"]
    assert body["sources"][0]["snippet"]

    article = await client.get(f"/kb/articles/{slug}", headers=auth(token))
    assert article.status_code == 200
    assert article.json()["slug"] == slug


async def test_search_without_a_relevant_article_returns_no_answer(client):
    token = await register(client, "kb-none@example.com")
    resp = await client.get("/kb/search", params={"q": "what is the weather in paris"}, headers=auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"answer": None, "sources": []}


async def test_search_ignores_vectors_from_another_embedding_model(client, db_session):
    from sqlalchemy import update

    from app.models import KnowledgeBaseArticle

    await db_session.execute(update(KnowledgeBaseArticle).values(embedding_model="some-other-model"))
    await db_session.commit()
    token = await register(client, "kb-stale@example.com")
    resp = await client.get("/kb/search", params={"q": "forgot my password"}, headers=auth(token))
    assert resp.json() == {"answer": None, "sources": []}


async def test_kb_requires_auth_and_unknown_article_is_404(client):
    assert (await client.get("/kb/search", params={"q": "password"})).status_code == 401
    token = await register(client, "kb-404@example.com")
    assert (await client.get("/kb/articles/nope", headers=auth(token))).status_code == 404
