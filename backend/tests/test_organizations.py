import pytest_asyncio
from sqlalchemy import select

from app.models import AuditLog, Organization
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


async def _admin_token(client, db_session, email: str = "org-admin@example.com") -> str:
    await create_user(db_session, email=email, name="Boss", role=UserRole.admin)
    return await login(client, email)


async def _org(db_session, name: str = "Acme Corp", kind: OrganizationKind = OrganizationKind.company) -> Organization:
    org = Organization(name=name, kind=kind)
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


# --- organisation CRUD -------------------------------------------------------


async def test_admin_creates_renames_and_deactivates_an_organization_audited(client, db_session):
    admin_token = await _admin_token(client, db_session)

    created = await client.post(
        "/organizations", json={"name": "  Acme  Corp ", "kind": "company"}, headers=auth(admin_token)
    )
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Acme Corp"  # collapsed whitespace
    org_id = created.json()["id"]

    listed = await client.get("/organizations", headers=auth(admin_token))
    assert [o["name"] for o in listed.json()] == ["Acme Corp"]

    renamed = await client.patch(
        f"/organizations/{org_id}", json={"name": "Acme Corporation", "kind": "government"}, headers=auth(admin_token)
    )
    assert (renamed.json()["name"], renamed.json()["kind"]) == ("Acme Corporation", "government")

    deactivated = await client.patch(f"/organizations/{org_id}", json={"active": False}, headers=auth(admin_token))
    assert deactivated.json()["active"] is False

    rows = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.entity_type == "organization", AuditLog.entity_id == org_id)
        )
    ).scalars().all()
    assert [r.action for r in rows] == ["organization.created", "organization.updated", "organization.updated"]

    audit = await client.get("/admin/audit?entity_type=organization", headers=auth(admin_token))
    assert audit.json()[0]["subject"] == "Acme Corporation"


async def test_organization_name_is_case_insensitive_unique(client, db_session):
    admin_token = await _admin_token(client, db_session)
    await client.post("/organizations", json={"name": "Acme Corp", "kind": "company"}, headers=auth(admin_token))
    dup = await client.post("/organizations", json={"name": "ACME CORP", "kind": "government"}, headers=auth(admin_token))
    assert dup.status_code == 409


async def test_only_admin_can_write_organizations_agents_can_list(client, db_session):
    agent = await create_agent(db_session, email="org-agent@example.com")
    agent_token = await login(client, "org-agent@example.com")
    assert (await client.get("/organizations", headers=auth(agent_token))).status_code == 200
    assert (
        await client.post("/organizations", json={"name": "X", "kind": "company"}, headers=auth(agent_token))
    ).status_code == 403
    end_user_token = await register(client, "org-enduser@example.com")
    assert (await client.get("/organizations", headers=auth(end_user_token))).status_code == 403
    assert agent.role == UserRole.agent  # sanity: helper returned the right role


# --- users ↔ organisation -----------------------------------------------------


async def test_admin_assigns_organization_to_end_user_only(client, db_session):
    admin_token = await _admin_token(client, db_session)
    org = await _org(db_session)
    end_user = await create_user(db_session, email="assignee@example.com", role=UserRole.end_user)
    agent = await create_agent(db_session, email="staff-org@example.com")

    ok = await client.patch(f"/users/{end_user.id}", json={"organization_id": org.id}, headers=auth(admin_token))
    assert ok.json()["organization_id"] == org.id

    refused = await client.patch(f"/users/{agent.id}", json={"organization_id": org.id}, headers=auth(admin_token))
    assert refused.status_code == 422

    inactive = await client.patch(f"/organizations/{org.id}", json={"active": False}, headers=auth(admin_token))
    assert inactive.status_code == 200
    end_user_2 = await create_user(db_session, email="assignee2@example.com", role=UserRole.end_user)
    refused_inactive = await client.patch(
        f"/users/{end_user_2.id}", json={"organization_id": org.id}, headers=auth(admin_token)
    )
    assert refused_inactive.status_code == 422


async def test_admin_can_clear_an_end_users_organization(client, db_session):
    admin_token = await _admin_token(client, db_session)
    org = await _org(db_session)
    end_user = await create_user(db_session, email="clearable@example.com", role=UserRole.end_user, organization_id=org.id)
    cleared = await client.patch(f"/users/{end_user.id}", json={"organization_id": None}, headers=auth(admin_token))
    assert cleared.status_code == 200
    assert cleared.json()["organization_id"] is None


