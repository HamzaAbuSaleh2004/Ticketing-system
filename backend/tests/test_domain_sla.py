from datetime import UTC, datetime, timedelta

from app.domain.sla import (
    compute_due_dates,
    enter_pending,
    is_at_risk,
    leave_pending,
    mark_first_response,
    recompute_due_on_priority_change,
)

CREATED = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_compute_due_dates():
    response_due, resolution_due = compute_due_dates(
        CREATED, response_minutes=60, resolution_minutes=480
    )
    assert response_due == CREATED + timedelta(minutes=60)
    assert resolution_due == CREATED + timedelta(minutes=480)


def test_recompute_on_priority_change_when_nothing_pinned():
    response_due, resolution_due = recompute_due_on_priority_change(
        created_at=CREATED,
        response_minutes=15,
        resolution_minutes=240,
        first_responded_at=None,
        paused_at=None,
        current_response_due=CREATED + timedelta(minutes=999),
        current_resolution_due=CREATED + timedelta(minutes=999),
    )
    assert response_due == CREATED + timedelta(minutes=15)
    assert resolution_due == CREATED + timedelta(minutes=240)


def test_recompute_on_priority_change_freezes_response_due_after_first_response():
    stale_response_due = CREATED + timedelta(minutes=999)
    response_due, resolution_due = recompute_due_on_priority_change(
        created_at=CREATED,
        response_minutes=15,
        resolution_minutes=240,
        first_responded_at=CREATED + timedelta(minutes=5),
        paused_at=None,
        current_response_due=stale_response_due,
        current_resolution_due=CREATED + timedelta(minutes=999),
    )
    assert response_due == stale_response_due
    assert resolution_due == CREATED + timedelta(minutes=240)


def test_recompute_on_priority_change_leaves_resolution_due_while_paused():
    stale_resolution_due = CREATED + timedelta(minutes=999)
    response_due, resolution_due = recompute_due_on_priority_change(
        created_at=CREATED,
        response_minutes=15,
        resolution_minutes=240,
        first_responded_at=None,
        paused_at=CREATED + timedelta(minutes=30),
        current_response_due=CREATED + timedelta(minutes=999),
        current_resolution_due=stale_resolution_due,
    )
    assert response_due == CREATED + timedelta(minutes=15)
    assert resolution_due == stale_resolution_due


def test_pause_resume_single_cycle_shifts_resolution_due_by_pause_duration():
    resolution_due = CREATED + timedelta(hours=8)
    paused_at = enter_pending(CREATED + timedelta(hours=1))
    resume_at = paused_at + timedelta(hours=2)

    new_due, paused_total = leave_pending(
        resolution_due=resolution_due,
        paused_at=paused_at,
        paused_total_seconds=0,
        now=resume_at,
    )

    assert new_due == resolution_due + timedelta(hours=2)
    assert paused_total == int(timedelta(hours=2).total_seconds())


def test_pause_resume_multiple_cycles_accumulate():
    resolution_due = CREATED + timedelta(hours=8)

    paused_at_1 = enter_pending(CREATED + timedelta(hours=1))
    resolution_due, paused_total = leave_pending(
        resolution_due=resolution_due,
        paused_at=paused_at_1,
        paused_total_seconds=0,
        now=paused_at_1 + timedelta(minutes=30),
    )

    paused_at_2 = enter_pending(resolution_due - timedelta(hours=5))
    resolution_due, paused_total = leave_pending(
        resolution_due=resolution_due,
        paused_at=paused_at_2,
        paused_total_seconds=paused_total,
        now=paused_at_2 + timedelta(hours=1, minutes=15),
    )

    total_pause = timedelta(minutes=30) + timedelta(hours=1, minutes=15)
    assert paused_total == int(total_pause.total_seconds())
    assert resolution_due == CREATED + timedelta(hours=8) + total_pause


def test_mark_first_response_sets_once():
    first_time = CREATED + timedelta(minutes=10)
    assert mark_first_response(None, first_time) == first_time
    # A second reply doesn't move an already-set first response.
    assert mark_first_response(first_time, first_time + timedelta(hours=1)) == first_time


def test_is_at_risk_true_under_25_percent_remaining():
    due = CREATED + timedelta(minutes=10)  # 10 of 60 minutes left = 16%
    assert is_at_risk(due=due, window_minutes=60, paused=False, now=CREATED) is True


def test_is_at_risk_false_with_plenty_of_time_left():
    due = CREATED + timedelta(minutes=50)  # 50 of 60 minutes left
    assert is_at_risk(due=due, window_minutes=60, paused=False, now=CREATED) is False


def test_is_at_risk_false_when_paused():
    due = CREATED + timedelta(minutes=1)
    assert is_at_risk(due=due, window_minutes=60, paused=True, now=CREATED) is False


def test_is_at_risk_false_when_due_is_none():
    assert is_at_risk(due=None, window_minutes=60, paused=False, now=CREATED) is False


def test_is_at_risk_true_when_already_breached():
    due = CREATED - timedelta(minutes=5)
    assert is_at_risk(due=due, window_minutes=60, paused=False, now=CREATED) is True
