from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.models import User
from app.models.enums import UserRole
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/staff", response_model=list[UserOut])
async def list_staff(
    user: User = Depends(require_role(UserRole.agent, UserRole.admin)),
    session: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    """Agents and admins: the assignee picker's options."""
    rows = await session.scalars(
        select(User).where(User.role.in_([UserRole.agent, UserRole.admin])).order_by(User.name)
    )
    return [UserOut.model_validate(u) for u in rows]
