import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import get_ai_provider
from app.ai.fake import FakeProvider
from app.ai.gemini import GeminiError
from app.auth.dependencies import current_user
from app.config import get_settings
from app.db import get_db
from app.domain.grounding import ground_citations
from app.models import KnowledgeBaseArticle, User
from app.schemas.ai import KbContext
from app.schemas.kb import KbArticleOut, KbSearchResponse, KbSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/kb", tags=["kb"])

_SNIPPET_CHARS = 180


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
    settings = get_settings()
    provider = get_ai_provider()
    try:
        [query_vector] = await provider.embed([q], task="query")
    except (GeminiError, httpx.HTTPError) as exc:
        logger.warning("KB query embedding failed: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Search is unavailable right now") from exc

    distance = KnowledgeBaseArticle.embedding.cosine_distance(query_vector)
    rows = (
        await session.execute(
            select(KnowledgeBaseArticle, distance.label("distance"))
            # Only vectors from the model that embedded the query are comparable.
            .where(KnowledgeBaseArticle.embedding_model == provider.EMBEDDING_MODEL_ID)
            .order_by(distance)
            .limit(settings.KB_SEARCH_TOP_K)
        )
    ).all()

    threshold = (
        settings.KB_SIMILARITY_THRESHOLD_FAKE
        if isinstance(provider, FakeProvider)
        else settings.KB_SIMILARITY_THRESHOLD
    )
    if not rows or 1 - rows[0].distance < threshold:
        return KbSearchResponse(answer=None, sources=[])

    articles = [row.KnowledgeBaseArticle for row in rows]
    grounded = await provider.answer(
        question=q, articles=[KbContext(id=a.id, title=a.title, body=a.body) for a in articles]
    )
    answer, source_ids = ground_citations(
        grounded.answer, grounded.cited_article_ids, [a.id for a in articles]
    )
    by_id = {a.id: a for a in articles}
    return KbSearchResponse(
        answer=answer,
        sources=[
            KbSource(id=i, title=by_id[i].title, slug=by_id[i].slug, snippet=_snippet(by_id[i].body))
            for i in source_ids
        ],
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
