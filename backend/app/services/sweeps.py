"""Periodic worker sweeps. Each takes an injected `now` so tests call them
directly, and locks the rows it changes with FOR UPDATE SKIP LOCKED: a row
an agent's PATCH is holding is skipped this round rather than overwritten."""

from datetime import datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.audit import write_audit
from app.domain.sla import is_at_risk
from app.models import LoginAttempt, Ticket
from app.models.enums import TicketPriority, TicketStatus
from app.services.tickets import escalate

_ESCALATION_PRIORITIES = [TicketPriority.high, TicketPriority.urgent]
# pending is excluded: the resolution clock is paused, and "at risk" means
# "not paused" (PLAN.md §3).
_RUNNING_STATUSES = [TicketStatus.open, TicketStatus.in_progress]


def _epoch(interval):
    return func.extract("epoch", interval)


def _resolution_window_minutes(ticket: Ticket) -> float:
    # Derived from the ticket itself rather than the current sla_policies row,
    # so editing a policy later doesn't change the window of existing tickets.
    total = (ticket.sla_resolution_due - ticket.created_at).total_seconds()
    return (total - ticket.sla_paused_total_seconds) / 60


def _response_window_minutes(ticket: Ticket) -> float:
    return (ticket.sla_response_due - ticket.created_at).total_seconds() / 60


def ticket_at_risk(ticket: Ticket, now: datetime) -> bool:
    paused = ticket.sla_paused_at is not None
    resolution = ticket.sla_resolution_due is not None and is_at_risk(
        due=ticket.sla_resolution_due,
        window_minutes=_resolution_window_minutes(ticket),
        paused=paused,
        now=now,
    )
    response = (
        ticket.first_responded_at is None
        and ticket.sla_response_due is not None
        and is_at_risk(
            due=ticket.sla_response_due,
            window_minutes=_response_window_minutes(ticket),
            paused=False,
            now=now,
        )
    )
    return resolution or response


async def sla_risk_sweep(session: AsyncSession, now: datetime) -> list[int]:
    """Auto-escalates urgent/high tickets that are at risk. `escalated` is the
    no-duplicate guard: an escalated ticket never matches again."""
    resolution_at_risk = _epoch(Ticket.sla_resolution_due - now) < 0.25 * (
        _epoch(Ticket.sla_resolution_due - Ticket.created_at) - Ticket.sla_paused_total_seconds
    )
    response_at_risk = and_(
        Ticket.first_responded_at.is_(None),
        _epoch(Ticket.sla_response_due - now) < 0.25 * _epoch(Ticket.sla_response_due - Ticket.created_at),
    )
    candidates = (
        await session.scalars(
            select(Ticket)
            .where(
                Ticket.status.in_(_RUNNING_STATUSES),
                Ticket.priority.in_(_ESCALATION_PRIORITIES),
                Ticket.escalated.is_(False),
                Ticket.sla_paused_at.is_(None),
                or_(resolution_at_risk, response_at_risk),
            )
            .order_by(Ticket.id)
            .with_for_update(skip_locked=True)
        )
    ).all()

    escalated_ids: list[int] = []
    for ticket in candidates:
        # The SQL filter narrows the candidates; the pure function decides.
        if not ticket_at_risk(ticket, now):
            continue
        before, after = await escalate(session, ticket)
        await write_audit(
            session,
            entity_type="ticket",
            entity_id=ticket.id,
            actor_id=None,
            action="ticket.auto_escalated",
            diff={"before": before, "after": after, "reason": "sla_at_risk"},
        )
        escalated_ids.append(ticket.id)
    await session.commit()
    return escalated_ids


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
