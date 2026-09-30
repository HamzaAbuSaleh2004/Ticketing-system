from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.auth.dependencies import current_user, require_role
from app.config import get_settings
from app.db import get_db
from app.domain import clock
from app.domain.audit import write_audit
from app.domain.lifecycle import (
    IllegalTransitionError,
    allowed_next_statuses,
    can_escalate,
    customer_reply_outcome,
    validate_transition,
)
from app.models import (
    Attachment,
    AuditLog,
    Category,
    Organization,
    Ticket,
    TicketActionItem,
    TicketCollaborator,
    TicketComment,
    User,
)
from app.models.enums import ActionItemSide, TicketPriority, TicketStatus, UserRole
from app.schemas.ticket import (
    ActionItemCreate,
    ActionItemOut,
    ActionItemPatch,
    AttachmentOut,
    AuditLogOut,
    CollaboratorCreate,
    CollaboratorOut,
    CommentCreate,
    CommentCreateResult,
    CommentOut,
    TicketCreate,
    TicketDetail,
    TicketDetailPublic,
    TicketListItem,
    TicketListResponse,
    TicketPatch,
    TicketQueueItem,
    TicketQueueResponse,
)
from app.services.tickets import drop_as_collaborator, escalate, lock_ticket, set_priority
from app.storage import Storage, get_storage

router = APIRouter(prefix="/tickets", tags=["tickets"])

# Kept small and specific rather than a generic "any file" allowlist, per
# PLAN.md's "keep it minimal" instruction for attachments.
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/pdf",
    "text/plain",
}

# Leading bytes each allowed type must start with: the declared type alone
# is whatever the client says.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    "image/png": (b"\x89PNG",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "application/pdf": (b"%PDF-",),
}


def _content_matches_type(content_type: str, contents: bytes) -> bool:
    if content_type == "text/plain":
        try:
            contents.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return b"\x00" not in contents
    return contents.startswith(_MAGIC[content_type])


_SORTABLE_COLUMNS: dict[str, ColumnElement] = {
    "id": Ticket.id,
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "priority": Ticket.priority,
    "status": Ticket.status,
}

_AGENT_ROLES = (UserRole.agent, UserRole.admin)


def _is_agent(user: User) -> bool:
    return user.role in _AGENT_ROLES


async def _require_active_organization(session: AsyncSession, organization_id: int) -> None:
    org = await session.get(Organization, organization_id)
    if org is None or not org.active:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown or inactive organisation")


async def _require_agent_user(session: AsyncSession, user_id: int, *, field: str) -> User:
    """Used for both a ticket's primary assignee and its collaborators —
    both must be an existing agent or admin, checked the same way."""
    candidate = await session.get(User, user_id)
    if candidate is None or candidate.role not in _AGENT_ROLES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"{field} must be an existing agent or admin"
        )
    return candidate


