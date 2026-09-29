from datetime import datetime

from sqlalchemy import ARRAY, DateTime, String, Text, func, literal_column
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class KnowledgeBaseArticle(Base):
    __tablename__ = "knowledge_base_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # §2 addition: slug is the source-link target for the KB search panel.
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# The text-search config, inlined as a constant (a bound parameter wouldn't
# resolve to regconfig), and the searchable text: title + body.
KB_SEARCH_CONFIG = "'english'::regconfig"
KB_SEARCH_VECTOR = func.to_tsvector(
    literal_column(KB_SEARCH_CONFIG),
    KnowledgeBaseArticle.title + " " + KnowledgeBaseArticle.body,
)
