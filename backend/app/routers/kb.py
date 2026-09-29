import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.config import get_settings
from app.db import get_db
from app.models import KnowledgeBaseArticle, User
from app.models.kb_article import KB_SEARCH_CONFIG, KB_SEARCH_VECTOR
from app.schemas.kb import KbArticleOut, KbSearchResponse, KbSearchResult

router = APIRouter(prefix="/kb", tags=["kb"])

_SNIPPET_CHARS = 180
_WORD = re.compile(r"\w+")


def _snippet(body: str) -> str:
    if len(body) <= _SNIPPET_CHARS:
        return body
    return body[:_SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


@router.get("/search", response_model=KbSearchResponse)
async def search(
    q: str = Query(min_length=2, max_length=500),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> KbSearchResponse:
    """Postgres full-text search over title + body. Any of the question's
    stemmed words can match (OR, not AND), so "forgot my password" finds the
    password article without needing every word in it; ts_rank_cd puts the
    articles matching more of them, closer together, first. websearch_to_tsquery
    never raises on user input, and stopword-only input matches nothing."""
    words = _WORD.findall(q)
    if not words:
        return KbSearchResponse(results=[])
    query = func.websearch_to_tsquery(literal_column(KB_SEARCH_CONFIG), " or ".join(words))
    rank = func.ts_rank_cd(KB_SEARCH_VECTOR, query)
    rows = (
        await session.execute(
            select(KnowledgeBaseArticle)
            .where(KB_SEARCH_VECTOR.op("@@")(query))
            .order_by(rank.desc(), KnowledgeBaseArticle.id)
            .limit(get_settings().KB_SEARCH_LIMIT)
        )
    ).scalars()
    return KbSearchResponse(
        results=[KbSearchResult(id=a.id, title=a.title, slug=a.slug, snippet=_snippet(a.body)) for a in rows]
    )


@router.get("/articles/{slug}", response_model=KbArticleOut)
async def get_article(
    slug: str,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> KbArticleOut:
    article = await session.scalar(select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.slug == slug))
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Article not found")
    return KbArticleOut.model_validate(article)
