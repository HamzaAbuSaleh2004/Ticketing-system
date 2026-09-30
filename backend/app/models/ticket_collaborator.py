from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TicketCollaborator(Base):
    """Phase 20 addition: an agent working a ticket alongside its primary
    assignee (`Ticket.assignee_id`). Collaborators never affect escalation,
    least-loaded-senior assignment, or the "active tickets" load count -
    those all key off `assignee_id` alone."""

    __tablename__ = "ticket_collaborators"
    __table_args__ = (UniqueConstraint("ticket_id", "user_id", name="uq_ticket_collaborators_ticket_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
