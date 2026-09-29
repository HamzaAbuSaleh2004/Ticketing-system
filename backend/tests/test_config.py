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
    settings = Settings(
        ENV="prod", JWT_SECRET="x" * 32,
        SWEEP_AUDIENCE="https://helpdesk.example.com", SWEEP_INVOKER_EMAIL="sched@x.iam.gserviceaccount.com",
    )
    settings.check_prod_safe()


def test_local_with_default_secret_starts():
    settings = Settings(ENV="local", JWT_SECRET="dev-secret-change-me")
    settings.check_prod_safe()


def test_prod_with_seed_demo_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32, SEED_DEMO=True)
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


_PROD_SWEEP_KWARGS = {
    "SWEEP_AUDIENCE": "https://helpdesk.example.com",
    "SWEEP_INVOKER_EMAIL": "sched@x.iam.gserviceaccount.com",
}


def test_prod_without_seed_demo_starts():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32, SEED_DEMO=False, **_PROD_SWEEP_KWARGS)
    settings.check_prod_safe()
    # Unset entirely (the common case): defaults to off in prod, so it's fine.
    Settings(ENV="prod", JWT_SECRET="x" * 32, **_PROD_SWEEP_KWARGS).check_prod_safe()


def test_prod_without_sweep_audience_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32, SWEEP_INVOKER_EMAIL="sched@x.iam.gserviceaccount.com")
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


def test_prod_without_sweep_invoker_email_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32, SWEEP_AUDIENCE="https://helpdesk.example.com")
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


def test_prod_gcs_backend_without_bucket_refuses_to_start():
    settings = Settings(ENV="prod", JWT_SECRET="x" * 32, ATTACHMENTS_BACKEND="gcs", **_PROD_SWEEP_KWARGS)
    with pytest.raises(RuntimeError):
        settings.check_prod_safe()


def test_prod_gcs_backend_with_bucket_starts():
    settings = Settings(
        ENV="prod", JWT_SECRET="x" * 32, ATTACHMENTS_BACKEND="gcs", ATTACHMENTS_BUCKET="liverx-attachments",
        **_PROD_SWEEP_KWARGS,
    )
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
