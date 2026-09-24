from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.ai.fake import FakeProvider
from app.models import AuditLog
from app.services.triage import triage_ticket
from tests.helpers import (
    auth,
    create_agent,
    create_ticket,
    freeze,
    login,
    register,
    seed_reference_data,
)

BASE = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _triage_audits(db_session, ticket_id: int) -> list[AuditLog]:
    return list(
        await db_session.scalars(
            select(AuditLog).where(
                AuditLog.entity_id == ticket_id, AuditLog.action == "ticket.ai_triaged"
            )
        )
    )


async def test_worker_triage_applies_category_priority_recomputes_sla_and_audits_as_system(
    client, db_session, monkeypatch
):
    freeze(monkeypatch, BASE)
    token = await register(client, "triage-user@example.com")
    ticket = await create_ticket(client, token, "Locked out", "I can't log in to my account, this is urgent")
    assert (ticket["status"], ticket["priority"], ticket["category"]) == ("new", "normal", None)

    triaged = await triage_ticket(db_session, ticket["id"], FakeProvider())

    assert triaged.status.value == "triaged"
    assert triaged.category == "account-login"
    assert triaged.priority.value == "urgent"
    assert triaged.ai_summary == "Locked out"
    # urgent policy: 15m response / 4h resolution, recomputed from created_at
    assert triaged.sla_response_due == BASE + timedelta(minutes=15)
    assert triaged.sla_resolution_due == BASE + timedelta(hours=4)
    assert triaged.ai_triage["model"] == "fake"
    assert triaged.ai_triage["accepted_fields"] == {"category": "auto", "priority": "auto"}
    assert triaged.ai_triage["suggestion"]["suggested_response_draft"]

    [audit] = await _triage_audits(db_session, ticket["id"])
    assert audit.actor_id is None
    assert audit.diff_json["after"]["status"] == "triaged"

    # A redelivered ticket.created event is a no-op.
    await triage_ticket(db_session, ticket["id"], FakeProvider())
    assert len(await _triage_audits(db_session, ticket["id"])) == 1


async def test_end_user_sees_applied_triage_but_not_the_raw_suggestion(client, db_session):
    token = await register(client, "triage-view@example.com")
    ticket = await create_ticket(client, token, "Refund", "I was charged twice on my invoice")
    await triage_ticket(db_session, ticket["id"], FakeProvider())

    view = (await client.get(f"/tickets/{ticket['id']}", headers=auth(token))).json()
    assert (view["category"], view["priority"], view["status"]) == ("billing", "high", "triaged")
    assert "ai_triage" not in view

    listed = (await client.get("/tickets", headers=auth(token))).json()["items"]
    assert listed[0]["category"] == "billing"


