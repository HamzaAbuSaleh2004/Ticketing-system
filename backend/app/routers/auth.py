from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_role
from app.auth.security import hash_password, verify_password
from app.auth.tokens import create_access_token
from app.db import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email already registered")

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
    await session.commit()
    await session.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await session.scalar(select(User).where(User.email == body.email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

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
