import pytest
import pytest_asyncio
from sqlalchemy import text

from app import seed as seed_module
from tests.helpers import auth, register


@pytest_asyncio.fixture(autouse=True)
async def _kb(db_session):
    await seed_module.seed_kb_articles(db_session)


@pytest_asyncio.fixture
async def token(client):
    return await register(client, "kb-reader@example.com")


@pytest.mark.parametrize(
    ("query", "slug"),
    [
        ("forgot my password", "resetting-your-password"),
        ("the reset link never arrived", "resetting-your-password"),
        ("why was I charged twice on my invoice", "understanding-your-monthly-invoice"),
        ("the page is really slow and shows an error", "troubleshooting-slow-load-times"),
        ("can I delete my data", "how-we-handle-your-data"),
    ],
)
async def test_search_ranks_the_matching_article_first(client, token, query, slug):
    resp = await client.get("/kb/search", params={"q": query}, headers=auth(token))
    assert resp.status_code == 200
    first = resp.json()["results"][0]
    assert first["slug"] == slug
    assert first["title"] and first["snippet"]

    article = await client.get(f"/kb/articles/{slug}", headers=auth(token))
    assert article.status_code == 200
    assert article.json()["slug"] == slug


@pytest.mark.parametrize("query", ["what is the weather in paris", "the and of", "!!! ???", "'; drop table --"])
async def test_irrelevant_stopword_or_symbol_queries_find_nothing(client, token, query):
    resp = await client.get("/kb/search", params={"q": query}, headers=auth(token))
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


async def test_search_is_capped_and_every_result_matches(client, token):
    resp = await client.get("/kb/search", params={"q": "your account password invoice data slow request"}, headers=auth(token))
    results = resp.json()["results"]
    assert 1 < len(results) <= 5
    assert len({r["slug"] for r in results}) == len(results)


async def test_kb_requires_auth_and_unknown_article_is_404(client, token):
    assert (await client.get("/kb/search", params={"q": "password"})).status_code == 401
    assert (await client.get("/kb/articles/nope", headers=auth(token))).status_code == 404


async def test_search_expression_has_a_gin_index(db_session):
    """Without this index, /kb/search recomputes to_tsvector(title || body)
    for every row on every call - fine at 5 seeded articles, but an O(n)
    sequential scan once the knowledge base grows."""
    row = (
        await db_session.execute(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE tablename = 'knowledge_base_articles' AND indexname = 'ix_knowledge_base_articles_search'"
            )
        )
    ).first()
    assert row is not None, "ix_knowledge_base_articles_search is missing"
    assert "gin" in row[0].lower()
    assert "to_tsvector" in row[0].lower()
