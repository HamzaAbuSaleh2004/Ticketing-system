from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.domain import clock
from app.models import AuditLog, User
from app.models.enums import Team
from tests.helpers import create_agent, login, register_full

BASE = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


def _freeze(monkeypatch, when: datetime) -> None:
    monkeypatch.setattr(clock, "now", lambda: when)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email: str, name: str = "Test User", password: str = "Password123!"):
    body = await register_full(client, email, password, name)
    return body["access_token"], body["user"]


async def _create_agent(db_session, *, email: str, team: Team = Team.tier1, password: str = "Secret123!") -> User:
    return await create_agent(db_session, email=email, team=team, password=password)


async def _login(client, email: str, password: str) -> str:
    return await login(client, email, password)


async def _audit_count(db_session, ticket_id: int) -> int:
    result = await db_session.scalar(
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket_id)
    )
    return result or 0


async def test_full_lifecycle_walk_and_follow_up(client, db_session, monkeypatch):
    _freeze(monkeypatch, BASE)

    customer_token, _ = await _register(client, "customer@example.com")
    agent = await _create_agent(db_session, email="agent-walk@example.com")
    agent_token = await _login(client, "agent-walk@example.com", "Secret123!")

    create_resp = await client.post(
        "/tickets",
        json={"subject": "Can't log in", "description": "Locked out of my account"},
        headers=_auth(customer_token),
    )
    assert create_resp.status_code == 201
    ticket = create_resp.json()
    ticket_id = ticket["id"]
    assert ticket["status"] == "open"
    assert ticket["priority"] == "normal"

    audit_count = await _audit_count(db_session, ticket_id)
    assert audit_count == 1  # ticket.created

    # open -> in_progress with no assignee is rejected, with the allowed set in the body
    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"}, headers=_auth(agent_token))
    assert resp.status_code == 409
    assert resp.json()["detail"]["allowed"] == ["in_progress"]
    assert await _audit_count(db_session, ticket_id) == audit_count  # rejected, no new row

    # assign, then in_progress succeeds
    resp = await client.patch(
        f"/tickets/{ticket_id}", json={"assignee_id": agent.id}, headers=_auth(agent_token)
    )
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count

    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count

    # agent's first public reply sets first_responded_at
    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": "Looking into it", "is_internal_note": False},
        headers=_auth(agent_token),
    )
    assert resp.status_code == 201
    detail = (await client.get(f"/tickets/{ticket_id}", headers=_auth(agent_token))).json()
    assert detail["first_responded_at"] is not None

    # in_progress -> pending
    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "pending"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count

    # 2 hours later, pending -> in_progress
    resumed_at = BASE + timedelta(hours=2)
    _freeze(monkeypatch, resumed_at)
    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "in_progress"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count

    # in_progress -> resolved
    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count
    assert resp.json()["resolved_at"] is not None

    # customer reply within the cooling-off window reopens the same ticket
    reply_time = resumed_at + timedelta(hours=1)
    _freeze(monkeypatch, reply_time)
    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": "Still broken", "is_internal_note": False},
        headers=_auth(customer_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["follow_up_ticket_id"] is None
    assert body["comment"]["body"] == "Still broken"
    audit_count += 1  # ticket.reopened_by_reply
    assert await _audit_count(db_session, ticket_id) == audit_count

    detail = (await client.get(f"/tickets/{ticket_id}", headers=_auth(agent_token))).json()
    assert detail["status"] == "in_progress"
    assert detail["resolved_at"] is None

    # resolved again, then closed
    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "resolved"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count

    resp = await client.patch(f"/tickets/{ticket_id}", json={"status": "closed"}, headers=_auth(agent_token))
    assert resp.status_code == 200
    audit_count += 1
    assert await _audit_count(db_session, ticket_id) == audit_count
    assert resp.json()["closed_at"] is not None

    # a reply on a closed ticket creates a linked follow-up, and leaves the original untouched
    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": "New, unrelated problem", "is_internal_note": False},
        headers=_auth(customer_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["comment"] is None
    follow_up_id = body["follow_up_ticket_id"]
    assert follow_up_id is not None and follow_up_id != ticket_id
    assert await _audit_count(db_session, ticket_id) == audit_count  # original ticket's trail unchanged

    original_after = (await client.get(f"/tickets/{ticket_id}", headers=_auth(agent_token))).json()
    assert original_after["status"] == "closed"

    follow_up = (await client.get(f"/tickets/{follow_up_id}", headers=_auth(agent_token))).json()
    assert follow_up["parent_ticket_id"] == ticket_id
    assert follow_up["status"] == "open"
    assert follow_up["description"] == "New, unrelated problem"


async def test_end_user_gets_404_on_another_users_ticket(client, db_session):
    owner_token, _ = await _register(client, "owner@example.com")
    other_token, _ = await _register(client, "other@example.com")

    create_resp = await client.post(
        "/tickets", json={"subject": "Billing question", "description": "Why was I charged?"},
        headers=_auth(owner_token),
    )
    ticket_id = create_resp.json()["id"]

    resp = await client.get(f"/tickets/{ticket_id}", headers=_auth(other_token))
    assert resp.status_code == 404

    resp = await client.get("/tickets", headers=_auth(other_token))
    assert resp.status_code == 200
    assert all(item["id"] != ticket_id for item in resp.json()["items"])


async def test_end_user_never_receives_internal_notes(client, db_session):
    customer_token, _ = await _register(client, "notes-customer@example.com")
    await _create_agent(db_session, email="notes-agent@example.com")
    agent_token = await _login(client, "notes-agent@example.com", "Secret123!")

    create_resp = await client.post(
        "/tickets", json={"subject": "Slow dashboard", "description": "It's slow"},
        headers=_auth(customer_token),
    )
    ticket_id = create_resp.json()["id"]

    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": "Customer seems confused, escalating internally", "is_internal_note": True},
        headers=_auth(agent_token),
    )
    assert resp.status_code == 201

    # an end user can't post an internal note either
    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        json={"body": "trying", "is_internal_note": True},
        headers=_auth(customer_token),
    )
    assert resp.status_code == 403

    as_customer = (await client.get(f"/tickets/{ticket_id}", headers=_auth(customer_token))).json()
    assert as_customer["comments"] == []
    for agent_only in ("audit_log", "allowed_transitions"):
        assert agent_only not in as_customer

    as_agent = (await client.get(f"/tickets/{ticket_id}", headers=_auth(agent_token))).json()
    assert len(as_agent["comments"]) == 1
    assert as_agent["comments"][0]["is_internal_note"] is True
    assert as_agent["audit_log"] is not None
    assert len(as_agent["audit_log"]) >= 1


