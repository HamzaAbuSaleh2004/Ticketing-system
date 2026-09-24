from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db import Base

_settings = get_settings()


class KnowledgeBaseArticle(Base):
    __tablename__ = "knowledge_base_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # §2 addition: slug is the source-link target for the KB search panel.
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    # §2 addition: real vector(768) column, populated at seed time by the AIProvider.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_settings.EMBED_DIM), nullable=True)
    # Phase 3 follow-up: which model produced `embedding` (e.g. "fake-hash-v1"
    # vs "gemini-embedding-001"), so seed.py can re-embed articles when the
    # provider changes instead of comparing stale and current vectors.
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
