"""Ticket status transitions and escalation. Pure functions: no ORM, no I/O,
so they're unit-testable without a database."""

from datetime import datetime, timedelta

from app.models.enums import TicketPriority, TicketStatus

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.open: {TicketStatus.in_progress},
    TicketStatus.in_progress: {TicketStatus.pending, TicketStatus.resolved},
    TicketStatus.pending: {TicketStatus.in_progress},
    TicketStatus.resolved: {TicketStatus.in_progress, TicketStatus.closed},
    TicketStatus.closed: set(),
}

_PRIORITY_ORDER = [
    TicketPriority.low,
    TicketPriority.normal,
    TicketPriority.high,
    TicketPriority.urgent,
]


class IllegalTransitionError(Exception):
    """A requested status change isn't a legal move from the current status,
    or fails a transition guard (e.g. `in_progress` needs an assignee)."""

    def __init__(self, current: TicketStatus, allowed: set[TicketStatus], reason: str | None = None):
        self.current = current
        self.allowed = allowed
        self.reason = reason
        super().__init__(reason or f"{current.value} -> not in {sorted(s.value for s in allowed)}")


def allowed_next_statuses(current: TicketStatus) -> set[TicketStatus]:
    return ALLOWED_TRANSITIONS[current]


def validate_transition(
    current: TicketStatus, target: TicketStatus, *, assignee_id: int | None
) -> None:
    allowed = ALLOWED_TRANSITIONS[current]
    if target not in allowed:
        raise IllegalTransitionError(current, allowed)
    if current is TicketStatus.open and target is TicketStatus.in_progress and assignee_id is None:
        raise IllegalTransitionError(current, allowed, reason="in_progress requires an assignee")


def can_escalate(status: TicketStatus) -> bool:
    return status not in (TicketStatus.resolved, TicketStatus.closed)


def escalate_priority(priority: TicketPriority) -> TicketPriority:
    """Bumps priority one level, capped at urgent."""
    idx = _PRIORITY_ORDER.index(priority)
    return _PRIORITY_ORDER[min(idx + 1, len(_PRIORITY_ORDER) - 1)]


def customer_reply_outcome(
    *,
    status: TicketStatus,
    resolved_at: datetime | None,
    cooloff_hours: int,
    now: datetime,
) -> str:
    """What a customer's public reply does to a ticket's lifecycle:
    - "reopen": move it back to in_progress (this ticket).
    - "follow_up": leave it untouched and create a new linked ticket instead.
    - "none": no automatic status change.

    A resolved ticket past its cooling-off window behaves like a closed one
    (follow-up instead of reopen) even before the worker's auto-close sweep
    (every SWEEP_INTERVAL_SECONDS) has flipped it to closed.
    """
    if status is TicketStatus.pending:
        return "reopen"
    if status is TicketStatus.resolved:
        if resolved_at is not None and now - resolved_at <= timedelta(hours=cooloff_hours):
            return "reopen"
        return "follow_up"
    if status is TicketStatus.closed:
        return "follow_up"
    return "none"
