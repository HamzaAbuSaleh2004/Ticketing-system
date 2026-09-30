from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog, Organization, Ticket
from app.models.enums import OrganizationKind, TicketPriority, TicketStatus, UserRole
from tests.helpers import (
    auth,
    create_agent,
    create_user,
    freeze,
    login,
    register,
    seed_reference_data,
)

NOW = datetime(2026, 6, 10, 12, 0, tzinfo=UTC)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, tzinfo=UTC)


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _admin(client, db_session) -> str:
    await create_user(db_session, email="boss@example.com", name="Boss", role=UserRole.admin)
    return await login(client, "boss@example.com")


async def _dataset(db_session, requester_id: int, org_a_id: int, org_b_id: int) -> None:
    """Hand-computed expectations are in the test below."""
    def ticket(**f) -> Ticket:
        base = {"subject": "s", "description": "d", "priority": TicketPriority.normal, "requester_id": requester_id}
        return Ticket(**(base | f))

    db_session.add_all([
        # T1: replied in 10m; resolved after 4h of which 1h paused -> 3h; on time.
        ticket(status=TicketStatus.closed, created_at=at(1, 9), first_responded_at=at(1, 9, 10),
               sla_response_due=at(1, 9, 15), resolved_at=at(1, 13), sla_resolution_due=at(1, 17),
               sla_paused_total_seconds=3600, closed_at=at(1, 14)),
        # T2: replied in 20m (response breached); resolved after 24h (resolution breached).
        ticket(status=TicketStatus.resolved, created_at=at(1, 10), first_responded_at=at(1, 10, 20),
               sla_response_due=at(1, 10, 15), resolved_at=at(2, 10), sla_resolution_due=at(1, 14)),
        # T3: replied in 1h; still running past its resolution due -> resolution breached. Org A.
        ticket(status=TicketStatus.in_progress, created_at=at(2, 8), first_responded_at=at(2, 9),
               sla_response_due=at(2, 12), sla_resolution_due=at(3, 8), organization_id=org_a_id),
        # T4: never replied, both clocks past due -> both breached. Org B.
        ticket(status=TicketStatus.open, created_at=at(3, 8), sla_response_due=at(3, 8, 15), sla_resolution_due=at(4, 8),
               organization_id=org_b_id),
        # T5: replied in 5m; paused before its resolution due -> not breached although "now" is later. Org A.
        ticket(status=TicketStatus.pending, created_at=at(3, 9), first_responded_at=at(3, 9, 5),
               sla_response_due=at(3, 9, 15), sla_resolution_due=at(3, 17), sla_paused_at=at(3, 10),
               organization_id=org_a_id),
        # T6: outside the window; only counts toward the current backlog. No organisation.
        ticket(status=TicketStatus.open, created_at=datetime(2026, 5, 20, 9, tzinfo=UTC),
               sla_response_due=datetime(2026, 5, 20, 13, tzinfo=UTC), sla_resolution_due=datetime(2026, 5, 21, 9, tzinfo=UTC),
               first_responded_at=datetime(2026, 5, 20, 9, 30, tzinfo=UTC)),
    ])
    await db_session.commit()