async def _get_ticket_or_404(
    session: AsyncSession, ticket_id: int, user: User, *, lock: bool = False
) -> Ticket:
    ticket = await (lock_ticket(session, ticket_id) if lock else session.get(Ticket, ticket_id))
    # A 404, not 403, for an end user's scoping miss: they shouldn't be able
    # to tell another user's ticket ID exists at all.
    if ticket is None or (user.role == UserRole.end_user and ticket.requester_id != user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


async def _build_ticket_detail(
    session: AsyncSession, ticket: Ticket, user: User
) -> TicketDetail | TicketDetailPublic:
    agent = _is_agent(user)

    comment_stmt = (
        select(TicketComment)
        .options(selectinload(TicketComment.author))
        .where(TicketComment.ticket_id == ticket.id)
        .order_by(TicketComment.created_at, TicketComment.id)
    )
    attachment_stmt = (
        select(Attachment)
        .outerjoin(TicketComment, TicketComment.id == Attachment.comment_id)
        .where(Attachment.ticket_id == ticket.id)
        .order_by(Attachment.created_at, Attachment.id)
    )
    if not agent:
        # Enforced here, in the query, not just hidden in the UI.
        comment_stmt = comment_stmt.where(TicketComment.is_internal_note.is_(False))
        attachment_stmt = attachment_stmt.where(
            or_(Attachment.comment_id.is_(None), TicketComment.is_internal_note.is_(False))
        )
    comments = [_comment_out(c, user) for c in await session.scalars(comment_stmt)]
    attachments = [AttachmentOut.model_validate(a) for a in await session.scalars(attachment_stmt)]

    organization = await session.get(Organization, ticket.organization_id) if ticket.organization_id else None
    action_item_rows = (
        await session.execute(
            select(TicketActionItem, User.name)
            .outerjoin(User, User.id == TicketActionItem.done_by)
            .where(TicketActionItem.ticket_id == ticket.id)
            .order_by(TicketActionItem.created_at, TicketActionItem.id)
        )
    ).all()
    action_items = [
        ActionItemOut.model_validate(item).model_copy(update={"done_by_name": name})
        for item, name in action_item_rows
    ]
    open_customer_items = sum(1 for i in action_items if i.side is ActionItemSide.customer and not i.done)
    open_liverx_items = sum(1 for i in action_items if i.side is ActionItemSide.liverx and not i.done)

    cooloff = timedelta(hours=get_settings().RESOLVED_COOLOFF_HOURS)
    public = TicketDetailPublic.model_validate(ticket).model_copy(
        update={
            "comments": comments,
            "attachments": attachments,
            "reopen_until": ticket.resolved_at + cooloff
            if ticket.status is TicketStatus.resolved and ticket.resolved_at
            else None,
            "organization_name": organization.name if organization else None,
            "organization_kind": organization.kind if organization else None,
            "action_items": action_items,
            "open_customer_items": open_customer_items,
            "open_liverx_items": open_liverx_items,
        }
    )
    if not agent:
        return public

    audit_rows = (
        await session.execute(
            select(AuditLog, User.name)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket.id)
            .order_by(AuditLog.created_at, AuditLog.id)
        )
    ).all()
    requester = await session.get(User, ticket.requester_id) if ticket.requester_id else None
    assignee = await session.get(User, ticket.assignee_id) if ticket.assignee_id else None
    collaborators = await _collaborators_out(session, ticket.id)
    return TicketDetail(
        **public.model_dump(),
        requester_name=requester.name if requester else None,
        requester_email=requester.email if requester else None,
        assignee_name=assignee.name if assignee else None,
        collaborators=collaborators,
        audit_log=[
            AuditLogOut.model_validate(row).model_copy(update={"actor_name": name})
            for row, name in audit_rows
        ],
        allowed_transitions=sorted(allowed_next_statuses(ticket.status), key=lambda s: s.value),
    )


async def _collaborators_by_ticket(session: AsyncSession, ticket_ids: list[int]) -> dict[int, list[CollaboratorOut]]:
    if not ticket_ids:
        return {}
    rows = await session.execute(
        select(TicketCollaborator.ticket_id, TicketCollaborator.user_id, User.name)
        .join(User, User.id == TicketCollaborator.user_id)
        .where(TicketCollaborator.ticket_id.in_(ticket_ids))
        .order_by(TicketCollaborator.added_at)
    )
    by_ticket: dict[int, list[CollaboratorOut]] = {}
    for tid, uid, name in rows:
        by_ticket.setdefault(tid, []).append(CollaboratorOut(user_id=uid, name=name))
    return by_ticket


async def _collaborators_out(session: AsyncSession, ticket_id: int) -> list[CollaboratorOut]:
    return (await _collaborators_by_ticket(session, [ticket_id])).get(ticket_id, [])


def _comment_out(comment: TicketComment, viewer: User) -> CommentOut:
    out = CommentOut.model_validate(comment)
    # Customers see staff by first name only ("Tara from Support").
    if not _is_agent(viewer) and comment.author.role in _AGENT_ROLES:
        out.author_name = comment.author.name.split()[0]
    return out


