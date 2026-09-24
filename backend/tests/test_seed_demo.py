import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import seed as seed_module
from app.config import Settings
from app.domain import clock
from app.models import AuditLog, SlaPolicy, Ticket, TicketComment
from app.models.enums import TicketPriority, TicketStatus
from app.seed_demo import seed_demo_tickets
from app.services.sweeps import auto_close_sweep, sla_risk_sweep, ticket_at_risk

NOW = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
DEMO_FILE = "/demo-data/tickets.json"

pytestmark = pytest.mark.skipif(not Path(DEMO_FILE).is_file(), reason="docs/demo-data is mounted at /demo-data by compose")


def _raw() -> dict[str, dict]:
    return {t["ref"]: t for t in json.loads(Path(DEMO_FILE).read_text(encoding="utf-8"))["tickets"]}


async def _seed(db_session, monkeypatch):
    monkeypatch.setattr(clock, "now", lambda: NOW)
    await seed_module.seed_users(db_session)
    await seed_module.seed_sla_policies(db_session)
    await seed_module.seed_categories(db_session)
    return await seed_demo_tickets(db_session, DEMO_FILE)


async def test_demo_seed_maps_the_file_as_its_readme_specifies(db_session, monkeypatch):
    assert await _seed(db_session, monkeypatch) == 25
    assert await seed_demo_tickets(db_session, DEMO_FILE) == 0  # never re-seeds

    raw = _raw()
    tickets = {t.subject: t for t in await db_session.scalars(select(Ticket))}
    policies = {p.priority: p for p in await db_session.scalars(select(SlaPolicy))}
    by_ref = {ref: tickets[r["subject"]] for ref, r in raw.items()}

    assert {t.status for t in tickets.values()} == set(TicketStatus)
    assert {t.priority for t in tickets.values()} == set(TicketPriority)

    for ref, r in raw.items():
        t = by_ref[ref]
        created = NOW - timedelta(minutes=r["created_minutes_ago"])
        assert t.created_at == created
        policy = policies[t.priority]
        assert t.sla_response_due == created + timedelta(minutes=policy.response_minutes)
        extra = timedelta(minutes=r.get("pending_minutes", 0)) if t.status is not TicketStatus.pending else timedelta()
        assert t.sla_resolution_due == created + timedelta(minutes=policy.resolution_minutes) + extra
        if t.status is TicketStatus.pending:
            assert t.sla_paused_at == NOW - timedelta(minutes=r["pending_minutes"]) and t.sla_paused_total_seconds == 0
        agent_public = [c for c in r.get("comments", []) if not c["is_internal_note"] and c["author_email"].startswith("agent")]
        expected_first = NOW - timedelta(minutes=max(c["minutes_ago"] for c in agent_public)) if agent_public else None
        assert t.first_responded_at == expected_first
        assert t.escalated is bool(r.get("escalated"))

    assert by_ref["t25"].parent_ticket_id == by_ref["t24"].id
    assert by_ref["t01"].category is None and by_ref["t01"].priority is TicketPriority.normal

    notes = await db_session.scalar(select(func.count()).select_from(TicketComment).where(TicketComment.is_internal_note.is_(True)))
    assert notes == sum(c["is_internal_note"] for r in raw.values() for c in r.get("comments", []))
    audits = (await db_session.scalars(select(AuditLog))).all()
    assert len(audits) == 25 and all(a.actor_id is None and a.action == "ticket.created" for a in audits)
    assert {a.entity_id: a.created_at for a in audits}[by_ref["t24"].id] == by_ref["t24"].created_at


async def test_demo_data_is_stable_under_the_worker_sweeps(db_session, monkeypatch):
    await _seed(db_session, monkeypatch)
    # README: no non-escalated urgent/high ticket is at risk, and no resolved ticket is past the window.
    assert await sla_risk_sweep(db_session, NOW) == []
    assert await auto_close_sweep(db_session, NOW, cooloff_hours=72) == []
    at_risk = [t.subject for t in await db_session.scalars(select(Ticket)) if ticket_at_risk(t, NOW)]
    assert len(at_risk) >= 3  # t04, t13, t08 (+ escalated breached ones)


def test_seed_demo_defaults_to_local_only():
    assert Settings(ENV="local").seed_demo is True
    assert Settings(ENV="prod", JWT_SECRET="x" * 32).seed_demo is False
    assert Settings(ENV="prod", JWT_SECRET="x" * 32, SEED_DEMO=True).seed_demo is True