async def test_analytics_summary_math_on_a_fixed_dataset(client, db_session, monkeypatch):
    freeze(monkeypatch, NOW)
    user_token = await register(client, "analytics-user@example.com")
    requester_id = (await client.get("/auth/me", headers=auth(user_token))).json()["id"]
    org_a = Organization(name="Acme Corp", kind=OrganizationKind.company)
    org_b = Organization(name="Ministry of Roads", kind=OrganizationKind.government)
    db_session.add_all([org_a, org_b])
    await db_session.commit()
    await _dataset(db_session, requester_id, org_a.id, org_b.id)
    await create_agent(db_session, email="analytics-agent@example.com")
    agent_token = await login(client, "analytics-agent@example.com")

    resp = await client.get("/analytics/summary?from=2026-06-01&to=2026-06-03", headers=auth(agent_token))
    assert resp.status_code == 200
    s = resp.json()

    assert s["created"] == 5
    assert [(d["date"], d["count"]) for d in s["volume"]] == [("2026-06-01", 2), ("2026-06-02", 1), ("2026-06-03", 2)]
    # First responses: 300, 600, 1200, 3600 seconds.
    assert s["first_response"] == {"median_seconds": 900.0, "avg_seconds": 1425.0, "count": 4}
    # Resolutions excluding paused time: 3h (4h - 1h paused) and 24h.
    assert s["resolution"] == {"median_seconds": 48600.0, "avg_seconds": 48600.0, "count": 2}
    assert {b["status"]: b["count"] for b in s["backlog"]} == {"open": 2, "in_progress": 1, "pending": 1}
    assert s["sla_breaches"] == {"total": 3, "response": 2, "resolution": 3}
    # Backlog by organisation: Org A has T3+T5 (in_progress+pending), Org B
    # has T4 (open), and T6 (open) has no organisation - always present even
    # though a busy top 10 could otherwise push it out.
    assert [(o["name"], o["count"]) for o in s["backlog_by_organization"]] == [
        ("Acme Corp", 2), ("Ministry of Roads", 1), ("No organisation", 1),
    ]

    # Default range: the 30 days ending today (frozen clock), zero-filled.
    default = (await client.get("/analytics/summary", headers=auth(agent_token))).json()
    assert (default["from_date"], default["to_date"], len(default["volume"])) == ("2026-05-12", "2026-06-10", 30)
    assert default["created"] == 6

    assert (await client.get("/analytics/summary?from=2026-06-05&to=2026-06-01", headers=auth(agent_token))).status_code == 422
    assert (await client.get("/analytics/summary", headers=auth(user_token))).status_code == 403


