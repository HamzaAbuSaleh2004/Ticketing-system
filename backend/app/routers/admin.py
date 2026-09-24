"""Admin settings: users (role/team), categories, SLA policies, and the
audit trail of those changes. Every write is audit-logged."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.domain.audit import write_audit
from app.models import AuditLog, Category, SlaPolicy, Ticket, User
from app.models.enums import Team, TicketPriority, UserRole
from app.schemas.category import CategoryOut
from app.services.tickets import ACTIVE_STATUSES

router = APIRouter(tags=["admin"])
_admin = require_role(UserRole.admin)
_staff = require_role(UserRole.agent, UserRole.admin)

MAX_SLA_MINUTES = 60 * 24 * 90


class AdminUserOut(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole
    team: Team | None

    model_config = {"from_attributes": True}


class UserPatch(BaseModel):
    role: UserRole | None = None
    team: Team | None = None


def _clean_name(value: str | None) -> str | None:
    # Validated after trimming, so "   " can't become a blank category.
    if value is None:
        return None
    value = " ".join(value.split())
    if not value:
        raise ValueError("Name can't be blank")
    return value


class CategoryCreate(BaseModel):
    name: str = Field(max_length=100)

    _name = field_validator("name")(_clean_name)


class CategoryPatch(BaseModel):
    name: str | None = Field(None, max_length=100)
    active: bool | None = None

    _name = field_validator("name")(_clean_name)


class SlaPolicyOut(BaseModel):
    id: int
    name: str
    priority: TicketPriority
    response_minutes: int
    resolution_minutes: int

    model_config = {"from_attributes": True}


class SlaPolicyPatch(BaseModel):
    response_minutes: int = Field(ge=1, le=MAX_SLA_MINUTES)
    resolution_minutes: int = Field(ge=1, le=MAX_SLA_MINUTES)

    @model_validator(mode="after")
    def _response_within_resolution(self):
        if self.response_minutes > self.resolution_minutes:
            raise ValueError("The first-reply target can't be longer than the resolution target")
        return self


class AdminAuditOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    # What was changed, by name: the user, the category, or the SLA priority.
    subject: str | None
    actor_name: str | None
    action: str
    diff_json: dict | None
    created_at: str


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:100]


def _diff(obj, changes: dict) -> tuple[dict, dict]:
    before, after = {}, {}
    for key, value in changes.items():
        old = getattr(obj, key)
        if old != value:
            before[key] = old.value if hasattr(old, "value") else old
            after[key] = value.value if hasattr(value, "value") else value
            setattr(obj, key, value)
    return before, after


# --- users -----------------------------------------------------------------


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(user: User = Depends(_admin), session: AsyncSession = Depends(get_db)) -> list[AdminUserOut]:
    rows = await session.scalars(select(User).order_by(User.role, User.name))
    return [AdminUserOut.model_validate(u) for u in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def patch_user(
    user_id: int, body: UserPatch, admin: User = Depends(_admin), session: AsyncSession = Depends(get_db)
) -> AdminUserOut:
    target = await session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    # An explicit null role would violate NOT NULL; null team is derived below.
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if target.id == admin.id and "role" in changes and changes["role"] != target.role:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="You can't change your own role")
    staff_roles = (UserRole.agent, UserRole.admin)
    if target.role in staff_roles and changes.get("role", target.role) not in staff_roles:
        open_count = await session.scalar(
            select(func.count()).select_from(Ticket).where(
                Ticket.assignee_id == target.id, Ticket.status.in_(ACTIVE_STATUSES)
            )
        )
        if open_count:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Reassign their {open_count} open ticket{'s' if open_count != 1 else ''} before changing the role",
            )

    role = changes.get("role", target.role)
    # Teams only mean something for agents (tier1 vs the senior escalation queue).
    if role != UserRole.agent:
        changes["team"] = None
    elif changes.get("team", target.team) is None:
        changes["team"] = Team.tier1

    before, after = _diff(target, changes)
    if before:
        await write_audit(
            session, entity_type="user", entity_id=target.id, actor_id=admin.id,
            action="user.updated", diff={"before": before, "after": after},
        )
        await session.commit()
    return AdminUserOut.model_validate(target)


# --- categories ------------------------------------------------------------


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate, admin: User = Depends(_admin), session: AsyncSession = Depends(get_db)
) -> CategoryOut:
    name = body.name
    slug = _slugify(name)
    if not slug:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Use letters or numbers in the name")
    category = Category(name=name, slug=slug, active=True)
    session.add(category)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A category with that name already exists") from exc
    await write_audit(
        session, entity_type="category", entity_id=category.id, actor_id=admin.id,
        action="category.created", diff={"after": {"name": name, "slug": slug, "active": True}},
    )
    await session.commit()
    return CategoryOut.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def patch_category(
    category_id: int, body: CategoryPatch, admin: User = Depends(_admin), session: AsyncSession = Depends(get_db)
) -> CategoryOut:
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Category not found")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    # The slug stays fixed: tickets reference it.
    before, after = _diff(category, changes)
    if before:
        await write_audit(
            session, entity_type="category", entity_id=category.id, actor_id=admin.id,
            action="category.updated", diff={"before": before, "after": after},
        )
        await session.commit()
    return CategoryOut.model_validate(category)


# --- SLA policies ----------------------------------------------------------


@router.get("/sla-policies", response_model=list[SlaPolicyOut])
async def list_sla_policies(user: User = Depends(_staff), session: AsyncSession = Depends(get_db)) -> list[SlaPolicyOut]:
    rows = (await session.scalars(select(SlaPolicy))).all()
    order = list(TicketPriority)[::-1]  # urgent first
    return [SlaPolicyOut.model_validate(p) for p in sorted(rows, key=lambda p: order.index(p.priority))]


@router.patch("/sla-policies/{priority}", response_model=SlaPolicyOut)
async def patch_sla_policy(
    priority: TicketPriority, body: SlaPolicyPatch, admin: User = Depends(_admin), session: AsyncSession = Depends(get_db)
) -> SlaPolicyOut:
    """Applies to tickets created after the change (and to an existing ticket
    only if its priority later changes); existing due dates are not recomputed."""
    policy = await session.scalar(select(SlaPolicy).where(SlaPolicy.priority == priority))
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="SLA policy not found")
    before, after = _diff(policy, body.model_dump())
    if before:
        await write_audit(
            session, entity_type="sla_policy", entity_id=policy.id, actor_id=admin.id,
            action="sla_policy.updated", diff={"before": before, "after": after, "priority": priority.value},
        )
        await session.commit()
    return SlaPolicyOut.model_validate(policy)


# --- audit of admin changes ------------------------------------------------


@router.get("/admin/audit", response_model=list[AdminAuditOut])
async def admin_audit(
    entity_type: Literal["user", "category", "sla_policy"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(_admin),
    session: AsyncSession = Depends(get_db),
) -> list[AdminAuditOut]:
    stmt = (
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(AuditLog.entity_type.in_([entity_type] if entity_type else ["user", "category", "sla_policy"]))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    ids = {kind: {r.entity_id for r, _ in rows if r.entity_type == kind} for kind in ("user", "category", "sla_policy")}
    names: dict[tuple[str, int], str] = {}
    for u in await session.scalars(select(User).where(User.id.in_(ids["user"]))):
        names["user", u.id] = u.name
    for c in await session.scalars(select(Category).where(Category.id.in_(ids["category"]))):
        names["category", c.id] = c.name
    for p in await session.scalars(select(SlaPolicy).where(SlaPolicy.id.in_(ids["sla_policy"]))):
        names["sla_policy", p.id] = p.priority.value
    return [
        AdminAuditOut(
            id=row.id, entity_type=row.entity_type, entity_id=row.entity_id,
            subject=names.get((row.entity_type, row.entity_id)), actor_name=actor,
            action=row.action, diff_json=row.diff_json, created_at=row.created_at.isoformat(),
        )
        for row, actor in rows
    ]
