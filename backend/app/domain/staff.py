"""Which email domains are allowed for staff (agent/admin) accounts."""

from app.config import Settings


def is_allowed_staff_email(email: str, settings: Settings) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    # The local demo staff accounts (seed.py) use @ticketing.demo; allowed
    # only for a local run, never in prod.
    if settings.ENV == "local" and domain == "ticketing.demo":
        return True
    return domain in settings.staff_email_domains
