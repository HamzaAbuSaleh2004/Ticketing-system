"""SLA due-date calculation and pause/resume math. Pure functions with an
injectable `now`: no ORM, no I/O, no `sleep` in tests."""

from datetime import datetime, timedelta


def compute_due_dates(
    created_at: datetime, *, response_minutes: int, resolution_minutes: int
) -> tuple[datetime, datetime]:
    return (
        created_at + timedelta(minutes=response_minutes),
        created_at + timedelta(minutes=resolution_minutes),
    )


def recompute_due_on_priority_change(
    *,
    created_at: datetime,
    response_minutes: int,
    resolution_minutes: int,
    first_responded_at: datetime | None,
    paused_at: datetime | None,
    current_response_due: datetime | None,
    current_resolution_due: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    """Recomputes both due dates from created_at, unless the corresponding
    clock is no longer live: the response due date is frozen once
    first_responded_at is set, and the resolution due date is left alone
    while paused (recomputing it from created_at would erase the pause)."""
    response_due = (
        current_response_due
        if first_responded_at is not None
        else created_at + timedelta(minutes=response_minutes)
    )
    resolution_due = (
        current_resolution_due
        if paused_at is not None
        else created_at + timedelta(minutes=resolution_minutes)
    )
    return response_due, resolution_due


def enter_pending(now: datetime) -> datetime:
    """Returns the value to store in sla_paused_at."""
    return now


def leave_pending(
    *,
    resolution_due: datetime,
    paused_at: datetime,
    paused_total_seconds: int,
    now: datetime,
) -> tuple[datetime, int]:
    """Returns (new resolution_due, new paused_total_seconds). The response
    SLA never pauses, so it isn't touched here."""
    delta = now - paused_at
    return resolution_due + delta, paused_total_seconds + int(delta.total_seconds())


def mark_first_response(first_responded_at: datetime | None, now: datetime) -> datetime:
    return first_responded_at if first_responded_at is not None else now


def is_at_risk(*, due: datetime | None, window_minutes: int, paused: bool, now: datetime) -> bool:
    """Less than 25% of the window remaining, and not paused."""
    if due is None or paused or window_minutes <= 0:
        return False
    remaining_seconds = (due - now).total_seconds()
    window_seconds = window_minutes * 60
    return remaining_seconds < 0.25 * window_seconds
