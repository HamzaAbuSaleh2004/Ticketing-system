from datetime import datetime

from pydantic import BaseModel


class KbSource(BaseModel):
    id: int
    title: str
    slug: str
    snippet: str


class KbSearchResponse(BaseModel):
    # null when nothing relevant was found; the UI then offers "Submit a request".
    answer: str | None
    sources: list[KbSource]


class KbArticleOut(BaseModel):
    id: int
    title: str
    slug: str
    body: str
    tags: list[str]
    updated_at: datetime

    model_config = {"from_attributes": True}
