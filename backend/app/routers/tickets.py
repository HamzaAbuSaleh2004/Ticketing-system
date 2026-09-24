from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

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
    escalate_priority,
    validate_transition,
)
from app.domain.sla import (
    compute_due_dates,
    enter_pending,
    leave_pending,
    mark_first_response,
    recompute_due_on_priority_change,
)
from app.events.bus import get_event_bus
from app.models import (
    Attachment,
    AuditLog,
    Category,
    SlaPolicy,
    Team,
    Ticket,
    TicketComment,
    User,
)
from app.models.enums import TicketPriority, TicketStatus, UserRole
from app.schemas.ticket import (
    AttachmentOut,
    AuditLogOut,
    CommentCreate,
    CommentCreateResult,
    CommentOut,
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketListResponse,
    TicketPatch,
)

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

_SORTABLE_COLUMNS: dict[str, InstrumentedAttribute] = {
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "priority": Ticket.priority,
    "status": Ticket.status,
    "sla_resolution_due": Ticket.sla_resolution_due,
}

_ACTIVE_STATUSES = [
    TicketStatus.new,
    TicketStatus.triaged,
    TicketStatus.open,
    TicketStatus.in_progress,
    TicketStatus.pending,
]


async def _get_ticket_or_404(session: AsyncSession, ticket_id: int, user: User) -> Ticket:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    # A 404, not 403: an end user shouldn't be able to tell another user's
    # ticket ID exists at all.
    if user.role == UserRole.end_user and ticket.requester_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


async def _get_policy(session: AsyncSession, priority: TicketPriority) -> SlaPolicy:
    policy = await session.scalar(select(SlaPolicy).where(SlaPolicy.priority == priority))
    if policy is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No SLA policy configured for priority {priority.value}",
        )
    return policy


async def _least_loaded_senior(session: AsyncSession) -> int | None:
    load_subq = (
        select(Ticket.assignee_id, func.count(Ticket.id).label("load"))
        .where(Ticket.status.in_(_ACTIVE_STATUSES))
        .group_by(Ticket.assignee_id)
        .subquery()
    )
    stmt = (
        select(User.id)
        .outerjoin(load_subq, load_subq.c.assignee_id == User.id)
        .where(User.role == UserRole.agent, User.team == Team.senior)
        .order_by(func.coalesce(load_subq.c.load, 0).asc(), User.id.asc())
        .limit(1)
    )
    return await session.scalar(stmt)


async def _build_ticket_detail(session: AsyncSession, ticket: Ticket, user: User) -> TicketDetail:
    comment_stmt = (
        select(TicketComment)
        .where(TicketComment.ticket_id == ticket.id)
        .order_by(TicketComment.created_at)
    )
    if user.role == UserRole.end_user:
        # Enforced here, in the query, not just hidden in the UI.
        comment_stmt = comment_stmt.where(TicketComment.is_internal_note.is_(False))
    comments = (await session.scalars(comment_stmt)).all()

    attachments = (
        await session.scalars(
            select(Attachment).where(Attachment.ticket_id == ticket.id).order_by(Attachment.created_at)
        )
    ).all()

    audit_log = None
    if user.role in (UserRole.agent, UserRole.admin):
        audit_rows = (
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "ticket", AuditLog.entity_id == ticket.id)
                .order_by(AuditLog.created_at)
            )
        ).all()
        audit_log = [AuditLogOut.model_validate(row) for row in audit_rows]

    detail = TicketDetail.model_validate(ticket)
    detail.comments = [CommentOut.model_validate(c) for c in comments]
    detail.attachments = [AttachmentOut.model_validate(a) for a in attachments]
    detail.audit_log = audit_log
    detail.allowed_transitions = sorted(
        allowed_next_statuses(ticket.status), key=lambda s: s.value
    )
    return detail


def _parse_sort(sort: str) -> tuple[InstrumentedAttribute, bool]:
    desc = sort.startswith("-")
    key = sort[1:] if desc else sort
    column = _SORTABLE_COLUMNS.get(key)
    if column is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown sort field: {key}")
    return column, desc


