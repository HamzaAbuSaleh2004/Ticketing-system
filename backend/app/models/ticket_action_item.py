from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.enums import ActionItemSide, action_item_side_enum


class TicketActionItem(Base):
    """Phase 12 addition: a ticket's "what's needed" checklist item, on one
    of two sides - what's needed from the customer, or from LiverX."""

    __tablename__ = "ticket_action_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False, index=True)
    side: Mapped[ActionItemSide] = mapped_column(action_item_side_enum, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
