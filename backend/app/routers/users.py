from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.models import Organization, User
from app.models.enums import UserRole
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])

# Plenty for a type-ahead picker; this isn't a paginated admin listing.
_CUSTOMER_SEARCH_LIMIT = 20


class CustomerSearchResult(BaseModel):
    id: int
    name: str
    email: str
    organization_id: int | None
    organization_name: str | None

    model_config = {"from_attributes": True}


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


@router.get("/customers", response_model=list[CustomerSearchResult])
async def search_customers(
    q: str = Query(min_length=1, max_length=255),
    user: User = Depends(require_role(UserRole.agent, UserRole.admin)),
    session: AsyncSession = Depends(get_db),
) -> list[CustomerSearchResult]:
    """Agents and admins: the "create/claim a ticket for this customer"
    picker's data source. Existing end_user accounts only — staff-created
    tickets can only be claimed by someone who's actually registered."""
    like = f"%{q}%"
    rows = (
        await session.execute(
            select(User, Organization.name)
            .outerjoin(Organization, Organization.id == User.organization_id)
            .where(User.role == UserRole.end_user, or_(User.name.ilike(like), User.email.ilike(like)))
            .order_by(User.name)
            .limit(_CUSTOMER_SEARCH_LIMIT)
        )
    ).all()
    return [
        CustomerSearchResult(
            id=u.id, name=u.name, email=u.email, organization_id=u.organization_id, organization_name=org_name
        )
        for u, org_name in rows
    ]
