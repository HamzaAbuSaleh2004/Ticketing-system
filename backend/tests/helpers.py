from datetime import UTC, datetime, timedelta

import pyotp

from app.auth.security import hash_password
from app.domain import clock
from app.models import Category, SlaPolicy, User
from app.models.enums import Team, TicketPriority, UserRole
from app.seed import CATEGORIES

# Accounts made directly in the DB (create_agent) have 2FA set up on this.
TEST_TOTP_SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"

SLA_POLICIES = [
    {"name": "Urgent", "priority": TicketPriority.urgent, "response_minutes": 15, "resolution_minutes": 4 * 60},
    {"name": "High", "priority": TicketPriority.high, "response_minutes": 60, "resolution_minutes": 8 * 60},
    {"name": "Normal", "priority": TicketPriority.normal, "response_minutes": 4 * 60, "resolution_minutes": 24 * 60},
    {"name": "Low", "priority": TicketPriority.low, "response_minutes": 8 * 60, "resolution_minutes": 72 * 60},
]


async def seed_reference_data(db_session) -> None:
    for p in SLA_POLICIES:
        db_session.add(SlaPolicy(**p))
    for c in CATEGORIES:
        db_session.add(Category(name=c["name"], slug=c["slug"], active=True))
    await db_session.commit()


def freeze(monkeypatch, when: datetime) -> None:
    monkeypatch.setattr(clock, "now", lambda: when)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def enroll(client, mfa_token: str) -> dict:
    """The real enrolment: setup, then confirm a code for the new secret.
    Returns the enable response (access_token, user, recovery_codes)."""
    setup = await client.post("/auth/2fa/setup", json={"mfa_token": mfa_token})
    assert setup.status_code == 200, setup.text
    code = pyotp.TOTP(setup.json()["secret"]).now()
    enabled = await client.post("/auth/2fa/enable", json={"mfa_token": mfa_token, "code": code})
    assert enabled.status_code == 200, enabled.text
    return enabled.json()


async def register_full(client, email: str, password: str = "Password123!", name: str = "Test User") -> dict:
    resp = await client.post("/auth/register", json={"email": email, "password": password, "name": name})
    assert resp.status_code == 201, resp.text
    assert resp.json()["mfa"] == "enroll"
    return await enroll(client, resp.json()["mfa_token"])


async def register(client, email: str, password: str = "Password123!", name: str = "Test User") -> str:
    return (await register_full(client, email, password, name))["access_token"]


async def create_agent(db_session, *, email: str, team: Team = Team.tier1, password: str = "Secret123!") -> User:
    return await create_user(db_session, email=email, name="Agent", role=UserRole.agent, team=team, password=password)


async def create_user(
    db_session, *, email: str, role: UserRole, name: str = "Test User", team: Team | None = None,
    password: str = "Secret123!", two_factor: bool = True,
) -> User:
    """Straight into the DB, with 2FA already set up on TEST_TOTP_SECRET
    (unless two_factor=False: the account still has to enrol)."""
    user = User(
        email=email,
        name=name,
        role=role,
        team=team,
        password_hash=hash_password(password),
        totp_secret=TEST_TOTP_SECRET if two_factor else None,
        totp_enabled_at=datetime.now(UTC) - timedelta(minutes=1) if two_factor else None,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client, email: str, password: str = "Secret123!", secret: str = TEST_TOTP_SECRET) -> str:
    """Password, then the current code. A code works once, so one login per
    account per 30 s window (tests needing more pass their own codes)."""
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    assert resp.json()["mfa"] == "verify"
    code = pyotp.TOTP(secret).now()
    verified = await client.post("/auth/2fa/verify", json={"mfa_token": resp.json()["mfa_token"], "code": code})
    assert verified.status_code == 200, verified.text
    return verified.json()["access_token"]


async def create_ticket(client, token: str, subject: str, description: str) -> dict:
    resp = await client.post("/tickets", json={"subject": subject, "description": description}, headers=auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()
