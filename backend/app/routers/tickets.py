from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import ColumnElement, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.ai import get_ai_provider
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
from app.domain.sla import (
    compute_due_dates,
    enter_pending,
    leave_pending,
    mark_first_response,
)
from app.events.bus import get_event_bus
from app.models import Attachment, AuditLog, Category, Ticket, TicketComment, User
from app.models.enums import TicketPriority, TicketStatus, UserRole
from app.schemas.ticket import (
    AttachmentOut,
    AuditLogOut,
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
from app.services.tickets import escalate, get_policy, lock_ticket, set_priority
from app.services.triage import record_ai_field_decisions, triage_ticket

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

_SORTABLE_COLUMNS: dict[str, ColumnElement] = {
    "id": Ticket.id,
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
    "priority": Ticket.priority,
    "status": Ticket.status,
    "sla_resolution_due": Ticket.sla_resolution_due,
    # The next deadline that matters: first reply while unanswered, then
    # resolution. A paused ticket's stored due date is frozen (it only moves
    # on resume), so it sorts by where the deadline would be if resumed now,
    # instead of floating to the top as "overdue" while nobody can act.
    "sla_due": case(
        (
            Ticket.first_responded_at.is_(None),
            func.least(Ticket.sla_response_due, Ticket.sla_resolution_due),
        ),
        (
            Ticket.sla_paused_at.is_not(None),
            Ticket.sla_resolution_due + (func.now() - Ticket.sla_paused_at),
        ),
        else_=Ticket.sla_resolution_due,
    ),
}

_AGENT_ROLES = (UserRole.agent, UserRole.admin)


def _is_agent(user: User) -> bool:
    return user.role in _AGENT_ROLES


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

    cooloff = timedelta(hours=get_settings().RESOLVED_COOLOFF_HOURS)
    public = TicketDetailPublic.model_validate(ticket).model_copy(
        update={
            "comments": comments,
            "attachments": attachments,
            "reopen_until": ticket.resolved_at + cooloff
            if ticket.status is TicketStatus.resolved and ticket.resolved_at
            else None,
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
    requester = await session.get(User, ticket.requester_id)
    assignee = await session.get(User, ticket.assignee_id) if ticket.assignee_id else None
    return TicketDetail(
        **public.model_dump(),
        sla_paused_total_seconds=ticket.sla_paused_total_seconds,
        ai_triage=ticket.ai_triage,
        requester_name=requester.name,
        requester_email=requester.email,
        assignee_name=assignee.name if assignee else None,
        audit_log=[
            AuditLogOut.model_validate(row).model_copy(update={"actor_name": name})
            for row, name in audit_rows
        ],
        allowed_transitions=sorted(allowed_next_statuses(ticket.status), key=lambda s: s.value),
    )


def _comment_out(comment: TicketComment, viewer: User) -> CommentOut:
    out = CommentOut.model_validate(comment)
    # Customers see staff by first name only ("Tara from Support").
    if not _is_agent(viewer) and comment.author.role in _AGENT_ROLES:
        out.author_name = comment.author.name.split()[0]
    return out


def _parse_sort(sort: str) -> tuple[ColumnElement, bool]:
    desc = sort.startswith("-")
    key = sort[1:] if desc else sort
    column = _SORTABLE_COLUMNS.get(key)
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
    # Every new ticket starts at the default priority; AI triage (worker, on
    # the ticket.created event) then applies its category/priority.
    policy = await get_policy(session, TicketPriority.normal)
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


@router.get("", response_model=TicketQueueResponse | TicketListResponse)
async def list_tickets(
    # Repeatable: ?status=open&status=pending.
    status_filter: list[TicketStatus] | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    assignee: str | None = None,
    category: str | None = None,
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
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="assignee must be 'me', 'unassigned', or a user id",
                ) from exc
            conditions.append(Ticket.assignee_id == assignee_id)

    sort_column, sort_desc = _parse_sort(sort)

    requester = aliased(User)
    assignee = aliased(User)
    stmt = (
        select(Ticket, requester.name, assignee.name)
        .join(requester, requester.id == Ticket.requester_id)
        .outerjoin(assignee, assignee.id == Ticket.assignee_id)
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

    if not _is_agent(user):
        return TicketListResponse(
            items=[TicketListItem.model_validate(t) for t, _, _ in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
    return TicketQueueResponse(
        items=[
            TicketQueueItem(
                **TicketListItem.model_validate(t).model_dump(),
                requester_name=requester_name,
                assignee_name=assignee_name,
                sla_paused_at=t.sla_paused_at,
                first_responded_at=t.first_responded_at,
                sla_paused_total_seconds=t.sla_paused_total_seconds,
            )
            for t, requester_name, assignee_name in rows
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

    # AI triage accept/override bookkeeping. Direct category/priority edits
    # count as accepted when they match the suggestion, overridden otherwise.
    suggestion = (ticket.ai_triage or {}).get("suggestion")
    ai_accept = changes.pop("ai_accept", None) or []
    if ai_accept and suggestion is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="This ticket has no AI triage to accept")
    decisions: dict[str, str] = {}
    for field in ai_accept:
        decisions[field] = "accepted"
        if field in ("category", "priority"):
            if field in changes and changes[field] != suggestion[field]:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"{field} conflicts with accepting the AI suggestion",
                )
            changes[field] = suggestion[field] if field == "category" else TicketPriority(suggestion[field])
        elif field == "one_line_summary" and ticket.ai_summary != suggestion["one_line_summary"]:
            before["ai_summary"], after["ai_summary"] = ticket.ai_summary, suggestion["one_line_summary"]
            ticket.ai_summary = suggestion["one_line_summary"]
    if suggestion is not None:
        for field in ("category", "priority"):
            if field in changes and field not in decisions and changes[field] is not None:
                value = changes[field].value if field == "priority" else changes[field]
                decisions[field] = "accepted" if value == suggestion[field] else "overridden"

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
        decisions.pop("priority", None)

    if changes.get("priority") is not None and changes["priority"] != ticket.priority:
        before["priority"] = ticket.priority.value
        await set_priority(session, ticket, changes["priority"])
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

    if "assignee_id" in changes and changes["assignee_id"] != ticket.assignee_id:
        new_assignee_id = changes["assignee_id"]
        if new_assignee_id is not None:
            assignee = await session.get(User, new_assignee_id)
            if assignee is None or assignee.role not in _AGENT_ROLES:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="assignee_id must be an existing agent or admin",
                )
        before["assignee_id"] = ticket.assignee_id
        ticket.assignee_id = new_assignee_id
        after["assignee_id"] = ticket.assignee_id

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

    decision_diff = record_ai_field_decisions(ticket, decisions)
    if decision_diff is not None:
        before["ai_accepted_fields"], after["ai_accepted_fields"] = decision_diff

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


@router.post("/{ticket_id}/ai-triage", response_model=TicketDetail)
async def rerun_ai_triage(
    ticket_id: int,
    user: User = Depends(require_role(*_AGENT_ROLES)),
    session: AsyncSession = Depends(get_db),
) -> TicketDetail:
    await _get_ticket_or_404(session, ticket_id, user)
    ticket = await triage_ticket(session, ticket_id, get_ai_provider(), actor_id=user.id, force=True)
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
            policy = await get_policy(session, TicketPriority.normal)
            follow_up = Ticket(
                subject=ticket.subject,
                description=body.body,
                status=TicketStatus.new,
                priority=TicketPriority.normal,
                requester_id=user.id,
                parent_ticket_id=ticket.id,
                created_at=now,
            )
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
        author=user,
        body=body.body,
        is_internal_note=body.is_internal_note,
    )
    session.add(comment)

    if not is_requester and not body.is_internal_note and ticket.first_responded_at is None:
        ticket.first_responded_at = mark_first_response(None, now)

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
                status.HTTP_422_UNPROCESSABLE_CONTENT, detail="comment_id must belong to this ticket"
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
        filename=safe_name,
        content_type=file.content_type,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return AttachmentOut.model_validate(attachment)
