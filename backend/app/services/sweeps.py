"""Periodic worker sweeps. Each takes an injected `now` so tests call them
directly, and locks the rows it changes with FOR UPDATE SKIP LOCKED: a row
an agent's PATCH is holding is skipped this round rather than overwritten."""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import write_audit
from app.models import LoginAttempt, Ticket
from app.models.enums import TicketStatus


async def auto_close_sweep(session: AsyncSession, now: datetime, *, cooloff_hours: int) -> list[int]:
    """Closes resolved tickets whose cooling-off window has expired."""
    tickets = (
        await session.scalars(
            select(Ticket)
            .where(
                Ticket.status == TicketStatus.resolved,
                Ticket.resolved_at <= now - timedelta(hours=cooloff_hours),
            )
            .order_by(Ticket.id)
            .with_for_update(skip_locked=True)
        )
    ).all()
    for ticket in tickets:
        ticket.status = TicketStatus.closed
        ticket.closed_at = now
        await write_audit(
            session,
            entity_type="ticket",
            entity_id=ticket.id,
            actor_id=None,
            action="ticket.auto_closed",
            diff={"before": {"status": "resolved"}, "after": {"status": "closed"}},
        )
    await session.commit()
    return [t.id for t in tickets]


async def prune_login_attempts(session: AsyncSession, now: datetime, *, older_than_days: int = 1) -> list[int]:
    """Failed-login rows exist only to feed the rolling rate-limit window
    (Phase 13), so nothing needs one past a day old."""
    cutoff = now - timedelta(days=older_than_days)
    result = await session.execute(
        delete(LoginAttempt).where(LoginAttempt.created_at < cutoff).returning(LoginAttempt.id)
    )
    ids = [row[0] for row in result]
    await session.commit()
    return ids
