from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.db import SessionLocal
from app.models import AuditLog, Ticket
from app.models.enums import TicketPriority, TicketStatus
from app.services.sweeps import auto_close_sweep
from app.services.tickets import lock_ticket
from tests.helpers import register, seed_reference_data

BASE = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _ticket(db_session, requester_id: int, **fields) -> Ticket:
    values = {
        "subject": "s",
        "description": "d",
        "status": TicketStatus.in_progress,
        "priority": TicketPriority.high,
        "requester_id": requester_id,
        "created_at": BASE,
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
