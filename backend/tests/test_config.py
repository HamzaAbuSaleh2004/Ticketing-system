import pytest

from app.config import Settings


def test_prod_with_default_secret_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="dev-secret-change-me")
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


def test_prod_with_short_secret_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="short-secret")
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


def test_prod_with_strong_secret_starts():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32)
    settings.check_prod_safe()


def test_local_with_default_secret_starts():
    settings = Settings(ENV="local", JWT_SECRET="dev-secret-change-me")
    settings.check_prod_safe()


async def test_seed_users_is_skipped_in_prod(db_session, monkeypatch):
    from sqlalchemy import func, select

    from app import seed
    from app.config import get_settings
    from app.models import User

    monkeypatch.setattr(get_settings(), "ENV", "prod")
    await seed.seed_users(db_session)
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


async def test_local_demo_accounts_come_with_2fa_on_the_published_secret(client, db_session):
    import pyotp
    from sqlalchemy import select

    from app import seed
    from app.models import User

    await seed.seed_users(db_session)
    users = (await db_session.scalars(select(User))).all()
    assert users and all(u.two_factor_enabled and u.totp_secret == seed.DEMO_TOTP_SECRET for u in users)

    step = await client.post("/auth/login", json={"email": "agent1@ticketing.demo", "password": seed.SEED_PASSWORD})
    assert step.json()["mfa"] == "verify"
    code = pyotp.TOTP(seed.DEMO_TOTP_SECRET).now()
    verified = await client.post("/auth/2fa/verify", json={"mfa_token": step.json()["mfa_token"], "code": code})
    assert verified.status_code == 200
