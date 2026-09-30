from sqlalchemy import ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import TicketPriority, ticket_priority_enum


class SlaPolicy(Base):
    """One row per priority, either the global default (organization_id
    NULL) or an override for one organisation. `get_policy` (services/
    tickets.py) resolves the applicable row: the organisation's own if it
    has one for that priority, else the global default. Postgres treats
    every NULL as distinct, so a plain UNIQUE(organization_id, priority)
    wouldn't stop duplicate global rows - two partial unique indexes instead:
    one default per priority, one override per (organisation, priority)."""

    __tablename__ = "sla_policies"
    __table_args__ = (
        Index(
            "uq_sla_policies_global_priority",
            "priority",
            unique=True,
            postgresql_where=text("organization_id IS NULL"),
        ),
        Index(
            "uq_sla_policies_org_priority",
            "organization_id",
            "priority",
            unique=True,
            postgresql_where=text("organization_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(ticket_priority_enum, nullable=False)
    response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
