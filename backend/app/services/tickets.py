"""Ticket mutations shared by the API routers, AI triage and the worker
sweeps, so each rule lives in one place."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lifecycle import escalate_priority
from app.models import Team, Ticket, User
from app.models.enums import TicketPriority, TicketStatus, UserRole

ACTIVE_STATUSES = [
    TicketStatus.open,
    TicketStatus.in_progress,
    TicketStatus.pending,
]


async def lock_ticket(session: AsyncSession, ticket_id: int) -> Ticket | None:
    """Row-locks the ticket for the rest of the transaction, so an agent's
    PATCH, a customer reply, AI triage and the worker sweeps can't overwrite
    each other's changes."""
    return await session.scalar(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def set_priority(ticket: Ticket, priority: TicketPriority) -> None:
    ticket.priority = priority


async def least_loaded_senior(session: AsyncSession) -> int | None:
    load_subq = (
        select(Ticket.assignee_id, func.count(Ticket.id).label("load"))
        .where(Ticket.status.in_(ACTIVE_STATUSES))
        .group_by(Ticket.assignee_id)
        .subquery()
    )
    stmt = (
        select(User.id)
        .outerjoin(load_subq, load_subq.c.assignee_id == User.id)
        .where(User.role == UserRole.agent, User.team == Team.senior)
        .order_by(func.coalesce(load_subq.c.load, 0).asc(), User.id.asc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def escalate(session: AsyncSession, ticket: Ticket) -> tuple[dict, dict]:
    """Priority bump (capped at urgent) + escalated flag + reassignment to
    the least-loaded senior agent. Returns the (before, after) audit diff.
    The caller checks lifecycle.can_escalate first."""
    before = {
        "priority": ticket.priority.value,
        "escalated": ticket.escalated,
        "assignee_id": ticket.assignee_id,
    }
    set_priority(ticket, escalate_priority(ticket.priority))
    ticket.escalated = True
    senior_id = await least_loaded_senior(session)
    if senior_id is not None:
        ticket.assignee_id = senior_id
    after = {
        "priority": ticket.priority.value,
        "escalated": ticket.escalated,
        "assignee_id": ticket.assignee_id,
    }
    return before, after
