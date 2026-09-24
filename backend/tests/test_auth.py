import jwt

from app.auth.security import hash_password
from app.config import get_settings
from app.models import User
from app.models.enums import Team, UserRole


async def _create_user(db_session, *, email, role, team=None, password="Secret123!"):
    user = User(email=email, name="Test User", role=role, team=team, password_hash=hash_password(password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_register_creates_end_user_and_token_grants_me(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "Password123!", "name": "New User"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["role"] == "end_user"

    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "new@example.com"


async def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@example.com", "password": "Password123!", "name": "Dup"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_success(client, db_session):
    await _create_user(db_session, email="agent@example.com", role=UserRole.agent, team=Team.tier1)
    resp = await client.post("/auth/login", json={"email": "agent@example.com", "password": "Secret123!"})
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "agent"


async def test_login_wrong_password_fails(client, db_session):
    await _create_user(db_session, email="agent2@example.com", role=UserRole.agent)
    resp = await client.post("/auth/login", json={"email": "agent2@example.com", "password": "wrong"})
    assert resp.status_code == 401


async def test_login_unknown_email_fails(client):
    resp = await client.post("/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert resp.status_code == 401


async def test_probe_denies_end_user(client):
    register = await client.post(
        "/auth/register",
        json={"email": "enduser@example.com", "password": "Password123!", "name": "End User"},
    )
    token = register.json()["access_token"]
    resp = await client.get("/auth/_probe/agent-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_probe_allows_agent(client, db_session):
    await _create_user(db_session, email="agent3@example.com", role=UserRole.agent)
    login = await client.post("/auth/login", json={"email": "agent3@example.com", "password": "Secret123!"})
    token = login.json()["access_token"]
    resp = await client.get("/auth/_probe/agent-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "role": "agent"}


async def test_missing_token_is_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_tampered_token_is_401(client):
    register = await client.post(
        "/auth/register",
        json={"email": "tamper@example.com", "password": "Password123!", "name": "Tamper"},
    )
    token = register.json()["access_token"]
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401


async def test_register_password_over_72_bytes_is_422(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "toolong@example.com", "password": "a" * 73, "name": "Too Long"},
    )
    assert resp.status_code == 422


async def test_register_password_over_72_utf8_bytes_is_422(client):
    # 24 codepoints but each is 3+ bytes in UTF-8, well over the 72-byte limit.
    resp = await client.post(
        "/auth/register",
        json={"email": "multibyte@example.com", "password": "€" * 25, "name": "Multibyte"},
    )
    assert resp.status_code == 422


async def test_login_password_over_72_bytes_is_401_not_500(client):
    resp = await client.post(
        "/auth/login", json={"email": "whoever@example.com", "password": "a" * 100}
    )
    assert resp.status_code == 401


async def test_register_and_login_email_case_insensitive(client):
    register = await client.post(
        "/auth/register",
        json={"email": "Mixed.Case@Example.com", "password": "Password123!", "name": "Mixed Case"},
    )
    assert register.status_code == 201
    assert register.json()["user"]["email"] == "mixed.case@example.com"

    login = await client.post(
        "/auth/login", json={"email": "  MIXED.CASE@EXAMPLE.COM  ", "password": "Password123!"}
    )
    assert login.status_code == 200


async def test_register_duplicate_email_different_case_conflicts(client):
    await client.post(
        "/auth/register",
        json={"email": "casedup@example.com", "password": "Password123!", "name": "Case Dup"},
    )
    second = await client.post(
        "/auth/register",
        json={"email": "CaseDup@Example.com", "password": "Password123!", "name": "Case Dup 2"},
    )
    assert second.status_code == 409


async def test_expired_token_is_401(client, db_session):
    user = await _create_user(db_session, email="expired@example.com", role=UserRole.end_user)
    settings = get_settings()
    expired_token = jwt.encode(
        {"sub": str(user.id), "role": user.role.value, "iat": 0, "exp": 1},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
