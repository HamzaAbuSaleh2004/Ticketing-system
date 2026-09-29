import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.create_admin import create_or_promote_admin
from app.models import LoginAttempt, User
from app.models.enums import UserRole
from app.services.sweeps import prune_login_attempts
from tests.helpers import auth, create_user, freeze, login, register

pytestmark = pytest.mark.usefixtures("db_session")


async def _admin_token(client, db_session, email: str = "boss@liverx.me") -> str:
    await create_user(db_session, email=email, name="Boss", role=UserRole.admin)
    return await login(client, email)


# --- create_admin -----------------------------------------------------------


def _password(value: str = "Password123!"):
    return lambda: value


def _never_read_password():
    raise AssertionError("get_password must not be called when promoting an existing account")


async def test_create_admin_creates_promotes_and_is_idempotent(db_session):
    msg = await create_or_promote_admin("habusaleh@liverx.me", "Hamza", _password())
    assert "Created admin" in msg
    user = await db_session.scalar(select(User).where(User.email == "habusaleh@liverx.me"))
    assert user.role is UserRole.admin
    # Never sets up 2FA: the admin enrols at their first sign-in.
    assert user.totp_secret is None and user.totp_enabled_at is None

    again = await create_or_promote_admin("habusaleh@liverx.me", "Hamza", _never_read_password)
    assert again == "habusaleh@liverx.me is already an admin."

    end_user = await create_user(db_session, email="promote-only@liverx.me", role=UserRole.end_user)
    # A callable that fails if invoked: proves promotion never reads a
    # password, rather than just supplying one that would be ignored.
    promoted = await create_or_promote_admin("promote-only@liverx.me", "Ignored Name", _never_read_password)
    assert "Promoted" in promoted
    await db_session.refresh(end_user)
    assert end_user.role is UserRole.admin and end_user.team is None


async def test_create_admin_rejects_a_short_password(db_session):
    with pytest.raises(ValueError):
        await create_or_promote_admin("shortpw@liverx.me", "Someone", _password("short"))
    assert await db_session.scalar(select(User).where(User.email == "shortpw@liverx.me")) is None


async def test_create_admin_rejects_a_non_staff_domain(db_session):
    with pytest.raises(ValueError):
        await create_or_promote_admin("nobody@gmail.com", "Someone", _password())


# --- staff email domain ------------------------------------------------------


