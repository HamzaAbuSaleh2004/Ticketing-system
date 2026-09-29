from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.models.enums import UserRole

# `typ` keeps the two tokens apart: the password step's mfa token can only
# be exchanged for an access token, never used as one.
ACCESS = "access"
MFA = "mfa"


class TokenError(Exception):
    """Raised for a missing, malformed, expired, or tampered token."""


def _encode(payload: dict, minutes: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {**payload, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode(token: str, typ: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "iat", "typ"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if payload["typ"] != typ:
        raise TokenError(f"expected a {typ} token")
    return payload


def create_access_token(*, user_id: int, role: UserRole) -> str:
    return _encode(
        {"sub": str(user_id), "role": role.value, "typ": ACCESS},
        get_settings().JWT_EXPIRES_MINUTES,
    )


def decode_access_token(token: str) -> dict:
    return _decode(token, ACCESS)


def create_mfa_token(*, user_id: int) -> str:
    return _encode({"sub": str(user_id), "typ": MFA}, get_settings().MFA_TOKEN_EXPIRES_MINUTES)


def decode_mfa_token(token: str) -> dict:
    return _decode(token, MFA)
