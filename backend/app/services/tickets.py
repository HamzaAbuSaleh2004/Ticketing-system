"""Ticket mutations shared by the API routers, AI triage and the worker
sweeps, so each rule lives in one place."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.lifecycle import escalate_priority
from app.domain.sla import recompute_due_on_priority_change
from app.models import SlaPolicy, Team, Ticket, User
from app.models.enums import TicketPriority, TicketStatus, UserRole

ACTIVE_STATUSES = [
    TicketStatus.new,
    TicketStatus.triaged,
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


async def get_policy(session: AsyncSession, priority: TicketPriority) -> SlaPolicy:
    policy = await session.scalar(select(SlaPolicy).where(SlaPolicy.priority == priority))
    if policy is None:
        raise RuntimeError(f"No SLA policy configured for priority {priority.value}")
    return policy


async def set_priority(session: AsyncSession, ticket: Ticket, priority: TicketPriority) -> None:
    ticket.priority = priority
    policy = await get_policy(session, priority)
    ticket.sla_response_due, ticket.sla_resolution_due = recompute_due_on_priority_change(
        created_at=ticket.created_at,
        response_minutes=policy.response_minutes,
        resolution_minutes=policy.resolution_minutes,
        first_responded_at=ticket.first_responded_at,
        paused_total_seconds=ticket.sla_paused_total_seconds,
        current_response_due=ticket.sla_response_due,
    )


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
    await set_priority(session, ticket, escalate_priority(ticket.priority))
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
