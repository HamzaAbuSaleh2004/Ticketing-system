"""Create the first admin, or promote an existing account to admin.

    python -m app.create_admin --email you@liverx.me --name "Your Name"

Prompts for the password twice (hidden input, no echo) only when actually
creating a new account — promoting an existing one never touches a password.
Never sets up 2FA: the admin enrols an authenticator at their first
sign-in, same as anyone else. Idempotent: running it again for an email
that's already an admin just says so and exits 0. Works with ENV=prod.
"""

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy import select

from app.auth.security import hash_password
from app.config import get_settings
from app.db import SessionLocal
from app.domain.staff import is_allowed_staff_email
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import RegisterRequest


async def create_or_promote_admin(email: str, name: str, get_password: Callable[[], str]) -> str:
    """The message to print. Raises ValueError for a caller to report and
    exit non-zero on. `get_password` is called only when actually creating a
    new account — never for a promotion, so the operator isn't prompted for
    (and doesn't type) a password that would just be thrown away."""
    settings = get_settings()
    email = email.strip().lower()
    if not is_allowed_staff_email(email, settings):
        raise ValueError(f"{email} isn't an allowed staff address ({', '.join(settings.staff_email_domains)})")

    async with SessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            if existing.role is UserRole.admin:
                return f"{email} is already an admin."
            existing.role = UserRole.admin
            existing.team = None
            await session.commit()
            return f"Promoted {email} to admin."

        password = get_password()
        try:
            RegisterRequest(email=email, password=password, name=name)
        except ValidationError as exc:
            raise ValueError("; ".join(e["msg"] for e in exc.errors())) from exc

        session.add(
            User(email=email, name=name, role=UserRole.admin, team=None, password_hash=hash_password(password))
        )
        await session.commit()
        return f"Created admin {email}. They set up two-step verification at their first sign-in."


def _read_password() -> str:
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise ValueError("Passwords didn't match.")
    return password


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    try:
        message = await create_or_promote_admin(args.email, args.name, _read_password)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    print(message)


if __name__ == "__main__":
    asyncio.run(main())
