from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import TicketPriority, TicketStatus


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)


class TicketPatch(BaseModel):
    """Fields left unset (not just null) are left untouched — the router
    reads `model_dump(exclude_unset=True)` to tell "don't change assignee"
    apart from "unassign" (assignee_id=null)."""

    status: TicketStatus | None = None
    assignee_id: int | None = None
    priority: TicketPriority | None = None
    category: str | None = None
    escalate: bool | None = None


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    is_internal_note: bool = False


class CommentOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int
    author_name: str
    author_role: str
    body: str
    is_internal_note: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentOut(BaseModel):
    id: int
    comment_id: int | None
    filename: str
    content_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: int
    actor_id: int | None
    # None for the system (the SLA sweeps): actor_id is NULL.
    actor_name: str | None = None
    action: str
    diff_json: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TicketListItem(BaseModel):
    id: int
    subject: str
    status: TicketStatus
    priority: TicketPriority
    category: str | None
    requester_id: int
    assignee_id: int | None
    escalated: bool
    sla_response_due: datetime | None
    sla_resolution_due: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class TicketQueueItem(TicketListItem):
    """Agent queue row: adds who's involved and the SLA clock inputs (pause
    accounting is agent-only, like on the detail)."""

    requester_name: str
    assignee_name: str | None
    sla_paused_at: datetime | None
    first_responded_at: datetime | None
    sla_paused_total_seconds: int


class TicketQueueResponse(BaseModel):
    items: list[TicketQueueItem]
    total: int
    page: int
    page_size: int


class TicketDetailPublic(TicketListItem):
    """What an end user gets. Agent-only fields (pause accounting, legal
    transitions, audit trail) are absent from the model, not just nulled."""

    description: str
    sla_paused_at: datetime | None
    first_responded_at: datetime | None
    parent_ticket_id: int | None
    resolved_at: datetime | None
    closed_at: datetime | None
    # While resolved: until when a customer reply reopens it instead of
    # starting a follow-up (resolved_at + RESOLVED_COOLOFF_HOURS).
    reopen_until: datetime | None = None
    comments: list[CommentOut] = []
    attachments: list[AttachmentOut] = []


class TicketDetail(TicketDetailPublic):
    """Agent/admin view. The extra fields have no defaults, so a public
    payload can never validate as this model."""

    sla_paused_total_seconds: int
    requester_name: str
    requester_email: str
    assignee_name: str | None
    audit_log: list[AuditLogOut]
    # Legal next statuses from the current one (domain/lifecycle.py), so the
    # UI's status control only ever offers a move the API will accept.
    allowed_transitions: list[TicketStatus]


class CommentCreateResult(BaseModel):
    comment: CommentOut | None = None
    # Set instead of `comment` when the reply landed on a closed (or
    # past-cooloff resolved) ticket and became a new linked ticket instead.
    follow_up_ticket_id: int | None = None
