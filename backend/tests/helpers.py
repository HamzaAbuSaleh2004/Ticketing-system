from datetime import datetime

from app.auth.security import hash_password
from app.domain import clock
from app.models import Category, SlaPolicy, User
from app.models.enums import Team, TicketPriority, UserRole
from app.seed import CATEGORIES

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


async def register(client, email: str, password: str = "Password123!") -> str:
    resp = await client.post("/auth/register", json={"email": email, "password": password, "name": "Test User"})
    assert resp.status_code == 201, resp.text
    return resp.json()["access_token"]


async def create_agent(db_session, *, email: str, team: Team = Team.tier1, password: str = "Secret123!") -> User:
    user = User(email=email, name="Agent", role=UserRole.agent, team=team, password_hash=hash_password(password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login(client, email: str, password: str = "Secret123!") -> str:
    resp = await client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def create_ticket(client, token: str, subject: str, description: str) -> dict:
    resp = await client.post("/tickets", json={"subject": subject, "description": description}, headers=auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()