def _parse_sort(sort: str, columns: dict[str, ColumnElement] = _SORTABLE_COLUMNS) -> tuple[ColumnElement, bool]:
    desc = sort.startswith("-")
    key = sort[1:] if desc else sort
    column = columns.get(key)
    if column is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unknown sort field: {key}")
    return column, desc


@router.post("", response_model=TicketDetail | TicketDetailPublic, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail | TicketDetailPublic:
    now = clock.now()
    # Every new ticket starts at the default priority and status; an agent
    # triages it by hand (category, priority, assignee).
    if _is_agent(user):
        # On behalf of a customer: either claimed immediately (an existing
        # end_user, organisation inherited from them) or unclaimed (no
        # requester yet, so the organisation must be given directly).
        requester_id = None
        organization_id = body.organization_id
        if body.requester_id is not None:
            customer = await session.get(User, body.requester_id)
            if customer is None or customer.role != UserRole.end_user:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="requester_id must be an existing customer")
            requester_id = customer.id
            organization_id = customer.organization_id
        elif organization_id is not None:
            await _require_active_organization(session, organization_id)
        else:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Set requester_id (an existing customer) or organization_id (for one with no account yet)",
            )
    else:
        # Self-service: always your own ticket, own organisation.
        requester_id = user.id
        organization_id = user.organization_id

    ticket = Ticket(
        subject=body.subject,
        description=body.description,
        status=TicketStatus.open,
        priority=TicketPriority.normal,
        requester_id=requester_id,
        organization_id=organization_id,
        created_at=now,
    )
    session.add(ticket)
    await session.flush()

    await write_audit(
        session,
        entity_type="ticket",
        entity_id=ticket.id,
        actor_id=user.id,
        action="ticket.created",
        diff={"after": {"status": "open", "priority": "normal"}},
    )
    await session.commit()
    await session.refresh(ticket)
    return await _build_ticket_detail(session, ticket, user)