async def test_rerun_on_a_later_status_stores_suggestion_without_touching_fields(client, db_session):
    token = await register(client, "rerun-user@example.com")
    agent = await create_agent(db_session, email="rerun-agent@example.com")
    agent_token = await login(client, "rerun-agent@example.com")
    ticket = await create_ticket(client, token, "Question", "How do I export my data?")
    tid = ticket["id"]

    for patch in ({"status": "triaged"}, {"assignee_id": agent.id}, {"status": "open"}, {"category": "other"}):
        assert (await client.patch(f"/tickets/{tid}", json=patch, headers=auth(agent_token))).status_code == 200

    resp = await client.post(f"/tickets/{tid}/ai-triage", headers=auth(agent_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "open"
    assert body["category"] == "other"  # the agent's choice survives
    assert body["ai_triage"]["suggestion"]["category"] == "data-privacy"
    assert body["ai_triage"]["accepted_fields"] == {}
    [audit] = await _triage_audits(db_session, tid)
    assert audit.actor_id == agent.id

    assert (await client.post(f"/tickets/{tid}/ai-triage", headers=auth(token))).status_code == 403


async def test_accept_and_override_are_recorded(client, db_session):
    token = await register(client, "accept-user@example.com")
    await create_agent(db_session, email="accept-agent@example.com")
    agent_token = await login(client, "accept-agent@example.com")
    ticket = await create_ticket(client, token, "Charged twice", "Charged twice on my card")
    tid = ticket["id"]

    # No triage yet: nothing to accept.
    resp = await client.patch(f"/tickets/{tid}", json={"ai_accept": ["category"]}, headers=auth(agent_token))
    assert resp.status_code == 409

    await triage_ticket(db_session, tid, FakeProvider())

    resp = await client.patch(
        f"/tickets/{tid}", json={"ai_accept": ["category", "suggested_response_draft"]}, headers=auth(agent_token)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["category"] == "billing"
    assert body["ai_triage"]["accepted_fields"] == {
        "category": "accepted",
        "priority": "auto",
        "suggested_response_draft": "accepted",
    }
    assert body["audit_log"][-1]["diff_json"]["after"]["ai_accepted_fields"]["category"] == "accepted"

    resp = await client.patch(f"/tickets/{tid}", json={"priority": "low"}, headers=auth(agent_token))
    body = resp.json()
    assert body["priority"] == "low"
    assert body["ai_triage"]["accepted_fields"]["priority"] == "overridden"

    resp = await client.patch(
        f"/tickets/{tid}", json={"ai_accept": ["priority"], "priority": "urgent"}, headers=auth(agent_token)
    )
    assert resp.status_code == 422


class _AgentEditsDuringCall(FakeProvider):
    """Simulates an agent PATCHing the ticket while the model call is in flight."""

    def __init__(self, ticket_id: int):
        self.ticket_id = ticket_id

    async def triage(self, **kwargs):
        from app.db import SessionLocal
        from app.models import Ticket
        from app.models.enums import TicketPriority

        async with SessionLocal() as other:
            ticket = await other.get(Ticket, self.ticket_id)
            ticket.priority = TicketPriority.urgent
            await other.commit()
        return await super().triage(**kwargs)


async def test_worker_triage_never_overwrites_a_field_the_agent_changed_mid_call(client, db_session):
    token = await register(client, "race-user@example.com")
    ticket = await create_ticket(client, token, "Invoice", "How do I download my invoice?")

    triaged = await triage_ticket(db_session, ticket["id"], _AgentEditsDuringCall(ticket["id"]))

    assert triaged.priority.value == "urgent"  # the agent's choice, not the suggested "low"
    assert triaged.ai_triage["suggestion"]["priority"] == "low"
    assert triaged.category == "billing"  # untouched by the agent, so applied
    assert triaged.ai_triage["accepted_fields"] == {"category": "auto"}
    assert triaged.status.value == "triaged"


async def test_rerun_keeps_decisions_whose_suggestion_did_not_change(client, db_session):
    token = await register(client, "keep-user@example.com")
    await create_agent(db_session, email="keep-agent@example.com")
    agent_token = await login(client, "keep-agent@example.com")
    ticket = await create_ticket(client, token, "Charged twice", "Charged twice on my card")
    tid = ticket["id"]
    await triage_ticket(db_session, tid, FakeProvider())
    await client.patch(f"/tickets/{tid}", json={"ai_accept": ["category"]}, headers=auth(agent_token))

    body = (await client.post(f"/tickets/{tid}/ai-triage", headers=auth(agent_token))).json()
    assert body["ai_triage"]["accepted_fields"] == {"category": "accepted", "priority": "auto"}


async def test_worker_reclaims_entries_left_pending_by_a_dead_consumer(client, db_session, monkeypatch):
    from app import worker
    from app.redis_client import get_redis

    redis = get_redis()
    await redis.delete(worker.STREAM)
    await redis.xgroup_create(worker.STREAM, worker.GROUP, id="0", mkstream=True)
    try:
        token = await register(client, "reclaim-user@example.com")
        # create_ticket publishes ticket.created to the (test) stream.
        ticket = await create_ticket(client, token, "Locked out", "I can't log in")
        # A consumer that read it and then died (e.g. a recreated container).
        await redis.xreadgroup(worker.GROUP, "dead-container", {worker.STREAM: ">"}, count=10)
        assert (await redis.xpending(worker.STREAM, worker.GROUP))["pending"] == 1

        monkeypatch.setattr(worker, "RECLAIM_IDLE_MS", 0)
        await worker._reclaim_stale()

        assert (await redis.xpending(worker.STREAM, worker.GROUP))["pending"] == 0
        view = (await client.get(f"/tickets/{ticket['id']}", headers=auth(token))).json()
        assert (view["status"], view["category"]) == ("triaged", "account-login")
    finally:
        await redis.delete(worker.STREAM)
