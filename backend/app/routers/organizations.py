"""The company or government entity a ticket's requester belongs to. Listed
for agents/admins (the queue filter and the ticket/organisation pickers);
only admins can create, rename, re-kind or deactivate one."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.domain.audit import write_audit
from app.models import Organization, User
from app.models.enums import UserRole
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationOut,
    OrganizationPatch,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])
_admin = require_role(UserRole.admin)
_staff = require_role(UserRole.agent, UserRole.admin)


@router.get("", response_model=list[OrganizationOut])
async def list_organizations(
    user: User = Depends(_staff), session: AsyncSession = Depends(get_db)
) -> list[OrganizationOut]:
    """Including inactive ones, so an existing ticket can still show its
    organisation's name; the admin and end-user pickers filter to active."""
    rows = await session.scalars(select(Organization).order_by(Organization.name))
    return [OrganizationOut.model_validate(o) for o in rows]


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate, admin: User = Depends(_admin), session: AsyncSession = Depends(get_db)
) -> OrganizationOut:
    org = Organization(name=body.name, kind=body.kind, active=True)
    session.add(org)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="An organisation with that name already exists"
        ) from exc
    await write_audit(
        session, entity_type="organization", entity_id=org.id, actor_id=admin.id,
        action="organization.created", diff={"after": {"name": org.name, "kind": org.kind.value, "active": True}},
    )
    await session.commit()
    return OrganizationOut.model_validate(org)


@router.patch("/{organization_id}", response_model=OrganizationOut)
async def patch_organization(
    organization_id: int,
    body: OrganizationPatch,
    admin: User = Depends(_admin),
    session: AsyncSession = Depends(get_db),
) -> OrganizationOut:
    org = await session.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    before, after = {}, {}
    for key, value in changes.items():
        old = getattr(org, key)
        if old != value:
            before[key] = old.value if hasattr(old, "value") else old
            after[key] = value.value if hasattr(value, "value") else value
            setattr(org, key, value)
    if before:
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="An organisation with that name already exists"
            ) from exc
        await write_audit(
            session, entity_type="organization", entity_id=org.id, actor_id=admin.id,
            action="organization.updated", diff={"before": before, "after": after},
        )
        await session.commit()
    return OrganizationOut.model_validate(org)