async def test_promoting_an_end_user_clears_their_organization(client, db_session):
    admin_token = await _admin_token(client, db_session)
    org = await _org(db_session)
    end_user = await create_user(db_session, email="promotee@ticketing.demo", role=UserRole.end_user, organization_id=org.id)
    promoted = await client.patch(f"/users/{end_user.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert (promoted.json()["role"], promoted.json()["organization_id"]) == ("agent", None)


# --- tickets ↔ organisation ---------------------------------------------------


async def test_ticket_inherits_requesters_organization_and_agent_can_change_it(client, db_session):
    org_a = await _org(db_session, "Org A")
    org_b = await _org(db_session, "Org B", OrganizationKind.government)
    await create_user(db_session, email="orged-customer@example.com", role=UserRole.end_user, organization_id=org_a.id)
    customer_token = await login(client, "orged-customer@example.com")
    agent = await create_agent(db_session, email="ticket-org-agent@example.com")
    agent_token = await login(client, "ticket-org-agent@example.com")

    created = await client.post(
        "/tickets", json={"subject": "s", "description": "d"}, headers=auth(customer_token)
    )
    ticket_id = created.json()["id"]
    assert created.json()["organization_id"] == org_a.id
    assert created.json()["organization_name"] == "Org A"
    assert created.json()["organization_kind"] == "company"

    changed = await client.patch(
        f"/tickets/{ticket_id}", json={"organization_id": org_b.id}, headers=auth(agent_token)
    )
    assert changed.status_code == 200
    assert changed.json()["organization_name"] == "Org B"

    unknown = await client.patch(f"/tickets/{ticket_id}", json={"organization_id": 999999}, headers=auth(agent_token))
    assert unknown.status_code == 422

    audit_actions = [
        row["action"] for row in (
            await client.get(f"/tickets/{ticket_id}", headers=auth(agent_token))
        ).json()["audit_log"]
    ]
    assert "ticket.updated" in audit_actions
    assert agent.role == UserRole.agent


async def test_ticket_list_filters_and_sorts_by_organization(client, db_session):
    org_a = await _org(db_session, "Filter Org A")
    customer_a = await create_user(db_session, email="filter-a@example.com", role=UserRole.end_user, organization_id=org_a.id)
    customer_b = await create_user(db_session, email="filter-b@example.com", role=UserRole.end_user)
    token_a = await login(client, "filter-a@example.com")
    token_b = await login(client, "filter-b@example.com")
    await create_agent(db_session, email="filter-agent@example.com")
    agent_token = await login(client, "filter-agent@example.com")

    await client.post("/tickets", json={"subject": "from A", "description": "d"}, headers=auth(token_a))
    await client.post("/tickets", json={"subject": "from B", "description": "d"}, headers=auth(token_b))

    by_org = await client.get(f"/tickets?organization={org_a.id}", headers=auth(agent_token))
    assert [t["subject"] for t in by_org.json()["items"]] == ["from A"]

    no_org = await client.get("/tickets?organization=none", headers=auth(agent_token))
    assert [t["subject"] for t in no_org.json()["items"]] == ["from B"]

    sorted_asc = await client.get("/tickets?sort=organization", headers=auth(agent_token))
    assert sorted_asc.status_code == 200
    assert customer_a.organization_id == org_a.id and customer_b.organization_id is None


# --- action items --------------------------------------------------------------


async def test_agent_manages_action_items_both_sides(client, db_session):
    await create_agent(db_session, email="ai-agent@example.com")
    agent_token = await login(client, "ai-agent@example.com")
    customer_token = await register(client, "ai-customer@example.com")
    ticket = await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=auth(customer_token))
    ticket_id = ticket.json()["id"]

    customer_item = await client.post(
        f"/tickets/{ticket_id}/action-items",
        json={"side": "customer", "description": "  Upload your invoice  "},
        headers=auth(agent_token),
    )
    assert customer_item.status_code == 201
    assert customer_item.json()["description"] == "Upload your invoice"
    liverx_item = await client.post(
        f"/tickets/{ticket_id}/action-items", json={"side": "liverx", "description": "Refund the charge"},
        headers=auth(agent_token),
    )
    assert liverx_item.status_code == 201

    detail = await client.get(f"/tickets/{ticket_id}", headers=auth(agent_token))
    assert detail.json()["open_customer_items"] == 1
    assert detail.json()["open_liverx_items"] == 1

    # An explicit null description is a clean 422, not a crash (it isn't a
    # valid "leave it unset", since description is a required column).
    null_description = await client.patch(
        f"/tickets/{ticket_id}/action-items/{liverx_item.json()['id']}",
        json={"description": None},
        headers=auth(agent_token),
    )
    assert null_description.status_code == 422

    done = await client.patch(
        f"/tickets/{ticket_id}/action-items/{liverx_item.json()['id']}", json={"done": True}, headers=auth(agent_token)
    )
    assert done.json()["done"] is True
    assert done.json()["done_by_name"] == "Agent"

    removed = await client.delete(f"/tickets/{ticket_id}/action-items/{customer_item.json()['id']}", headers=auth(agent_token))
    assert removed.status_code == 204
    after = await client.get(f"/tickets/{ticket_id}", headers=auth(agent_token))
    assert len(after.json()["action_items"]) == 1


