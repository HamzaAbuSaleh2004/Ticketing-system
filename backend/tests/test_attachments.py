import pytest_asyncio

from app.models import SlaPolicy
from app.models.enums import TicketPriority


@pytest_asyncio.fixture(autouse=True)
async def _sla_policy(db_session):
    db_session.add(
        SlaPolicy(name="Normal", priority=TicketPriority.normal, response_minutes=240, resolution_minutes=1440)
    )
    await db_session.commit()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _register(client, email: str) -> str:
    resp = await client.post(
        "/auth/register", json={"email": email, "password": "Password123!", "name": "Attacher"}
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def test_upload_attachment_allowed_type(client):
    token = await _register(client, "attach1@example.com")
    ticket_id = (
        await client.post(
            "/tickets", json={"subject": "Broken screenshot", "description": "See attached"},
            headers=_auth(token),
        )
    ).json()["id"]

    resp = await client.post(
        f"/tickets/{ticket_id}/attachments",
        files={"file": ("evidence.png", b"\x89PNG fake bytes", "image/png")},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "evidence.png"
    assert body["content_type"] == "image/png"

    detail = (await client.get(f"/tickets/{ticket_id}", headers=_auth(token))).json()
    assert len(detail["attachments"]) == 1


async def test_upload_attachment_rejects_disallowed_content_type(client):
    token = await _register(client, "attach2@example.com")
    ticket_id = (
        await client.post(
            "/tickets", json={"subject": "Script", "description": "See attached"},
            headers=_auth(token),
        )
    ).json()["id"]

    resp = await client.post(
        f"/tickets/{ticket_id}/attachments",
        files={"file": ("evil.exe", b"MZ", "application/x-msdownload")},
        headers=_auth(token),
    )
    assert resp.status_code == 415


async def test_upload_attachment_rejects_oversized_file(client):
    token = await _register(client, "attach3@example.com")
    ticket_id = (
        await client.post(
            "/tickets", json={"subject": "Huge file", "description": "See attached"},
            headers=_auth(token),
        )
    ).json()["id"]

    from app.config import get_settings

    oversized = b"a" * (get_settings().ATTACHMENT_MAX_BYTES + 1)
    resp = await client.post(
        f"/tickets/{ticket_id}/attachments",
        files={"file": ("big.txt", oversized, "text/plain")},
        headers=_auth(token),
    )
    assert resp.status_code == 413


async def test_end_user_cannot_upload_to_another_users_ticket(client):
    owner_token = await _register(client, "attach-owner@example.com")
    other_token = await _register(client, "attach-other@example.com")
    ticket_id = (
        await client.post(
            "/tickets", json={"subject": "Private", "description": "mine"},
            headers=_auth(owner_token),
        )
    ).json()["id"]

    resp = await client.post(
        f"/tickets/{ticket_id}/attachments",
        files={"file": ("x.txt", b"hi", "text/plain")},
        headers=_auth(other_token),
    )
    assert resp.status_code == 404
