from datetime import UTC, datetime, timedelta

import pytest

from app.domain.lifecycle import (
    IllegalTransitionError,
    allowed_next_statuses,
    can_escalate,
    customer_reply_outcome,
    escalate_priority,
    validate_transition,
)
from app.models.enums import TicketPriority, TicketStatus

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TicketStatus.new, TicketStatus.triaged),
        (TicketStatus.triaged, TicketStatus.open),
        (TicketStatus.open, TicketStatus.in_progress),
        (TicketStatus.in_progress, TicketStatus.pending),
        (TicketStatus.in_progress, TicketStatus.resolved),
        (TicketStatus.pending, TicketStatus.in_progress),
        (TicketStatus.resolved, TicketStatus.in_progress),
        (TicketStatus.resolved, TicketStatus.closed),
    ],
)
def test_legal_transitions_pass(current, target):
    validate_transition(current, target, assignee_id=1)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TicketStatus.new, TicketStatus.open),
        (TicketStatus.new, TicketStatus.in_progress),
        (TicketStatus.triaged, TicketStatus.in_progress),
        (TicketStatus.open, TicketStatus.pending),
        (TicketStatus.open, TicketStatus.resolved),
        (TicketStatus.pending, TicketStatus.resolved),
        (TicketStatus.pending, TicketStatus.closed),
        (TicketStatus.closed, TicketStatus.in_progress),
        (TicketStatus.closed, TicketStatus.open),
        (TicketStatus.resolved, TicketStatus.new),
    ],
)
def test_illegal_transitions_raise_with_allowed_set(current, target):
    with pytest.raises(IllegalTransitionError) as exc_info:
        validate_transition(current, target, assignee_id=1)
    assert exc_info.value.allowed == allowed_next_statuses(current)


def test_closed_has_no_allowed_transitions():
    assert allowed_next_statuses(TicketStatus.closed) == set()


def test_open_requires_assignee():
    with pytest.raises(IllegalTransitionError):
        validate_transition(TicketStatus.triaged, TicketStatus.open, assignee_id=None)
    validate_transition(TicketStatus.triaged, TicketStatus.open, assignee_id=7)


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        (TicketPriority.low, TicketPriority.normal),
        (TicketPriority.normal, TicketPriority.high),
        (TicketPriority.high, TicketPriority.urgent),
        (TicketPriority.urgent, TicketPriority.urgent),
    ],
)
def test_escalate_priority_bumps_one_level_capped_at_urgent(priority, expected):
    assert escalate_priority(priority) == expected


@pytest.mark.parametrize(
    "status",
    [
        TicketStatus.new,
        TicketStatus.triaged,
        TicketStatus.open,
        TicketStatus.in_progress,
        TicketStatus.pending,
    ],
)
def test_can_escalate_from_most_statuses(status):
    assert can_escalate(status) is True


@pytest.mark.parametrize("status", [TicketStatus.resolved, TicketStatus.closed])
def test_cannot_escalate_resolved_or_closed(status):
    assert can_escalate(status) is False


def test_customer_reply_on_pending_reopens():
    assert customer_reply_outcome(
        status=TicketStatus.pending, resolved_at=None, cooloff_hours=72, now=NOW
    ) == "reopen"


def test_customer_reply_on_resolved_within_window_reopens():
    resolved_at = NOW - timedelta(hours=1)
    assert customer_reply_outcome(
        status=TicketStatus.resolved, resolved_at=resolved_at, cooloff_hours=72, now=NOW
    ) == "reopen"


def test_customer_reply_on_resolved_past_window_creates_follow_up():
    resolved_at = NOW - timedelta(hours=73)
    assert customer_reply_outcome(
        status=TicketStatus.resolved, resolved_at=resolved_at, cooloff_hours=72, now=NOW
    ) == "follow_up"


def test_customer_reply_on_closed_creates_follow_up():
    assert customer_reply_outcome(
        status=TicketStatus.closed, resolved_at=None, cooloff_hours=72, now=NOW
    ) == "follow_up"


@pytest.mark.parametrize(
    "status",
    [TicketStatus.new, TicketStatus.triaged, TicketStatus.open, TicketStatus.in_progress],
)
def test_customer_reply_elsewhere_has_no_automatic_effect(status):
    assert customer_reply_outcome(
        status=status, resolved_at=None, cooloff_hours=72, now=NOW
    ) == "none"