async def test_escalate_bumps_priority_and_reassigns_to_least_loaded_senior(client, db_session, monkeypatch):
    _freeze(monkeypatch, BASE)
    customer_token, _ = await _register(client, "escalate-customer@example.com")
    senior = await _create_agent(db_session, email="senior1@example.com", team=Team.senior)
    agent_token = await _login(client, "senior1@example.com", "Secret123!")

    create_resp = await client.post(
        "/tickets", json={"subject": "Data loss", "description": "My data is gone"},
        headers=_auth(customer_token),
    )
    ticket_id = create_resp.json()["id"]
    assert create_resp.json()["priority"] == "normal"

    resp = await client.patch(f"/tickets/{ticket_id}", json={"escalate": True}, headers=_auth(agent_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == "high"
    assert body["escalated"] is True
    assert body["assignee_id"] == senior.id


async def test_cannot_escalate_a_closed_ticket(client, db_session, monkeypatch):
    _freeze(monkeypatch, BASE)
    customer_token, _ = await _register(client, "closed-escalate@example.com")
    agent = await _create_agent(db_session, email="closer1@example.com")
    agent_token = await _login(client, "closer1@example.com", "Secret123!")

    create_resp = await client.post(
        "/tickets", json={"subject": "Old issue", "description": "Long resolved"},
        headers=_auth(customer_token),
    )
    ticket_id = create_resp.json()["id"]

    for target in (None, "in_progress", "resolved", "closed"):
        if target is None:
            await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": agent.id}, headers=_auth(agent_token))
            continue
        resp = await client.patch(f"/tickets/{ticket_id}", json={"status": target}, headers=_auth(agent_token))
        assert resp.status_code == 200, resp.text

    resp = await client.patch(f"/tickets/{ticket_id}", json={"escalate": True}, headers=_auth(agent_token))
    assert resp.status_code == 409


async def test_thread_carries_author_names_and_categories_are_listed(client, db_session):
    from app.models import Category

    db_session.add(Category(name="Billing", slug="billing", active=True))
    await db_session.commit()
    customer_token, _ = await _register(client, "names-customer@example.com", name="Uma Customer")
    await _create_agent(db_session, email="names-agent@example.com")
    agent_token = await _login(client, "names-agent@example.com", "Secret123!")
    ticket_id = (
        await client.post("/tickets", json={"subject": "Hi", "description": "Help"}, headers=_auth(customer_token))
    ).json()["id"]

    posted = await client.post(
        f"/tickets/{ticket_id}/comments", json={"body": "On it"}, headers=_auth(agent_token)
    )
    assert posted.json()["comment"]["author_name"] == "Agent"
    await client.post(f"/tickets/{ticket_id}/comments", json={"body": "Thanks"}, headers=_auth(customer_token))

    thread = (await client.get(f"/tickets/{ticket_id}", headers=_auth(customer_token))).json()["comments"]
    assert [(c["author_name"], c["author_role"]) for c in thread] == [("Agent", "agent"), ("Uma Customer", "end_user")]

    cats = (await client.get("/categories", headers=_auth(customer_token))).json()
    assert cats == [{"id": cats[0]["id"], "name": "Billing", "slug": "billing", "active": True}]
    assert (await client.get("/categories")).status_code == 401


async def test_customers_see_staff_first_names_and_reopen_window(client, db_session, monkeypatch):
    _freeze(monkeypatch, BASE)
    customer_token, _ = await _register(client, "first-name@example.com")
    agent = await _create_agent(db_session, email="first-agent@example.com")
    agent.name = "Tara Tier1"
    await db_session.commit()
    agent_token = await _login(client, "first-agent@example.com", "Secret123!")
    tid = (await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=_auth(customer_token))).json()["id"]
    await client.post(f"/tickets/{tid}/comments", json={"body": "Hi"}, headers=_auth(agent_token))

    as_customer = (await client.get(f"/tickets/{tid}", headers=_auth(customer_token))).json()
    as_agent = (await client.get(f"/tickets/{tid}", headers=_auth(agent_token))).json()
    assert as_customer["comments"][0]["author_name"] == "Tara"
    assert as_agent["comments"][0]["author_name"] == "Tara Tier1"
    assert as_customer["reopen_until"] is None

    for patch in ({"assignee_id": agent.id}, {"status": "in_progress"}, {"status": "resolved"}):
        assert (await client.patch(f"/tickets/{tid}", json=patch, headers=_auth(agent_token))).status_code == 200
    resolved = (await client.get(f"/tickets/{tid}", headers=_auth(customer_token))).json()
    assert datetime.fromisoformat(resolved["reopen_until"]) == BASE + timedelta(hours=72)


async def test_agent_queue_rows_carry_names_end_users_dont(client, db_session, monkeypatch):
    _freeze(monkeypatch, BASE)
    customer_token, _ = await _register(client, "queue-customer@example.com", name="Quinn Customer")
    agent = await _create_agent(db_session, email="queue-agent@example.com")
    agent_token = await _login(client, "queue-agent@example.com", "Secret123!")
    first = (await client.post("/tickets", json={"subject": "a", "description": "d"}, headers=_auth(customer_token))).json()["id"]
    second = (await client.post("/tickets", json={"subject": "b", "description": "d"}, headers=_auth(customer_token))).json()["id"]
    for patch in ({"assignee_id": agent.id}, {"status": "in_progress"}):
        await client.patch(f"/tickets/{first}", json=patch, headers=_auth(agent_token))
    await client.patch(f"/tickets/{second}", json={"priority": "urgent"}, headers=_auth(agent_token))

    queue = (await client.get("/tickets?status=in_progress&status=open", headers=_auth(agent_token))).json()
    rows = {r["id"]: r for r in queue["items"]}
    assert set(rows) == {first, second}
    assert rows[first]["requester_name"] == "Quinn Customer"
    assert rows[first]["assignee_name"] == "Agent"

    mine = (await client.get("/tickets", headers=_auth(customer_token))).json()["items"]
    assert {"requester_name", "assignee_name"}.isdisjoint(mine[0])

    detail = (await client.get(f"/tickets/{first}", headers=_auth(agent_token))).json()
    assert (detail["requester_name"], detail["requester_email"], detail["assignee_name"]) == (
        "Quinn Customer", "queue-customer@example.com", "Agent",
    )
    assert detail["audit_log"][0]["actor_name"] == "Quinn Customer"

    staff = (await client.get("/users/staff", headers=_auth(agent_token))).json()
    assert [s["email"] for s in staff] == ["queue-agent@example.com"]
    assert (await client.get("/users/staff", headers=_auth(customer_token))).status_code == 403
