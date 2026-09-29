import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog, Organization, User
from app.models.enums import OrganizationKind, UserRole
from tests.helpers import (
    auth,
    create_agent,
    create_user,
    login,
    register,
    seed_reference_data,
)


@pytest_asyncio.fixture(autouse=True)
async def _reference_data(db_session):
    await seed_reference_data(db_session)


async def _org(db_session, name: str = "Acme Corp", kind: OrganizationKind = OrganizationKind.company) -> Organization:
    org = Organization(name=name, kind=kind)
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


async def test_agent_creates_a_ticket_for_an_existing_customer(client, db_session):
    org = await _org(db_session)
    customer = await create_user(db_session, email="known@example.com", role=UserRole.end_user, organization_id=org.id)
    await create_agent(db_session, email="creator1@example.com")
    agent_token = await login(client, "creator1@example.com")

    resp = await client.post(
        "/tickets",
        json={"subject": "Called in", "description": "They called about a login issue.", "requester_id": customer.id},
        headers=auth(agent_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["requester_id"] == customer.id
    assert body["requester_name"] == "Test User"
    assert body["organization_id"] == org.id
    assert body["organization_name"] == "Acme Corp"

    # The customer can see it themselves.
    customer_token = await login(client, "known@example.com")
    mine = await client.get("/tickets", headers=auth(customer_token))
    assert [t["subject"] for t in mine.json()["items"]] == ["Called in"]


async def test_agent_creates_an_unclaimed_ticket_with_only_an_organization(client, db_session):
    org = await _org(db_session, "Ministry of Roads", OrganizationKind.government)
    await create_agent(db_session, email="creator2@example.com")
    agent_token = await login(client, "creator2@example.com")

    resp = await client.post(
        "/tickets",
        json={"subject": "Phone call", "description": "Caller from the ministry, no account yet.", "organization_id": org.id},
        headers=auth(agent_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["requester_id"] is None
    assert body["requester_name"] is None
    assert body["organization_id"] == org.id
    ticket_id = body["id"]

    # Invisible to every end user until claimed.
    other_customer_token = await register(client, "other-customer@example.com")
    assert (await client.get(f"/tickets/{ticket_id}", headers=auth(other_customer_token))).status_code == 404

    # Shows up in the queue for staff.
    queue = await client.get("/tickets", headers=auth(agent_token))
    assert any(t["id"] == ticket_id for t in queue.json()["items"])


async def test_creating_a_ticket_without_requester_or_organization_is_a_422(client, db_session):
    await create_agent(db_session, email="creator3@example.com")
    agent_token = await login(client, "creator3@example.com")
    resp = await client.post(
        "/tickets", json={"subject": "s", "description": "d"}, headers=auth(agent_token)
    )
    assert resp.status_code == 422


async def test_end_user_cannot_set_requester_id_or_organization_id_on_create(client, db_session):
    org = await _org(db_session)
    other = await create_user(db_session, email="someone-else@example.com", role=UserRole.end_user)
    token = await register(client, "self-service@example.com")
    resp = await client.post(
        "/tickets",
        json={"subject": "s", "description": "d", "requester_id": other.id, "organization_id": org.id},
        headers=auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    caller = (await db_session.execute(select(User).where(User.email == "self-service@example.com"))).scalar_one()
    # Both silently ignored: it's still their own ticket, own (lack of) org.
    assert body["requester_id"] == caller.id
    assert body["organization_id"] is None


async def test_agent_claims_an_unclaimed_ticket_for_a_newly_registered_customer(client, db_session):
    org = await _org(db_session)
    await create_agent(db_session, email="creator4@example.com")
    agent_token = await login(client, "creator4@example.com")
    created = await client.post(
        "/tickets", json={"subject": "s", "description": "d", "organization_id": org.id}, headers=auth(agent_token)
    )
    ticket_id = created.json()["id"]

    new_customer_token = await register(client, "brand-new@example.com")
    new_customer_id = (await client.get("/auth/me", headers=auth(new_customer_token))).json()["id"]

    claimed = await client.patch(
        f"/tickets/{ticket_id}", json={"requester_id": new_customer_id}, headers=auth(agent_token)
    )
    assert claimed.status_code == 200
    assert claimed.json()["requester_id"] == new_customer_id

    mine = await client.get("/tickets", headers=auth(new_customer_token))
    assert [t["id"] for t in mine.json()["items"]] == [ticket_id]

    audit = (
        await db_session.scalars(
            select(AuditLog).where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket_id)
        )
    ).all()
    assert any(a.diff_json and a.diff_json.get("after", {}).get("requester_id") == new_customer_id for a in audit)


async def test_claiming_an_already_claimed_ticket_is_409(client, db_session):
    org = await _org(db_session)
    customer1 = await create_user(db_session, email="c1@example.com", role=UserRole.end_user, organization_id=org.id)
    customer2 = await create_user(db_session, email="c2@example.com", role=UserRole.end_user, organization_id=org.id)
    await create_agent(db_session, email="creator5@example.com")
    agent_token = await login(client, "creator5@example.com")
    created = await client.post(
        "/tickets", json={"subject": "s", "description": "d", "requester_id": customer1.id}, headers=auth(agent_token)
    )
    ticket_id = created.json()["id"]

    resp = await client.patch(
        f"/tickets/{ticket_id}", json={"requester_id": customer2.id}, headers=auth(agent_token)
    )
    assert resp.status_code == 409


async def test_claiming_with_an_unknown_or_non_customer_id_is_422(client, db_session):
    org = await _org(db_session)
    agent2 = await create_agent(db_session, email="not-a-customer@example.com")
    await create_agent(db_session, email="creator6@example.com")
    agent_token = await login(client, "creator6@example.com")
    created = await client.post(
        "/tickets", json={"subject": "s", "description": "d", "organization_id": org.id}, headers=auth(agent_token)
    )
    ticket_id = created.json()["id"]

    unknown = await client.patch(f"/tickets/{ticket_id}", json={"requester_id": 999999}, headers=auth(agent_token))
    assert unknown.status_code == 422
    not_customer = await client.patch(
        f"/tickets/{ticket_id}", json={"requester_id": agent2.id}, headers=auth(agent_token)
    )
    assert not_customer.status_code == 422


async def test_search_customers(client, db_session):
    org = await _org(db_session)
    await create_user(db_session, email="findme@example.com", name="Uma Findable", role=UserRole.end_user, organization_id=org.id)
    await create_agent(db_session, email="searcher@example.com")
    agent_token = await login(client, "searcher@example.com")

    by_name = await client.get("/users/customers", params={"q": "Findable"}, headers=auth(agent_token))
    assert by_name.status_code == 200
    assert [c["email"] for c in by_name.json()] == ["findme@example.com"]
    assert by_name.json()[0]["organization_name"] == "Acme Corp"

    by_email = await client.get("/users/customers", params={"q": "findme@"}, headers=auth(agent_token))
    assert [c["email"] for c in by_email.json()] == ["findme@example.com"]

    end_user_token = await register(client, "not-staff@example.com")
    assert (await client.get("/users/customers", params={"q": "a"}, headers=auth(end_user_token))).status_code == 403
