from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_role
from app.auth.security import (
    hash_password,
    password_exceeds_limit,
    verify_password_timing_safe,
)
from app.auth.tokens import create_access_token
from app.db import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    # Public registration always creates an end_user; agent/admin accounts are
    # provisioned by an admin (Phase 9), never through this endpoint.
    user = User(
        email=body.email,
        name=body.name,
        role=UserRole.end_user,
        team=None,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Two concurrent registrations for the same email both pass the
        # pre-commit check; the unique constraint is the real guard, so
        # translate its violation into the same 409 a sequential duplicate
        # would get, instead of a 500.
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    await session.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    # bcrypt raises ValueError past 72 bytes rather than just comparing
    # wrong; no real password is this long, so reject without hashing.
    if password_exceeds_limit(body.password):
        raise invalid

    user = await session.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password_timing_safe(body.password, user.password_hash if user else None)
    if user is None or not password_ok:
        raise invalid

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/_probe/agent-only")
async def agent_only_probe(user: User = Depends(require_role(UserRole.agent, UserRole.admin))) -> dict:
    """Exists only to give Phase 3's tests a role-gated route to hit before
    Phase 4 adds real agent-only ticket routes. Safe to remove once one exists."""
    return {"ok": True, "role": user.role.value}
