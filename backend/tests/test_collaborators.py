import pytest_asyncio

from app.models.enums import Team
from tests.helpers import auth, create_agent, login, register, seed_reference_data


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _ticket(client, customer_token: str) -> int:
    resp = await client.post(
        "/tickets", json={"subject": "s", "description": "d"}, headers=auth(customer_token)
    )
    return resp.json()["id"]


async def test_add_and_remove_collaborator(client, db_session):
    customer_token = await register(client, "collab-customer@example.com")
    primary = await create_agent(db_session, email="collab-primary@example.com")
    primary_token = await login(client, "collab-primary@example.com")
    helper = await create_agent(db_session, email="collab-helper@example.com")
    ticket_id = await _ticket(client, customer_token)

    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": primary.id}, headers=auth(primary_token))

    added = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token)
    )
    assert added.status_code == 201
    assert added.json() == {"user_id": helper.id, "name": "Agent"}

    detail = (await client.get(f"/tickets/{ticket_id}", headers=auth(primary_token))).json()
    assert detail["collaborators"] == [{"user_id": helper.id, "name": "Agent"}]

    removed = await client.delete(f"/tickets/{ticket_id}/collaborators/{helper.id}", headers=auth(primary_token))
    assert removed.status_code == 204
    detail = (await client.get(f"/tickets/{ticket_id}", headers=auth(primary_token))).json()
    assert detail["collaborators"] == []


async def test_cannot_add_the_primary_assignee_or_a_duplicate(client, db_session):
    customer_token = await register(client, "collab-dup-customer@example.com")
    primary = await create_agent(db_session, email="collab-dup-primary@example.com")
    primary_token = await login(client, "collab-dup-primary@example.com")
    helper = await create_agent(db_session, email="collab-dup-helper@example.com")
    ticket_id = await _ticket(client, customer_token)
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": primary.id}, headers=auth(primary_token))

    same_as_primary = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": primary.id}, headers=auth(primary_token)
    )
    assert same_as_primary.status_code == 409

    first = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token)
    )
    assert first.status_code == 201
    duplicate = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token)
    )
    assert duplicate.status_code == 409


async def test_only_agents_can_be_collaborators(client, db_session):
    customer_token = await register(client, "collab-role-customer@example.com")
    agent_token = await login(client, (await create_agent(db_session, email="collab-role-agent@example.com")).email)
    ticket_id = await _ticket(client, customer_token)
    customer_id = (await client.get("/auth/me", headers=auth(customer_token))).json()["id"]

    resp = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": customer_id}, headers=auth(agent_token)
    )
    assert resp.status_code == 422


async def test_closed_ticket_rejects_collaborator_changes(client, db_session):
    customer_token = await register(client, "collab-closed-customer@example.com")
    agent = await create_agent(db_session, email="collab-closed-agent@example.com")
    agent_token = await login(client, "collab-closed-agent@example.com")
    helper = await create_agent(db_session, email="collab-closed-helper@example.com")
    ticket_id = await _ticket(client, customer_token)
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": agent.id}, headers=auth(agent_token))
    await client.post(f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(agent_token))
    for target in ("in_progress", "resolved", "closed"):
        await client.patch(f"/tickets/{ticket_id}", json={"status": target}, headers=auth(agent_token))

    blocked_add = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": agent.id}, headers=auth(agent_token)
    )
    assert blocked_add.status_code == 409
    blocked_remove = await client.delete(
        f"/tickets/{ticket_id}/collaborators/{helper.id}", headers=auth(agent_token)
    )
    assert blocked_remove.status_code == 409


async def test_end_users_and_missing_collaborators_are_rejected(client, db_session):
    customer_token = await register(client, "collab-403-customer@example.com")
    agent = await create_agent(db_session, email="collab-403-agent@example.com")
    agent_token = await login(client, "collab-403-agent@example.com")
    ticket_id = await _ticket(client, customer_token)

    forbidden = await client.post(
        f"/tickets/{ticket_id}/collaborators", json={"user_id": agent.id}, headers=auth(customer_token)
    )
    assert forbidden.status_code == 403

    not_found = await client.delete(
        f"/tickets/{ticket_id}/collaborators/{agent.id}", headers=auth(agent_token)
    )
    assert not_found.status_code == 404


async def test_mine_filter_matches_collaborators_not_just_the_primary(client, db_session):
    customer_token = await register(client, "collab-mine-customer@example.com")
    primary = await create_agent(db_session, email="collab-mine-primary@example.com")
    primary_token = await login(client, "collab-mine-primary@example.com")
    helper = await create_agent(db_session, email="collab-mine-helper@example.com")
    helper_token = await login(client, "collab-mine-helper@example.com")
    ticket_id = await _ticket(client, customer_token)
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": primary.id}, headers=auth(primary_token))
    await client.post(f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token))

    mine = (await client.get("/tickets?assignee=me", headers=auth(helper_token))).json()
    assert ticket_id in {t["id"] for t in mine["items"]}
    row = next(t for t in mine["items"] if t["id"] == ticket_id)
    assert row["collaborators"] == [{"user_id": helper.id, "name": "Agent"}]


async def test_promoting_a_collaborator_to_primary_drops_them_as_a_collaborator(client, db_session):
    customer_token = await register(client, "collab-promote-customer@example.com")
    primary = await create_agent(db_session, email="collab-promote-primary@example.com")
    primary_token = await login(client, "collab-promote-primary@example.com")
    helper = await create_agent(db_session, email="collab-promote-helper@example.com")
    ticket_id = await _ticket(client, customer_token)
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": primary.id}, headers=auth(primary_token))
    await client.post(f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token))

    resp = await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": helper.id}, headers=auth(primary_token))
    assert resp.status_code == 200
    assert resp.json()["assignee_id"] == helper.id
    assert resp.json()["collaborators"] == []


async def test_escalation_only_touches_the_primary_assignee(client, db_session):
    customer_token = await register(client, "collab-escalate-customer@example.com")
    primary = await create_agent(db_session, email="collab-escalate-primary@example.com")
    primary_token = await login(client, "collab-escalate-primary@example.com")
    helper = await create_agent(db_session, email="collab-escalate-helper@example.com")
    senior = await create_agent(db_session, email="collab-escalate-senior@example.com", team=Team.senior)
    ticket_id = await _ticket(client, customer_token)
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": primary.id}, headers=auth(primary_token))
    await client.post(f"/tickets/{ticket_id}/collaborators", json={"user_id": helper.id}, headers=auth(primary_token))

    resp = await client.patch(f"/tickets/{ticket_id}", json={"escalate": True}, headers=auth(primary_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["assignee_id"] == senior.id
    assert body["collaborators"] == [{"user_id": helper.id, "name": "Agent"}]