async def test_customer_can_only_tick_their_own_side(client, db_session):
    await create_agent(db_session, email="ai-agent2@example.com")
    agent_token = await login(client, "ai-agent2@example.com")
    customer_token = await register(client, "ai-customer2@example.com")
    ticket = await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=auth(customer_token))
    ticket_id = ticket.json()["id"]

    customer_item = (
        await client.post(
            f"/tickets/{ticket_id}/action-items", json={"side": "customer", "description": "Send a screenshot"},
            headers=auth(agent_token),
        )
    ).json()
    liverx_item = (
        await client.post(
            f"/tickets/{ticket_id}/action-items", json={"side": "liverx", "description": "Check the logs"},
            headers=auth(agent_token),
        )
    ).json()

    ok = await client.patch(
        f"/tickets/{ticket_id}/action-items/{customer_item['id']}", json={"done": True}, headers=auth(customer_token)
    )
    assert ok.status_code == 200

    forbidden_side = await client.patch(
        f"/tickets/{ticket_id}/action-items/{liverx_item['id']}", json={"done": True}, headers=auth(customer_token)
    )
    assert forbidden_side.status_code == 403

    forbidden_field = await client.patch(
        f"/tickets/{ticket_id}/action-items/{customer_item['id']}", json={"description": "no"}, headers=auth(customer_token)
    )
    assert forbidden_field.status_code == 403

    no_add = await client.post(
        f"/tickets/{ticket_id}/action-items", json={"side": "customer", "description": "x"}, headers=auth(customer_token)
    )
    assert no_add.status_code == 403
    no_delete = await client.delete(
        f"/tickets/{ticket_id}/action-items/{liverx_item['id']}", headers=auth(customer_token)
    )
    assert no_delete.status_code == 403


async def test_closed_tickets_action_items_are_read_only(client, db_session):
    await create_agent(db_session, email="ai-agent3@example.com")
    agent_token = await login(client, "ai-agent3@example.com")
    customer_token = await register(client, "ai-customer3@example.com")
    ticket = await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=auth(customer_token))
    ticket_id = ticket.json()["id"]
    item = (
        await client.post(
            f"/tickets/{ticket_id}/action-items", json={"side": "liverx", "description": "Investigate"},
            headers=auth(agent_token),
        )
    ).json()

    # in_progress needs an assignee first.
    await client.patch(f"/tickets/{ticket_id}", json={"assignee_id": item["created_by"]}, headers=auth(agent_token))
    for target in ("in_progress", "resolved", "closed"):
        await client.patch(f"/tickets/{ticket_id}", json={"status": target}, headers=auth(agent_token))

    blocked_create = await client.post(
        f"/tickets/{ticket_id}/action-items", json={"side": "customer", "description": "x"}, headers=auth(agent_token)
    )
    assert blocked_create.status_code == 409
    blocked_patch = await client.patch(
        f"/tickets/{ticket_id}/action-items/{item['id']}", json={"done": True}, headers=auth(agent_token)
    )
    assert blocked_patch.status_code == 409
    blocked_delete = await client.delete(f"/tickets/{ticket_id}/action-items/{item['id']}", headers=auth(agent_token))
    assert blocked_delete.status_code == 409


async def test_end_user_cannot_read_another_organizations_ticket(client, db_session):
    org_a = await _org(db_session, "Scope Org A")
    await create_user(db_session, email="scope-a@example.com", role=UserRole.end_user, organization_id=org_a.id)
    token_a = await login(client, "scope-a@example.com")
    token_other = await register(client, "scope-other@example.com")

    ticket = await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=auth(token_a))
    ticket_id = ticket.json()["id"]

    assert (await client.get(f"/tickets/{ticket_id}", headers=auth(token_other))).status_code == 404