@router.post("", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    body: TicketCreate,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    now = clock.now()
    # No AI triage yet (Phase 5): every new ticket starts at the default
    # priority until triage applies a real category/priority.
    policy = await _get_policy(session, TicketPriority.normal)
    response_due, resolution_due = compute_due_dates(
        now, response_minutes=policy.response_minutes, resolution_minutes=policy.resolution_minutes
    )

    ticket = Ticket(
        subject=body.subject,
        description=body.description,
        status=TicketStatus.new,
        priority=TicketPriority.normal,
        requester_id=user.id,
        sla_response_due=response_due,
        sla_resolution_due=resolution_due,
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
        diff={"after": {"status": "new", "priority": "normal"}},
    )
    await session.commit()
    await session.refresh(ticket)

    await get_event_bus().publish("ticket.created", {"ticket_id": ticket.id})

    return await _build_ticket_detail(session, ticket, user)


@router.get("", response_model=TicketListResponse)
async def list_tickets(
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    assignee: str | None = None,
    category: str | None = None,
    q: str | None = None,
    sort: str = "-created_at",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketListResponse:
    conditions = []
    if user.role == UserRole.end_user:
        conditions.append(Ticket.requester_id == user.id)
    if status_filter is not None:
        conditions.append(Ticket.status == status_filter)
    if priority is not None:
        conditions.append(Ticket.priority == priority)
    if category is not None:
        conditions.append(Ticket.category == category)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Ticket.subject.ilike(like), Ticket.description.ilike(like)))
    if assignee is not None:
        if assignee == "me":
            conditions.append(Ticket.assignee_id == user.id)
        elif assignee == "unassigned":
            conditions.append(Ticket.assignee_id.is_(None))
        else:
            try:
                assignee_id = int(assignee)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="assignee must be 'me', 'unassigned', or a user id",
                ) from exc
            conditions.append(Ticket.assignee_id == assignee_id)

    sort_column, sort_desc = _parse_sort(sort)

    stmt = select(Ticket)
    count_stmt = select(func.count()).select_from(Ticket)
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    stmt = (
        stmt.order_by(sort_column.desc() if sort_desc else sort_column.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    total = await session.scalar(count_stmt) or 0
    tickets = (await session.scalars(stmt)).all()

    return TicketListResponse(
        items=[TicketListItem.model_validate(t) for t in tickets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: int,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    ticket = await _get_ticket_or_404(session, ticket_id, user)
    return await _build_ticket_detail(session, ticket, user)


@router.patch("/{ticket_id}", response_model=TicketDetail)
async def patch_ticket(
    ticket_id: int,
    body: TicketPatch,
    user: User = Depends(require_role(UserRole.agent, UserRole.admin)),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    now = clock.now()
    before: dict = {}
    after: dict = {}

    escalate = changes.pop("escalate", None)
    if escalate:
        if not can_escalate(ticket.status):
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Cannot escalate a resolved or closed ticket"
            )
        before["priority"] = ticket.priority.value
        before["escalated"] = ticket.escalated
        before["assignee_id"] = ticket.assignee_id

        ticket.priority = escalate_priority(ticket.priority)
        ticket.escalated = True
        new_assignee_id = await _least_loaded_senior(session)
        if new_assignee_id is not None:
            ticket.assignee_id = new_assignee_id
        changes.pop("priority", None)
        changes.pop("assignee_id", None)

        policy = await _get_policy(session, ticket.priority)
        ticket.sla_response_due, ticket.sla_resolution_due = recompute_due_on_priority_change(
            created_at=ticket.created_at,
            response_minutes=policy.response_minutes,
            resolution_minutes=policy.resolution_minutes,
            first_responded_at=ticket.first_responded_at,
            paused_at=ticket.sla_paused_at,
            current_response_due=ticket.sla_response_due,
            current_resolution_due=ticket.sla_resolution_due,
        )

        after["priority"] = ticket.priority.value
        after["escalated"] = ticket.escalated
        after["assignee_id"] = ticket.assignee_id

    if "priority" in changes and changes["priority"] != ticket.priority:
        before["priority"] = ticket.priority.value
        ticket.priority = changes["priority"]
        policy = await _get_policy(session, ticket.priority)
        ticket.sla_response_due, ticket.sla_resolution_due = recompute_due_on_priority_change(
            created_at=ticket.created_at,
            response_minutes=policy.response_minutes,
            resolution_minutes=policy.resolution_minutes,
            first_responded_at=ticket.first_responded_at,
            paused_at=ticket.sla_paused_at,
            current_response_due=ticket.sla_response_due,
            current_resolution_due=ticket.sla_resolution_due,
        )
        after["priority"] = ticket.priority.value

    if "category" in changes and changes["category"] != ticket.category:
        new_category = changes["category"]
        if new_category is not None:
            exists = await session.scalar(select(Category.slug).where(Category.slug == new_category))
            if exists is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown category")
        before["category"] = ticket.category
        ticket.category = new_category
        after["category"] = ticket.category

    if "assignee_id" in changes and changes["assignee_id"] != ticket.assignee_id:
        new_assignee_id = changes["assignee_id"]
        if new_assignee_id is not None:
            assignee = await session.get(User, new_assignee_id)
            if assignee is None or assignee.role not in (UserRole.agent, UserRole.admin):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="assignee_id must be an existing agent or admin",
                )
        before["assignee_id"] = ticket.assignee_id
        ticket.assignee_id = new_assignee_id
        after["assignee_id"] = ticket.assignee_id

    if "status" in changes and changes["status"] != ticket.status:
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

        if target is TicketStatus.pending:
            ticket.sla_paused_at = enter_pending(now)
        elif ticket.status is TicketStatus.pending and target is TicketStatus.in_progress:
            ticket.sla_resolution_due, ticket.sla_paused_total_seconds = leave_pending(
                resolution_due=ticket.sla_resolution_due,
                paused_at=ticket.sla_paused_at,
                paused_total_seconds=ticket.sla_paused_total_seconds,
                now=now,
            )
            ticket.sla_paused_at = None

        if target is TicketStatus.resolved:
            ticket.resolved_at = now
        elif ticket.status is TicketStatus.resolved and target is TicketStatus.in_progress:
            ticket.resolved_at = None

        if target is TicketStatus.closed:
            ticket.closed_at = now

        ticket.status = target
        after["status"] = ticket.status.value

    if not before:
        # Every field in the request already matched the current value.
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
    ticket = await _get_ticket_or_404(session, ticket_id, user)

    if body.is_internal_note and user.role not in (UserRole.agent, UserRole.admin):
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
                status=TicketStatus.new,
                priority=TicketPriority.normal,
                requester_id=user.id,
                parent_ticket_id=ticket.id,
                created_at=now,
            )
            policy = await _get_policy(session, TicketPriority.normal)
            follow_up.sla_response_due, follow_up.sla_resolution_due = compute_due_dates(
                now,
                response_minutes=policy.response_minutes,
                resolution_minutes=policy.resolution_minutes,
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
            await get_event_bus().publish("ticket.created", {"ticket_id": follow_up.id})
            return CommentCreateResult(follow_up_ticket_id=follow_up.id)

        if outcome == "reopen":
            before_status = ticket.status
            if ticket.status is TicketStatus.pending:
                ticket.sla_resolution_due, ticket.sla_paused_total_seconds = leave_pending(
                    resolution_due=ticket.sla_resolution_due,
                    paused_at=ticket.sla_paused_at,
                    paused_total_seconds=ticket.sla_paused_total_seconds,
                    now=now,
                )
                ticket.sla_paused_at = None
            elif ticket.status is TicketStatus.resolved:
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
        body=body.body,
        is_internal_note=body.is_internal_note,
    )
    session.add(comment)

    if not is_requester and not body.is_internal_note and ticket.first_responded_at is None:
        ticket.first_responded_at = mark_first_response(None, now)

    await session.commit()
    await session.refresh(comment)
    return CommentCreateResult(comment=CommentOut.model_validate(comment))


@router.post("/{ticket_id}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile,
    comment_id: int | None = Form(None),
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
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

    if comment_id is not None:
        comment = await session.get(TicketComment, comment_id)
        if comment is None or comment.ticket_id != ticket.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="comment_id must belong to this ticket"
            )

    directory = Path(settings.ATTACHMENTS_DIR) / str(ticket.id)
    directory.mkdir(parents=True, exist_ok=True)
    # Strip any directory components from the client-supplied filename so it
    # can't write outside `directory`; the uuid prefix also avoids collisions.
    safe_name = Path(file.filename or "upload").name
    stored_name = f"{uuid4().hex}_{safe_name}"
    file_path = directory / stored_name
    file_path.write_bytes(contents)

    attachment = Attachment(
        ticket_id=ticket.id,
        comment_id=comment_id,
        file_path=str(file_path),
        filename=file.filename or stored_name,
        content_type=file.content_type,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return AttachmentOut.model_validate(attachment)
