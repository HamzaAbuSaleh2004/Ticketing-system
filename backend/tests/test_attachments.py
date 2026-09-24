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


async def test_download_is_scoped_and_internal_note_attachments_never_reach_end_users(client, db_session):
    from tests.helpers import create_agent, login

    owner_token = await _register(client, "dl-owner@example.com")
    other_token = await _register(client, "dl-other@example.com")
    await create_agent(db_session, email="dl-agent@example.com")
    agent_token = await login(client, "dl-agent@example.com")
    ticket_id = (
        await client.post("/tickets", json={"subject": "Logs", "description": "see file"}, headers=_auth(owner_token))
    ).json()["id"]

    public = (
        await client.post(
            f"/tickets/{ticket_id}/attachments",
            files={"file": ("../../etc/log.txt", b"public bytes", "text/plain")},
            headers=_auth(owner_token),
        )
    ).json()
    assert public["filename"] == "log.txt"

    note = (
        await client.post(
            f"/tickets/{ticket_id}/comments",
            json={"body": "internal analysis", "is_internal_note": True},
            headers=_auth(agent_token),
        )
    ).json()["comment"]
    internal = (
        await client.post(
            f"/tickets/{ticket_id}/attachments",
            files={"file": ("analysis.txt", b"internal bytes", "text/plain")},
            data={"comment_id": str(note["id"])},
            headers=_auth(agent_token),
        )
    ).json()

    resp = await client.get(f"/attachments/{public['id']}", headers=_auth(owner_token))
    assert resp.status_code == 200
    assert resp.content == b"public bytes"
    assert resp.headers["content-disposition"].startswith("attachment;")
    assert 'filename="log.txt"' in resp.headers["content-disposition"]
    assert resp.headers["x-content-type-options"] == "nosniff"

    assert (await client.get(f"/attachments/{public['id']}", headers=_auth(other_token))).status_code == 404
    assert (await client.get(f"/attachments/{internal['id']}", headers=_auth(owner_token))).status_code == 404
    assert (await client.get(f"/attachments/{internal['id']}", headers=_auth(agent_token))).status_code == 200
    assert (await client.get(f"/attachments/{public['id']}")).status_code == 401

    as_owner = (await client.get(f"/tickets/{ticket_id}", headers=_auth(owner_token))).json()
    assert [a["id"] for a in as_owner["attachments"]] == [public["id"]]
    as_agent = (await client.get(f"/tickets/{ticket_id}", headers=_auth(agent_token))).json()
    assert {a["id"] for a in as_agent["attachments"]} == {public["id"], internal["id"]}


async def test_upload_body_cap_type_sniffing_and_comment_ownership(client, db_session, monkeypatch):
    from app.config import get_settings
    from tests.helpers import create_agent, login

    token = await _register(client, "sec-owner@example.com")
    await create_agent(db_session, email="sec-agent@example.com")
    agent_token = await login(client, "sec-agent@example.com")
    ticket_id = (await client.post("/tickets", json={"subject": "s", "description": "d"}, headers=_auth(token))).json()["id"]

    # Declared type must match the contents.
    fake_png = await client.post(
        f"/tickets/{ticket_id}/attachments", files={"file": ("x.png", b"<html>not a png", "image/png")}, headers=_auth(token)
    )
    assert fake_png.status_code == 415
    binary_as_text = await client.post(
        f"/tickets/{ticket_id}/attachments", files={"file": ("x.txt", b"MZ\x00\x01", "text/plain")}, headers=_auth(token)
    )
    assert binary_as_text.status_code == 415

    # Customers can't attach to an agent's reply or an internal note.
    reply = (await client.post(f"/tickets/{ticket_id}/comments", json={"body": "hi"}, headers=_auth(agent_token))).json()["comment"]
    note = (
        await client.post(f"/tickets/{ticket_id}/comments", json={"body": "n", "is_internal_note": True}, headers=_auth(agent_token))
    ).json()["comment"]
    mine = (await client.post(f"/tickets/{ticket_id}/comments", json={"body": "mine"}, headers=_auth(token))).json()["comment"]
    for cid, expected in ((reply["id"], 422), (note["id"], 422), (mine["id"], 201)):
        resp = await client.post(
            f"/tickets/{ticket_id}/attachments",
            files={"file": ("a.txt", b"hello", "text/plain")},
            data={"comment_id": str(cid)},
            headers=_auth(token),
        )
        assert resp.status_code == expected, (cid, resp.text)

    # Oversized bodies are refused before parsing, even without auth.
    monkeypatch.setattr(get_settings(), "ATTACHMENT_MAX_BYTES", 1000)
    big = await client.post(f"/tickets/{ticket_id}/attachments", files={"file": ("b.txt", b"a" * 200_000, "text/plain")})
    assert big.status_code == 413


async def test_tokens_without_exp_or_sub_are_rejected(client):
    import jwt

    from app.config import get_settings

    s = get_settings()
    for payload in ({"sub": "1"}, {"exp": 9999999999}):
        token = jwt.encode(payload, s.JWT_SECRET, algorithm=s.JWT_ALGORITHM)
        assert (await client.get("/auth/me", headers=_auth(token))).status_code == 401
