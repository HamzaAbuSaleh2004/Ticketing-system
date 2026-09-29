from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    ActionItemSide,
    OrganizationKind,
    TicketPriority,
    TicketStatus,
)


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1)
    # Agent/admin only: create the ticket already claimed for an existing
    # customer (organisation inherited from them), or — when omitted —
    # unclaimed and tagged with this organisation directly. An end_user
    # caller can't set either; the router forces requester=self, own org.
    requester_id: int | None = None
    organization_id: int | None = None


class TicketPatch(BaseModel):
    """Fields left unset (not just null) are left untouched — the router
    reads `model_dump(exclude_unset=True)` to tell "don't change assignee"
    apart from "unassign" (assignee_id=null)."""

    status: TicketStatus | None = None
    assignee_id: int | None = None
    priority: TicketPriority | None = None
    category: str | None = None
    organization_id: int | None = None
    # Agent/admin only: claims an unclaimed ticket for an existing customer.
    # Only settable once (409 if the ticket already has a requester).
    requester_id: int | None = None
    escalate: bool | None = None


def _clean_description(value: str | None) -> str:
    # ActionItemCreate's field is required (plain `str`), so pydantic's own
    # type check rejects None there before this runs. ActionItemPatch's field
    # is `str | None` so the field can be left unset — but if a client
    # explicitly sends `"description": null`, it must be a clean 422, not an
    # AttributeError from calling .strip() on None (which FastAPI would
    # otherwise surface as an unhandled 500).
    if value is None or not value.strip():
        raise ValueError("Can't be blank")
    return value.strip()


class ActionItemCreate(BaseModel):
    side: ActionItemSide
    description: str = Field(min_length=1, max_length=500)

    _description = field_validator("description")(_clean_description)


class ActionItemPatch(BaseModel):
    """Agents/admins may change either field; a requester may only set
    `done` on a `side=customer` item — enforced in the router, not here,
    since it depends on who's asking and which item this is."""

    done: bool | None = None
    description: str | None = Field(None, min_length=1, max_length=500)

    _description = field_validator("description")(_clean_description)


class ActionItemOut(BaseModel):
    id: int
    side: ActionItemSide
    description: str
    done: bool
    created_by: int
    created_at: datetime
    done_at: datetime | None
    done_by: int | None
    done_by_name: str | None = None

    model_config = {"from_attributes": True}


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
    requester_id: int | None
    assignee_id: int | None
    escalated: bool
    sla_response_due: datetime | None
    sla_resolution_due: datetime | None
    created_at: datetime
    updated_at: datetime
    organization_id: int | None
    organization_name: str | None = None
    organization_kind: OrganizationKind | None = None
    open_customer_items: int = 0
    open_liverx_items: int = 0

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketListItem]
    total: int
    page: int
    page_size: int


class TicketQueueItem(TicketListItem):
    """Agent queue row: adds who's involved and the SLA clock inputs (pause
    accounting is agent-only, like on the detail)."""

    # None for an unclaimed ticket (no requester yet).
    requester_name: str | None
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
    action_items: list[ActionItemOut] = []


class TicketDetail(TicketDetailPublic):
    """Agent/admin view. The extra fields have no defaults, so a public
    payload can never validate as this model."""

    sla_paused_total_seconds: int
    # Both None for an unclaimed ticket (no requester yet).
    requester_name: str | None
    requester_email: str | None
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
