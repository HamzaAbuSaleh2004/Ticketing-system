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
