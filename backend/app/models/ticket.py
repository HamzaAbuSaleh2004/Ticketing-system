from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import (
    TicketPriority,
    TicketStatus,
    ticket_priority_enum,
    ticket_status_enum,
)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        ticket_status_enum, nullable=False, default=TicketStatus.new, index=True
    )
    priority: Mapped[TicketPriority] = mapped_column(
        ticket_priority_enum, nullable=False, default=TicketPriority.normal, index=True
    )
    category: Mapped[str | None] = mapped_column(
        ForeignKey("categories.slug"), nullable=True, index=True
    )
    # Phase 12 addition: which organisation has the problem. Set at create
    # from the requester's organisation; agents can change it.
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )

    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    sla_response_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_resolution_due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # §2 addition: the resolution clock pauses while status = pending.
    sla_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_paused_total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # §2 addition: needed for first-response-time analytics and the response SLA.
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # §2 addition: the linked follow-up ticket created when a customer replies on a closed ticket.
    parent_ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"), nullable=True)

    # §2 addition: escalation flag.
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
