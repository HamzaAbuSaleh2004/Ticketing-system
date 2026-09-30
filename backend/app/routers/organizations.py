"""The company or government entity a ticket's requester belongs to. Listed
for agents/admins (the queue filter and the ticket/organisation pickers);
only admins can create, rename, re-kind or deactivate one — or override its
SLA policy (each priority falls back to the global default until overridden
here)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.domain.audit import write_audit
from app.models import Organization, SlaPolicy, User
from app.models.enums import TicketPriority, UserRole
from app.routers.admin import SlaPolicyPatch
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationOut,
    OrganizationPatch,
)
from app.services.tickets import get_policy

router = APIRouter(prefix="/organizations", tags=["organizations"])
_admin = require_role(UserRole.admin)
_staff = require_role(UserRole.agent, UserRole.admin)


class OrgSlaPolicyOut(BaseModel):
    priority: TicketPriority
    response_minutes: int
    resolution_minutes: int
    # False while this organisation uses the global default for this
    # priority; true once it has its own override row.
    is_override: bool


class OrgSlaPolicyPut(SlaPolicyPatch):
    """Same shape and validation as the global policy patch (admin.py) —
    just under a name that fits this endpoint's own meaning."""


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


async def _get_organization_or_404(session: AsyncSession, organization_id: int) -> Organization:
    org = await session.get(Organization, organization_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organisation not found")
    return org


@router.get("/{organization_id}/sla-policies", response_model=list[OrgSlaPolicyOut])
async def list_organization_sla_policies(
    organization_id: int, user: User = Depends(_staff), session: AsyncSession = Depends(get_db)
) -> list[OrgSlaPolicyOut]:
    """The effective policy per priority for this organisation: its own
    override if it has one, else the global default. Two queries (this
    organisation's overrides, the global defaults), not one per priority."""
    await _get_organization_or_404(session, organization_id)
    rows = await session.scalars(
        select(SlaPolicy).where(
            (SlaPolicy.organization_id == organization_id) | (SlaPolicy.organization_id.is_(None))
        )
    )
    overrides: dict[TicketPriority, SlaPolicy] = {}
    defaults: dict[TicketPriority, SlaPolicy] = {}
    for row in rows:
        (overrides if row.organization_id == organization_id else defaults)[row.priority] = row

    order = list(TicketPriority)[::-1]  # urgent first
    return [
        OrgSlaPolicyOut(
            priority=priority,
            response_minutes=(overrides.get(priority) or defaults[priority]).response_minutes,
            resolution_minutes=(overrides.get(priority) or defaults[priority]).resolution_minutes,
            is_override=priority in overrides,
        )
        for priority in order
    ]


@router.put("/{organization_id}/sla-policies/{priority}", response_model=OrgSlaPolicyOut)
async def put_organization_sla_policy(
    organization_id: int,
    priority: TicketPriority,
    body: OrgSlaPolicyPut,
    admin: User = Depends(_admin),
    session: AsyncSession = Depends(get_db),
) -> OrgSlaPolicyOut:
    """Creates or replaces this organisation's own override for a priority.
    Applies to tickets created after the change; existing due dates are not
    recomputed."""
    org = await _get_organization_or_404(session, organization_id)
    policy = await session.scalar(
        select(SlaPolicy).where(SlaPolicy.organization_id == organization_id, SlaPolicy.priority == priority)
    )
    if policy is None:
        policy = SlaPolicy(
            organization_id=organization_id,
            name=f"{org.name} — {priority.value}",
            priority=priority,
            response_minutes=body.response_minutes,
            resolution_minutes=body.resolution_minutes,
        )
        session.add(policy)
        await write_audit(
            session, entity_type="organization", entity_id=organization_id, actor_id=admin.id,
            action="organization.sla_override_set",
            diff={"after": body.model_dump(), "priority": priority.value},
        )
    else:
        before, after = {}, {}
        for key, value in body.model_dump().items():
            old = getattr(policy, key)
            if old != value:
                before[key] = old
                after[key] = value
                setattr(policy, key, value)
        if before:
            await write_audit(
                session, entity_type="organization", entity_id=organization_id, actor_id=admin.id,
                action="organization.sla_override_set",
                diff={"before": before, "after": after, "priority": priority.value},
            )
    await session.commit()
    await session.refresh(policy)
    return OrgSlaPolicyOut(
        priority=priority,
        response_minutes=policy.response_minutes,
        resolution_minutes=policy.resolution_minutes,
        is_override=True,
    )


@router.delete("/{organization_id}/sla-policies/{priority}", response_model=OrgSlaPolicyOut)
async def delete_organization_sla_policy(
    organization_id: int,
    priority: TicketPriority,
    admin: User = Depends(_admin),
    session: AsyncSession = Depends(get_db),
) -> OrgSlaPolicyOut:
    """Removes this organisation's override, reverting it to the global
    default for that priority."""
    await _get_organization_or_404(session, organization_id)
    policy = await session.scalar(
        select(SlaPolicy).where(SlaPolicy.organization_id == organization_id, SlaPolicy.priority == priority)
    )
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This organisation has no override for that priority")
    await write_audit(
        session, entity_type="organization", entity_id=organization_id, actor_id=admin.id,
        action="organization.sla_override_cleared",
        diff={
            "before": {
                "response_minutes": policy.response_minutes,
                "resolution_minutes": policy.resolution_minutes,
            },
            "priority": priority.value,
        },
    )
    await session.delete(policy)
    await session.commit()
    default = await get_policy(session, priority, None)
    return OrgSlaPolicyOut(
        priority=priority,
        response_minutes=default.response_minutes,
        resolution_minutes=default.resolution_minutes,
        is_override=False,
    )
