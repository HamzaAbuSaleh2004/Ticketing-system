from datetime import datetime

from pydantic import BaseModel


class KbSearchResult(BaseModel):
    id: int
    title: str
    slug: str
    snippet: str


class KbSearchResponse(BaseModel):
    # Best match first; empty when nothing matched, and the UI then offers a request.
    results: list[KbSearchResult]


class KbArticleOut(BaseModel):
    id: int
    title: str
    slug: str
    body: str
    tags: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}
