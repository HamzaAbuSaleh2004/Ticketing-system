from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import OrganizationKind, organization_kind_enum


class Organization(Base):
    """Phase 12 addition: the company or government entity a ticket and its
    requester belong to. Name uniqueness is case-insensitive (a functional
    unique index on lower(name), added in the migration)."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[OrganizationKind] = mapped_column(organization_kind_enum, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