@router.get("", response_model=TicketQueueResponse | TicketListResponse)
async def list_tickets(
    # Repeatable: ?status=open&status=pending.
    status_filter: list[TicketStatus] | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    assignee: str | None = None,
    category: str | None = None,
    organization: str | None = None,
    q: str | None = None,
    sort: str = "-created_at",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketQueueResponse | TicketListResponse:
    conditions = []
    if user.role == UserRole.end_user:
        conditions.append(Ticket.requester_id == user.id)
    if status_filter:
        conditions.append(Ticket.status.in_(status_filter))
    if priority is not None:
        conditions.append(Ticket.priority == priority)
    if category is not None:
        conditions.append(Ticket.category == category)
    if organization is not None:
        if organization == "none":
            conditions.append(Ticket.organization_id.is_(None))
        else:
            try:
                conditions.append(Ticket.organization_id == int(organization))
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="organization must be 'none' or an organisation id",
                ) from exc
    if q:
        like = f"%{q}%"
        conditions.append(or_(Ticket.subject.ilike(like), Ticket.description.ilike(like)))
    if assignee is not None:
        if assignee == "me":
            is_collaborator = (
                select(TicketCollaborator.id)
                .where(TicketCollaborator.ticket_id == Ticket.id, TicketCollaborator.user_id == user.id)
                .exists()
            )
            conditions.append(or_(Ticket.assignee_id == user.id, is_collaborator))
        elif assignee == "unassigned":
            conditions.append(Ticket.assignee_id.is_(None))
        else:
            try:
                assignee_id = int(assignee)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="assignee must be 'me', 'unassigned', or a user id",
                ) from exc
            conditions.append(Ticket.assignee_id == assignee_id)

    requester = aliased(User)
    assignee = aliased(User)
    org = aliased(Organization)
    sort_column, sort_desc = _parse_sort(sort, {**_SORTABLE_COLUMNS, "organization": org.name})

    # One aggregate per ticket for the open item counts on each side, joined
    # rather than queried per row (a prior per-row-query bug elsewhere in
    # this codebase was flagged in code review as an N+1).
    open_items = (
        select(
            TicketActionItem.ticket_id,
            func.count().filter(
                TicketActionItem.side == ActionItemSide.customer, TicketActionItem.done.is_(False)
            ).label("open_customer"),
            func.count().filter(
                TicketActionItem.side == ActionItemSide.liverx, TicketActionItem.done.is_(False)
            ).label("open_liverx"),
        )
        .group_by(TicketActionItem.ticket_id)
        .subquery()
    )

    stmt = (
        select(
            Ticket,
            requester.name,
            assignee.name,
            org.name,
            org.kind,
            func.coalesce(open_items.c.open_customer, 0),
            func.coalesce(open_items.c.open_liverx, 0),
        )
        .outerjoin(requester, requester.id == Ticket.requester_id)
        .outerjoin(assignee, assignee.id == Ticket.assignee_id)
        .outerjoin(org, org.id == Ticket.organization_id)
        .outerjoin(open_items, open_items.c.ticket_id == Ticket.id)
    )
    count_stmt = select(func.count()).select_from(Ticket)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = (
        stmt.order_by(
            sort_column.desc().nulls_last() if sort_desc else sort_column.asc().nulls_last(),
            Ticket.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    total = await session.scalar(count_stmt) or 0
    rows = (await session.execute(stmt)).all()

    def _item(t: Ticket, org_name: str | None, org_kind, open_customer: int, open_liverx: int) -> TicketListItem:
        return TicketListItem.model_validate(t).model_copy(
            update={
                "organization_name": org_name,
                "organization_kind": org_kind,
                "open_customer_items": open_customer,
                "open_liverx_items": open_liverx,
            }
        )

    if not _is_agent(user):
        return TicketListResponse(
            items=[_item(t, org_name, org_kind, oc, ol) for t, _, _, org_name, org_kind, oc, ol in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    collab_map = await _collaborators_by_ticket(session, [t.id for t, *_ in rows])

    return TicketQueueResponse(
        items=[
            TicketQueueItem(
                **_item(t, org_name, org_kind, oc, ol).model_dump(),
                requester_name=requester_name,
                assignee_name=assignee_name,
                first_responded_at=t.first_responded_at,
                collaborators=collab_map.get(t.id, []),
            )
            for t, requester_name, assignee_name, org_name, org_kind, oc, ol in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_id}", response_model=TicketDetail | TicketDetailPublic)
async def get_ticket(
    ticket_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail | TicketDetailPublic:
    ticket = await _get_ticket_or_404(session, ticket_id, user)
    return await _build_ticket_detail(session, ticket, user)


@router.patch("/{ticket_id}", response_model=TicketDetail)
async def patch_ticket(
    ticket_id: int,
    body: TicketPatch,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No fields to update")

    now = clock.now()
    before: dict = {}
    after: dict = {}

    if changes.pop("escalate", None):
        if not can_escalate(ticket.status):
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Cannot escalate a resolved or closed ticket"
            )
        esc_before, esc_after = await escalate(session, ticket)
        before.update(esc_before)
        after.update(esc_after)
        # Escalation owns priority and assignee in this request.
        changes.pop("priority", None)
        changes.pop("assignee_id", None)

    if changes.get("priority") is not None and changes["priority"] != ticket.priority:
        before["priority"] = ticket.priority.value
        set_priority(ticket, changes["priority"])
        after["priority"] = ticket.priority.value

    if "category" in changes and changes["category"] != ticket.category:
        new_category = changes["category"]
        if new_category is not None:
            exists = await session.scalar(select(Category.slug).where(Category.slug == new_category))
            if exists is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Unknown category")
        before["category"] = ticket.category
        ticket.category = new_category
        after["category"] = ticket.category

    if "organization_id" in changes and changes["organization_id"] != ticket.organization_id:
        new_org_id = changes["organization_id"]
        if new_org_id is not None:
            await _require_active_organization(session, new_org_id)
        before["organization_id"] = ticket.organization_id
        ticket.organization_id = new_org_id
        after["organization_id"] = ticket.organization_id

    if "requester_id" in changes and changes["requester_id"] != ticket.requester_id:
        new_requester_id = changes["requester_id"]
        if ticket.requester_id is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="This ticket already has a requester")
        if new_requester_id is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="requester_id can't be cleared")
        customer = await session.get(User, new_requester_id)
        if customer is None or customer.role != UserRole.end_user:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="requester_id must be an existing customer")
        before["requester_id"] = ticket.requester_id
        ticket.requester_id = new_requester_id
        after["requester_id"] = ticket.requester_id

    if "assignee_id" in changes and changes["assignee_id"] != ticket.assignee_id:
        new_assignee_id = changes["assignee_id"]
        if new_assignee_id is not None:
            await _require_agent_user(session, new_assignee_id, field="assignee_id")
        before["assignee_id"] = ticket.assignee_id
        ticket.assignee_id = new_assignee_id
        after["assignee_id"] = ticket.assignee_id
        if new_assignee_id is not None:
            await drop_as_collaborator(session, ticket.id, new_assignee_id)

    if changes.get("status") is not None and changes["status"] != ticket.status:
        target = changes["status"]
        try:
            validate_transition(ticket.status, target, assignee_id=ticket.assignee_id)
        except IllegalTransitionError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "error": exc.reason or "Illegal transition",
                    "allowed": sorted(s.value for s in exc.allowed),
                },
            ) from exc

        before["status"] = ticket.status.value

        if target is TicketStatus.resolved:
            ticket.resolved_at = now
        elif ticket.status is TicketStatus.resolved and target is TicketStatus.in_progress:
            ticket.resolved_at = None

        if target is TicketStatus.closed:
            ticket.closed_at = now

        ticket.status = target
        after["status"] = ticket.status.value

    if not before:
        # Every field in the request already matched the current value. Commit
        # (not rollback, which would expire `ticket`) just to release the lock.
        await session.commit()
        return await _build_ticket_detail(session, ticket, user)

    await write_audit(
        session,
        entity_type="ticket",
        entity_id=ticket.id,
        actor_id=user.id,
        action="ticket.updated",
        diff={"before": before, "after": after},
    )
    await session.commit()
    await session.refresh(ticket)
    return await _build_ticket_detail(session, ticket, user)


@router.post("/{ticket_id}/comments", response_model=CommentCreateResult, status_code=status.HTTP_201_CREATED)
async def create_comment(
    ticket_id: int,
    body: CommentCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> CommentCreateResult:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)

    if body.is_internal_note and not _is_agent(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only agents can add internal notes")

    is_requester = ticket.requester_id == user.id
    now = clock.now()

    if is_requester and not body.is_internal_note:
        outcome = customer_reply_outcome(
            status=ticket.status,
            resolved_at=ticket.resolved_at,
            cooloff_hours=get_settings().RESOLVED_COOLOFF_HOURS,
            now=now,
        )

        if outcome == "follow_up":
            follow_up = Ticket(
                subject=ticket.subject,
                description=body.body,
                status=TicketStatus.open,
                priority=TicketPriority.normal,
                requester_id=user.id,
                parent_ticket_id=ticket.id,
                created_at=now,
            )
            session.add(follow_up)
            await session.flush()
            await write_audit(
                session,
                entity_type="ticket",
                entity_id=follow_up.id,
                actor_id=user.id,
                action="ticket.created_from_reply",
                diff={"after": {"parent_ticket_id": ticket.id}},
            )
            await session.commit()
            await session.refresh(follow_up)
            return CommentCreateResult(follow_up_ticket_id=follow_up.id)

        if outcome == "reopen":
            before_status = ticket.status
            if ticket.status is TicketStatus.resolved:
                ticket.resolved_at = None
            ticket.status = TicketStatus.in_progress
            await write_audit(
                session,
                entity_type="ticket",
                entity_id=ticket.id,
                actor_id=user.id,
                action="ticket.reopened_by_reply",
                diff={"before": {"status": before_status.value}, "after": {"status": "in_progress"}},
            )

    comment = TicketComment(
        ticket_id=ticket.id,
        author_id=user.id,
        author=user,
        body=body.body,
        is_internal_note=body.is_internal_note,
    )
    session.add(comment)

    if not is_requester and not body.is_internal_note and ticket.first_responded_at is None:
        ticket.first_responded_at = now

    await session.commit()
    # Only server-generated columns: a full refresh would expire `author`.
    await session.refresh(comment, attribute_names=["id", "created_at"])
    return CommentCreateResult(comment=_comment_out(comment, user))


@router.post("/{ticket_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile,
    comment_id: int | None = Form(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> AttachmentOut:
    ticket = await _get_ticket_or_404(session, ticket_id, user)
    settings = get_settings()

    if file.content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type: {file.content_type}",
        )

    contents = await file.read(settings.ATTACHMENT_MAX_BYTES + 1)
    if len(contents) > settings.ATTACHMENT_MAX_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="Attachment too large")
    if not _content_matches_type(file.content_type, contents):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="The file's contents don't match its type"
        )

    if comment_id is not None:
        comment = await session.get(TicketComment, comment_id)
        # End users may only attach to their own public comments: not an
        # agent's reply (it would look sent by staff) and not an internal
        # note (whose existence they mustn't be able to probe).
        allowed = comment is not None and comment.ticket_id == ticket.id
        if allowed and not _is_agent(user):
            allowed = comment.author_id == user.id and not comment.is_internal_note
        if not allowed:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="comment_id must be one of your comments on this ticket"
            )

    # Strip any directory components from the client-supplied filename so it
    # can't write outside the store; the uuid prefix also avoids collisions.
    safe_name = Path(file.filename or "upload").name
    stored_name = f"{uuid4().hex}_{safe_name}"
    key = f"{ticket.id}/{stored_name}"
    await storage.save(key, contents, file.content_type)

    attachment = Attachment(
        ticket_id=ticket.id,
        comment_id=comment_id,
        file_path=key,
        filename=safe_name,
        content_type=file.content_type,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return AttachmentOut.model_validate(attachment)


@router.post(
    "/{ticket_id}/collaborators", response_model=CollaboratorOut, status_code=status.HTTP_201_CREATED
)
async def add_collaborator(
    ticket_id: int,
    body: CollaboratorCreate,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> CollaboratorOut:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)
    if ticket.status is TicketStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Closed tickets are read-only")

    candidate = await _require_agent_user(session, body.user_id, field="user_id")
    if body.user_id == ticket.assignee_id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Already the primary assignee")
    exists = await session.scalar(
        select(TicketCollaborator.id).where(
            TicketCollaborator.ticket_id == ticket.id, TicketCollaborator.user_id == body.user_id
        )
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Already a collaborator")

    collaborator = TicketCollaborator(ticket_id=ticket.id, user_id=body.user_id, added_by=user.id)
    session.add(collaborator)
    await write_audit(
        session, entity_type="ticket", entity_id=ticket.id, actor_id=user.id,
        action="ticket.collaborator_added",
        diff={"after": {"user_id": body.user_id, "name": candidate.name}},
    )
    await session.commit()
    return CollaboratorOut(user_id=candidate.id, name=candidate.name)


@router.delete("/{ticket_id}/collaborators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_collaborator(
    ticket_id: int,
    user_id: int,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> None:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)
    if ticket.status is TicketStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Closed tickets are read-only")

    row = (
        await session.execute(
            select(TicketCollaborator, User.name)
            .join(User, User.id == TicketCollaborator.user_id)
            .where(TicketCollaborator.ticket_id == ticket.id, TicketCollaborator.user_id == user_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not a collaborator")
    collaborator, removed_name = row

    await write_audit(
        session, entity_type="ticket", entity_id=ticket.id, actor_id=user.id,
        action="ticket.collaborator_removed",
        diff={"before": {"user_id": user_id, "name": removed_name}},
    )
    await session.delete(collaborator)
    await session.commit()


async def _action_item_out(session: AsyncSession, item: TicketActionItem) -> ActionItemOut:
    done_by_name = None
    if item.done_by:
        done_by_user = await session.get(User, item.done_by)
        done_by_name = done_by_user.name if done_by_user else None
    return ActionItemOut.model_validate(item).model_copy(update={"done_by_name": done_by_name})


async def _get_action_item_or_404(session: AsyncSession, ticket_id: int, item_id: int) -> TicketActionItem:
    item = await session.get(TicketActionItem, item_id)
    if item is None or item.ticket_id != ticket_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Action item not found")
    return item


@router.post(
    "/{ticket_id}/action-items", response_model=ActionItemOut, status_code=status.HTTP_201_CREATED
)
async def create_action_item(
    ticket_id: int,
    body: ActionItemCreate,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> ActionItemOut:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)
    if ticket.status is TicketStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Closed tickets are read-only")

    item = TicketActionItem(
        ticket_id=ticket.id, side=body.side, description=body.description, created_by=user.id
    )
    session.add(item)
    await session.flush()
    await write_audit(
        session, entity_type="ticket", entity_id=ticket.id, actor_id=user.id,
        action="ticket.action_item_added",
        diff={"after": {"id": item.id, "side": body.side.value, "description": body.description}},
    )
    await session.commit()
    await session.refresh(item)
    return await _action_item_out(session, item)


@router.patch("/{ticket_id}/action-items/{item_id}", response_model=ActionItemOut)
async def patch_action_item(
    ticket_id: int,
    item_id: int,
    body: ActionItemPatch,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> ActionItemOut:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)
    item = await _get_action_item_or_404(session, ticket.id, item_id)
    if ticket.status is TicketStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Closed tickets are read-only")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="No fields to update")
    # The requester may tick their own side's items, nothing else.
    if not _is_agent(user) and (item.side is not ActionItemSide.customer or set(changes) - {"done"}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You can only mark your own items done")

    before: dict = {}
    after: dict = {}
    now = clock.now()

    if "description" in changes and changes["description"] != item.description:
        before["description"] = item.description
        item.description = changes["description"]
        after["description"] = item.description

    if "done" in changes and changes["done"] != item.done:
        before["done"] = item.done
        item.done = changes["done"]
        item.done_at = now if item.done else None
        item.done_by = user.id if item.done else None
        after["done"] = item.done

    if not before:
        await session.commit()
        return await _action_item_out(session, item)

    await write_audit(
        session, entity_type="ticket", entity_id=ticket.id, actor_id=user.id,
        action="ticket.action_item_updated",
        diff={"before": before, "after": after, "item_id": item.id},
    )
    await session.commit()
    await session.refresh(item)
    return await _action_item_out(session, item)


@router.delete("/{ticket_id}/action-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action_item(
    ticket_id: int,
    item_id: int,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> None:
    ticket = await _get_ticket_or_404(session, ticket_id, user, lock=True)
    item = await _get_action_item_or_404(session, ticket.id, item_id)
    if ticket.status is TicketStatus.closed:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Closed tickets are read-only")

    await write_audit(
        session, entity_type="ticket", entity_id=ticket.id, actor_id=user.id,
        action="ticket.action_item_removed",
        diff={"before": {"id": item.id, "side": item.side.value, "description": item.description}},
    )
    await session.delete(item)
    await session.commit()