async def test_patch_refuses_to_promote_a_non_staff_email_to_agent(client, db_session):
    admin_token = await _admin_token(client, db_session)
    end_user = await create_user(db_session, email="customer@example.com", role=UserRole.end_user)
    resp = await client.patch(f"/users/{end_user.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert resp.status_code == 422


async def test_patch_allows_promoting_a_liverx_or_local_demo_address(client, db_session):
    admin_token = await _admin_token(client, db_session)
    staff_email_user = await create_user(db_session, email="new-agent@liverx.me", role=UserRole.end_user)
    resp = await client.patch(f"/users/{staff_email_user.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert resp.status_code == 200

    demo_user = await create_user(db_session, email="new-agent@ticketing.demo", role=UserRole.end_user)
    resp2 = await client.patch(f"/users/{demo_user.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert resp2.status_code == 200


async def test_ticketing_demo_staff_domain_is_refused_outside_local(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "ENV", "test")
    admin_token = await _admin_token(client, db_session)
    demo_user = await create_user(db_session, email="not-local@ticketing.demo", role=UserRole.end_user)
    resp = await client.patch(f"/users/{demo_user.id}", json={"role": "agent"}, headers=auth(admin_token))
    assert resp.status_code == 422


# --- registration switch ------------------------------------------------------


async def test_auth_config_reflects_the_registration_switch(client, monkeypatch):
    assert (await client.get("/auth/config")).json() == {"allow_registration": True}
    monkeypatch.setattr(get_settings(), "ALLOW_REGISTRATION", False)
    assert (await client.get("/auth/config")).json() == {"allow_registration": False}
    closed = await client.post(
        "/auth/register", json={"email": "toolate@example.com", "password": "Password123!", "name": "Too Late"}
    )
    assert closed.status_code == 403


# --- login throttling --------------------------------------------------------


async def test_ten_wrong_passwords_for_one_email_locks_that_email(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "TRUST_PROXY", True)
    freeze(monkeypatch, datetime(2026, 9, 29, 12, 0, tzinfo=UTC))
    await create_user(db_session, email="throttle-email@example.com", role=UserRole.agent, password="Secret123!")

    for i in range(10):
        resp = await client.post(
            "/auth/login",
            json={"email": "throttle-email@example.com", "password": "wrong"},
            # A different apparent IP each time, so only the email axis trips.
            headers={"X-Forwarded-For": f"10.0.0.{i}"},
        )
        assert resp.status_code == 401

    locked = await client.post(
        "/auth/login",
        json={"email": "throttle-email@example.com", "password": "Secret123!"},
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert locked.status_code == 429


async def test_a_concurrent_burst_cannot_all_slip_past_the_email_throttle(client, db_session, monkeypatch):
    """A naive check-then-insert throttle lets every request in a fast-enough
    burst read the same pre-burst count and all pass; the advisory-lock
    serialization in auth.py must close that race."""
    monkeypatch.setattr(get_settings(), "TRUST_PROXY", True)
    freeze(monkeypatch, datetime(2026, 9, 29, 12, 0, tzinfo=UTC))
    await create_user(db_session, email="burst@example.com", role=UserRole.agent, password="Secret123!")

    burst = 20
    responses = await asyncio.gather(
        *(
            client.post(
                "/auth/login",
                json={"email": "burst@example.com", "password": "wrong"},
                headers={"X-Forwarded-For": f"172.16.0.{i}"},
            )
            for i in range(burst)
        )
    )
    statuses = [r.status_code for r in responses]
    assert statuses.count(401) == get_settings().LOGIN_MAX_FAILED_ATTEMPTS
    assert statuses.count(429) == burst - get_settings().LOGIN_MAX_FAILED_ATTEMPTS


async def test_ten_wrong_passwords_from_one_ip_locks_that_ip_across_emails(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "TRUST_PROXY", True)
    freeze(monkeypatch, datetime(2026, 9, 29, 12, 0, tzinfo=UTC))
    for i in range(10):
        email = f"ip-throttle-{i}@example.com"
        await create_user(db_session, email=email, role=UserRole.agent, password="Secret123!")
        resp = await client.post(
            "/auth/login", json={"email": email, "password": "wrong"}, headers={"X-Forwarded-For": "203.0.113.5"}
        )
        assert resp.status_code == 401

    await create_user(db_session, email="ip-throttle-victim@example.com", role=UserRole.agent, password="Secret123!")
    locked = await client.post(
        "/auth/login",
        json={"email": "ip-throttle-victim@example.com", "password": "Secret123!"},
        headers={"X-Forwarded-For": "203.0.113.5"},
    )
    assert locked.status_code == 429


async def test_forwarded_for_is_ignored_without_trust_proxy(client, db_session, monkeypatch):
    # TRUST_PROXY defaults to False: a spoofed header can't be used to dodge
    # the by-IP throttle by claiming a different IP on every request.
    freeze(monkeypatch, datetime(2026, 9, 29, 12, 0, tzinfo=UTC))
    for i in range(10):
        email = f"no-trust-proxy-{i}@example.com"
        await create_user(db_session, email=email, role=UserRole.agent, password="Secret123!")
        await client.post(
            "/auth/login", json={"email": email, "password": "wrong"}, headers={"X-Forwarded-For": f"10.1.1.{i}"}
        )

    await create_user(db_session, email="no-trust-proxy-victim@example.com", role=UserRole.agent, password="Secret123!")
    locked = await client.post(
        "/auth/login",
        json={"email": "no-trust-proxy-victim@example.com", "password": "Secret123!"},
        headers={"X-Forwarded-For": "10.1.1.200"},
    )
    # Every request in this test client shares the same real (test) IP, so
    # the by-IP counter still trips even though the (ignored) header varied.
    assert locked.status_code == 429


async def test_login_unlocks_once_the_window_passes(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "TRUST_PROXY", True)
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    freeze(monkeypatch, now)
    await create_user(db_session, email="window-reset@example.com", role=UserRole.agent, password="Secret123!")
    for i in range(10):
        await client.post(
            "/auth/login",
            json={"email": "window-reset@example.com", "password": "wrong"},
            headers={"X-Forwarded-For": f"10.2.2.{i}"},
        )
    locked = await client.post(
        "/auth/login",
        json={"email": "window-reset@example.com", "password": "Secret123!"},
        headers={"X-Forwarded-For": "10.2.2.200"},
    )
    assert locked.status_code == 429

    freeze(monkeypatch, now + timedelta(minutes=get_settings().LOGIN_ATTEMPT_WINDOW_MINUTES, seconds=1))
    unlocked = await client.post(
        "/auth/login",
        json={"email": "window-reset@example.com", "password": "Secret123!"},
        headers={"X-Forwarded-For": "10.2.2.201"},
    )
    assert unlocked.status_code == 200


async def test_prune_login_attempts_removes_only_stale_rows(db_session, monkeypatch):
    now = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
    db_session.add_all([
        LoginAttempt(email="old@example.com", ip="1.1.1.1", created_at=now - timedelta(days=2)),
        LoginAttempt(email="fresh@example.com", ip="1.1.1.1", created_at=now - timedelta(hours=1)),
    ])
    await db_session.commit()

    pruned = await prune_login_attempts(db_session, now)
    assert len(pruned) == 1
    remaining = (await db_session.scalars(select(LoginAttempt))).all()
    assert [r.email for r in remaining] == ["fresh@example.com"]


# --- admin-created staff accounts --------------------------------------------


async def test_admin_creates_a_new_agent_and_it_can_sign_in(client, db_session):
    admin_token = await _admin_token(client, db_session)
    resp = await client.post(
        "/users",
        json={"email": "new-hire@liverx.me", "name": "New Hire", "role": "agent", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert (body["role"], body["team"]) == ("agent", "tier1")

    # A real account: signs in (starts its own enrolment, like anyone else).
    login_step = await client.post("/auth/login", json={"email": "new-hire@liverx.me", "password": "Password123!"})
    assert login_step.status_code == 200
    assert login_step.json()["mfa"] == "enroll"

    listed = await client.get("/users", headers=auth(admin_token))
    assert any(u["email"] == "new-hire@liverx.me" and u["role"] == "agent" for u in listed.json())


async def test_admin_creates_a_new_admin(client, db_session):
    admin_token = await _admin_token(client, db_session)
    resp = await client.post(
        "/users",
        json={"email": "manager@liverx.me", "name": "The Manager", "role": "admin", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


async def test_create_staff_rejects_a_non_staff_domain(client, db_session):
    admin_token = await _admin_token(client, db_session)
    resp = await client.post(
        "/users",
        json={"email": "someone@gmail.com", "name": "Someone", "role": "agent", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert resp.status_code == 422


async def test_create_staff_rejects_end_user_role_and_duplicate_email(client, db_session):
    admin_token = await _admin_token(client, db_session)
    bad_role = await client.post(
        "/users",
        json={"email": "customer@liverx.me", "name": "Nope", "role": "end_user", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert bad_role.status_code == 422

    first = await client.post(
        "/users",
        json={"email": "dup@liverx.me", "name": "First", "role": "agent", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert first.status_code == 201
    dup = await client.post(
        "/users",
        json={"email": "dup@liverx.me", "name": "Second", "role": "agent", "password": "Password123!"},
        headers=auth(admin_token),
    )
    assert dup.status_code == 409


async def test_create_staff_requires_admin(client, db_session):
    agent = await create_user(db_session, email="just-an-agent@liverx.me", role=UserRole.agent)
    agent_token = await login(client, "just-an-agent@liverx.me")
    resp = await client.post(
        "/users",
        json={"email": "sneaky@liverx.me", "name": "Sneaky", "role": "admin", "password": "Password123!"},
        headers=auth(agent_token),
    )
    assert resp.status_code == 403
    assert agent.role is UserRole.agent


# --- security headers ---------------------------------------------------------


async def test_security_headers_are_present(client):
    resp = await client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "same-origin"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


async def test_registration_still_works_when_not_throttled(client):
    # Sanity check none of the above blocks the ordinary path.
    token = await register(client, "still-works@example.com")
    assert token