async def test_admin_edits_users_categories_and_sla_policies_all_audited(client, db_session):
    admin_token = await _admin(client, db_session)
    agent = await create_agent(db_session, email="promote-me@ticketing.demo")
    agent_token = await login(client, "promote-me@ticketing.demo")
    boss_id = (await client.get("/auth/me", headers=auth(admin_token))).json()["id"]

    # Users: role/team edits, team cleared for non-agents, no self-demotion.
    resp = await client.patch(f"/users/{agent.id}", json={"team": "senior"}, headers=auth(admin_token))
    assert resp.json()["team"] == "senior"
    resp = await client.patch(f"/users/{agent.id}", json={"role": "end_user"}, headers=auth(admin_token))
    assert (resp.json()["role"], resp.json()["team"]) == ("end_user", None)
    resp = await client.patch(f"/users/{agent.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert (resp.json()["role"], resp.json()["team"]) == ("agent", "tier1")
    assert (await client.patch(f"/users/{boss_id}", json={"role": "agent"}, headers=auth(admin_token))).status_code == 409
    assert len((await client.get("/users", headers=auth(admin_token))).json()) == 2

    # Categories: create (slugged), duplicate 409, rename + deactivate keeps the slug.
    created = await client.post("/categories", json={"name": "Shipping & delivery"}, headers=auth(admin_token))
    assert created.status_code == 201 and created.json()["slug"] == "shipping-delivery"
    assert (await client.post("/categories", json={"name": "Shipping & Delivery"}, headers=auth(admin_token))).status_code == 409
    cat_id = created.json()["id"]
    patched = await client.patch(f"/categories/{cat_id}", json={"active": False, "name": "Shipping"}, headers=auth(admin_token))
    assert patched.json() == {"id": cat_id, "name": "Shipping", "slug": "shipping-delivery", "active": False}

    # SLA policies: edit minutes, validation, urgent listed first (global defaults only).
    policies = (await client.get("/sla-policies", headers=auth(agent_token))).json()
    assert [p["priority"] for p in policies] == ["urgent", "high", "normal", "low"]
    resp = await client.patch("/sla-policies/high", json={"response_minutes": 30, "resolution_minutes": 360}, headers=auth(admin_token))
    assert (resp.json()["response_minutes"], resp.json()["resolution_minutes"]) == (30, 360)
    bad = await client.patch("/sla-policies/high", json={"response_minutes": 600, "resolution_minutes": 60}, headers=auth(admin_token))
    assert bad.status_code == 422

    # Non-admins can't change anything.
    for method, path, body in [
        ("patch", f"/users/{agent.id}", {"team": "senior"}),
        ("post", "/categories", {"name": "Nope"}),
        ("patch", "/sla-policies/low", {"response_minutes": 1, "resolution_minutes": 2}),
    ]:
        assert (await getattr(client, method)(path, json=body, headers=auth(agent_token))).status_code == 403

    # Every change is in the audit log, with before/after.
    rows = (await db_session.scalars(select(AuditLog).order_by(AuditLog.id))).all()
    actions = [r.action for r in rows]
    assert actions.count("user.updated") == 3
    assert actions.count("category.created") == 1 and actions.count("category.updated") == 1
    assert actions.count("sla_policy.updated") == 1
    sla_row = next(r for r in rows if r.action == "sla_policy.updated")
    assert sla_row.diff_json["before"] == {"response_minutes": 60, "resolution_minutes": 480}
    assert all(r.actor_id == boss_id for r in rows)

    feed = (await client.get("/admin/audit", headers=auth(admin_token))).json()
    assert feed[0]["action"] == "sla_policy.updated" and feed[0]["actor_name"] == "Boss"
    assert (await client.get("/admin/audit", headers=auth(agent_token))).status_code == 403


async def test_new_tickets_use_the_edited_policy_existing_ones_keep_theirs(client, db_session, monkeypatch):
    freeze(monkeypatch, NOW)
    admin_token = await _admin(client, db_session)
    user_token = await register(client, "policy-user@example.com")
    before = (await client.post("/tickets", json={"subject": "a", "description": "d"}, headers=auth(user_token))).json()
    await client.patch("/sla-policies/normal", json={"response_minutes": 30, "resolution_minutes": 120}, headers=auth(admin_token))
    after = (await client.post("/tickets", json={"subject": "b", "description": "d"}, headers=auth(user_token))).json()

    assert datetime.fromisoformat(after["sla_response_due"]) == NOW + timedelta(minutes=30)
    refetched = (await client.get(f"/tickets/{before['id']}", headers=auth(user_token))).json()
    assert datetime.fromisoformat(refetched["sla_response_due"]) == NOW + timedelta(hours=4)


async def test_admin_validation_and_readable_change_log(client, db_session):
    admin_token = await _admin(client, db_session)
    agent = await create_agent(db_session, email="holder@example.com")
    user_token = await register(client, "holder-customer@example.com")

    # Explicit null role is ignored, not a 500.
    resp = await client.patch(f"/users/{agent.id}", json={"role": None}, headers=auth(admin_token))
    assert resp.status_code == 200 and resp.json()["role"] == "agent"

    # Can't demote someone still holding open tickets.
    tid = (await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=auth(user_token))).json()["id"]
    await client.patch(f"/tickets/{tid}", json={"assignee_id": agent.id}, headers=auth(admin_token))
    blocked = await client.patch(f"/users/{agent.id}", json={"role": "end_user"}, headers=auth(admin_token))
    assert blocked.status_code == 409 and "1 open ticket" in blocked.json()["detail"]

    # Blank names are rejected after trimming, on create and rename.
    assert (await client.post("/categories", json={"name": "   "}, headers=auth(admin_token))).status_code == 422
    cat = (await client.post("/categories", json={"name": "  Refunds  "}, headers=auth(admin_token))).json()
    assert cat["name"] == "Refunds"
    assert (await client.patch(f"/categories/{cat['id']}", json={"name": "  "}, headers=auth(admin_token))).status_code == 422

    await client.patch("/sla-policies/urgent", json={"response_minutes": 10, "resolution_minutes": 200}, headers=auth(admin_token))
    feed = (await client.get("/admin/audit", headers=auth(admin_token))).json()
    assert [(f["entity_type"], f["subject"]) for f in feed[:2]] == [("sla_policy", "urgent"), ("category", "Refunds")]
