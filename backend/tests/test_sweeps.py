from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Ticket
from app.models.enums import Team, TicketPriority, TicketStatus
from app.services.sweeps import auto_close_sweep, sla_risk_sweep
from app.services.tickets import lock_ticket
from tests.helpers import create_agent, register, seed_reference_data

BASE = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _ticket(db_session, requester_id: int, **fields) -> Ticket:
    """High priority, 1h response / 8h resolution window from BASE by default."""
    values = {
        "subject": "s",
        "description": "d",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.high,
        "requester_id": requester_id,
        "created_at": BASE,
        "sla_response_due": BASE + timedelta(hours=1),
        "sla_resolution_due": BASE + timedelta(hours=8),
        "first_responded_at": BASE + timedelta(minutes=5),
    } | fields
    ticket = Ticket(**values)
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    return ticket


async def _requester(client, db_session) -> int:
    await register(client, "sweep-user@example.com")
    from app.models import User

    return (await db_session.scalar(select(User.id).where(User.email == "sweep-user@example.com")))


async def test_sla_risk_sweep_escalates_at_risk_high_ticket_once(client, db_session):
    senior = await create_agent(db_session, email="sweep-senior@example.com", team=Team.senior)
    requester = await _requester(client, db_session)
    at_risk = await _ticket(db_session, requester)
    comfortable = await _ticket(db_session, requester, sla_resolution_due=BASE + timedelta(hours=20))
    paused = await _ticket(
        db_session, requester, status=TicketStatus.pending, sla_paused_at=BASE + timedelta(hours=1)
    )
    normal = await _ticket(db_session, requester, priority=TicketPriority.normal)

    # 7h in: 1h of the 8h window left = 12.5% < 25%.
    now = BASE + timedelta(hours=7)
    async with SessionLocal() as session:
        escalated = await sla_risk_sweep(session, now)
    assert escalated == [at_risk.id]

    async with SessionLocal() as session:
        ticket = await session.get(Ticket, at_risk.id)
        assert ticket.escalated is True
        assert ticket.priority is TicketPriority.urgent
        assert ticket.assignee_id == senior.id
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.entity_id == at_risk.id, AuditLog.action == "ticket.auto_escalated")
        )
        assert audit.actor_id is None
        for other in (comfortable, paused, normal):
            assert (await session.get(Ticket, other.id)).escalated is False

    # No duplicate escalation on the next sweep.
    async with SessionLocal() as session:
        assert await sla_risk_sweep(session, now + timedelta(minutes=1)) == []


async def test_sla_risk_sweep_counts_pause_time_in_the_window(client, db_session):
    requester = await _requester(client, db_session)
    # 8h window + 4h of past pause = due at 12h. At 9h, 3h of 8h left (37%): fine.
    ticket = await _ticket(
        db_session, requester,
        sla_resolution_due=BASE + timedelta(hours=12), sla_paused_total_seconds=4 * 3600,
    )
    async with SessionLocal() as session:
        assert await sla_risk_sweep(session, BASE + timedelta(hours=9)) == []
    async with SessionLocal() as session:
        assert await sla_risk_sweep(session, BASE + timedelta(hours=10, minutes=30)) == [ticket.id]


async def test_sla_risk_sweep_escalates_on_response_sla_before_first_reply(client, db_session):
    requester = await _requester(client, db_session)
    ticket = await _ticket(db_session, requester, status=TicketStatus.open, first_responded_at=None)
    # 50 of 60 response minutes gone.
    async with SessionLocal() as session:
        assert await sla_risk_sweep(session, BASE + timedelta(minutes=50)) == [ticket.id]


async def test_sla_risk_sweep_skips_a_row_locked_by_a_concurrent_patch(client, db_session):
    requester = await _requester(client, db_session)
    ticket = await _ticket(db_session, requester)
    now = BASE + timedelta(hours=7)

    async with SessionLocal() as agent_session:
        await lock_ticket(agent_session, ticket.id)  # an agent's PATCH mid-transaction
        async with SessionLocal() as sweep_session:
            assert await sla_risk_sweep(sweep_session, now) == []
        await agent_session.commit()

    async with SessionLocal() as sweep_session:
        assert await sla_risk_sweep(sweep_session, now) == [ticket.id]


async def test_auto_close_sweep_skips_a_row_locked_by_a_concurrent_patch(client, db_session):
    requester = await _requester(client, db_session)
    resolved_at = BASE + timedelta(hours=2)
    ticket = await _ticket(db_session, requester, status=TicketStatus.resolved, resolved_at=resolved_at)
    now = resolved_at + timedelta(hours=72, minutes=1)

    async with SessionLocal() as agent_session:
        await lock_ticket(agent_session, ticket.id)  # an agent's PATCH mid-transaction
        async with SessionLocal() as sweep_session:
            assert await auto_close_sweep(sweep_session, now, cooloff_hours=72) == []
        await agent_session.commit()

    async with SessionLocal() as sweep_session:
        assert await auto_close_sweep(sweep_session, now, cooloff_hours=72) == [ticket.id]


async def test_auto_close_sweep_closes_after_cooloff(client, db_session):
    requester = await _requester(client, db_session)
    resolved_at = BASE + timedelta(hours=2)
    ticket = await _ticket(db_session, requester, status=TicketStatus.resolved, resolved_at=resolved_at)

    async with SessionLocal() as session:
        assert await auto_close_sweep(session, resolved_at + timedelta(hours=71), cooloff_hours=72) == []

    closed_at = resolved_at + timedelta(hours=72, minutes=1)
    async with SessionLocal() as session:
        assert await auto_close_sweep(session, closed_at, cooloff_hours=72) == [ticket.id]

    async with SessionLocal() as session:
        row = await session.get(Ticket, ticket.id)
        assert row.status is TicketStatus.closed
        assert row.closed_at == closed_at
        audit = await session.scalar(
            select(AuditLog).where(AuditLog.entity_id == ticket.id, AuditLog.action == "ticket.auto_closed")
        )
        assert audit.actor_id is None
