from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import TokenError, decode_access_token
from app.db import get_db
from app.models import User
from app.models.enums import UserRole

_bearer_scheme = HTTPBearer(auto_error=False)


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = await session.scalar(select(User).where(User.id == int(payload["sub"])))
    # Access tokens are only issued after 2FA, so one for an account whose
    # 2FA was since reset, or issued before its current enrolment, is dead.
    if (
        user is None
        or user.totp_enabled_at is None
        or payload["iat"] < int(user.totp_enabled_at.timestamp())
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


def require_role(*roles: UserRole):
    async def _check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return user

    return _check
