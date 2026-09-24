from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.db import get_db
from app.domain import clock
from app.models import User
from app.models.enums import TicketStatus, UserRole

router = APIRouter(prefix="/analytics", tags=["analytics"])

_BACKLOG_STATUSES = [
    TicketStatus.new,
    TicketStatus.triaged,
    TicketStatus.open,
    TicketStatus.in_progress,
    TicketStatus.pending,
]
MAX_RANGE_DAYS = 366


class DayCount(BaseModel):
    date: date
    count: int


class DurationStats(BaseModel):
    median_seconds: float | None
    avg_seconds: float | None
    count: int


class StatusCount(BaseModel):
    status: TicketStatus
    count: int


class Breaches(BaseModel):
    total: int
    response: int
    resolution: int


class AnalyticsSummary(BaseModel):
    from_date: date
    to_date: date
    created: int
    volume: list[DayCount]
    first_response: DurationStats
    resolution: DurationStats
    backlog: list[StatusCount]
    sla_breaches: Breaches


# Every figure is a SQL aggregate over tickets created in [start, end).
# Days are a date series turned into UTC instants explicitly, so buckets
# don't shift with the database session's TimeZone or across DST.
_VOLUME = text("""
    SELECT d::date AS day, count(t.id) AS n
    FROM generate_series(CAST(:from_date AS date), CAST(:to_date AS date), interval '1 day') AS d
    LEFT JOIN tickets t
        ON t.created_at >= (d::date::timestamp AT TIME ZONE 'UTC')
        AND t.created_at < ((d::date + 1)::timestamp AT TIME ZONE 'UTC')
    GROUP BY d
    ORDER BY d
""")

_FIRST_RESPONSE = text("""
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY s) AS median, avg(s) AS mean, count(*) AS n
    FROM (
        SELECT extract(epoch FROM first_responded_at - created_at) AS s
        FROM tickets
        WHERE created_at >= :start AND created_at < :end AND first_responded_at IS NOT NULL
    ) x
""")

# Resolution time excludes time spent paused while pending.
_RESOLUTION = text("""
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY s) AS median, avg(s) AS mean, count(*) AS n
    FROM (
        SELECT extract(epoch FROM resolved_at - created_at) - sla_paused_total_seconds AS s
        FROM tickets
        WHERE created_at >= :start AND created_at < :end AND resolved_at IS NOT NULL
    ) x
""")

# Backlog is the current open work, whenever it was created.
_BACKLOG = text("""
    SELECT status::text AS status, count(*) AS n
    FROM tickets
    WHERE status::text = ANY(:statuses)
    GROUP BY status
""")

# A response SLA is breached if the first public reply came late, or never
# came before resolution/now. A resolution SLA is breached if it was resolved
# late, or is still running past due; a paused ticket only counts if it was
# already late when it paused (the clock is frozen while pending).
_BREACHES = text("""
    SELECT
        count(*) FILTER (WHERE response_breached OR resolution_breached) AS total,
        count(*) FILTER (WHERE response_breached) AS response,
        count(*) FILTER (WHERE resolution_breached) AS resolution
    FROM (
        SELECT
            (first_responded_at IS NOT NULL AND first_responded_at > sla_response_due)
            OR (first_responded_at IS NULL AND coalesce(resolved_at, CAST(:now AS timestamptz)) > sla_response_due)
                AS response_breached,
            (resolved_at IS NOT NULL AND resolved_at > sla_resolution_due)
            OR (resolved_at IS NULL AND sla_paused_at IS NULL AND CAST(:now AS timestamptz) > sla_resolution_due)
            OR (resolved_at IS NULL AND sla_paused_at IS NOT NULL AND sla_paused_at > sla_resolution_due)
                AS resolution_breached
        FROM tickets
        WHERE created_at >= :start AND created_at < :end
    ) x
""")


def _stats(row) -> DurationStats:
    return DurationStats(
        median_seconds=float(row.median) if row.median is not None else None,
        avg_seconds=float(row.mean) if row.mean is not None else None,
        count=row.n,
    )


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    user: User = Depends(require_role(UserRole.agent, UserRole.admin)),
    session: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    """Dates are UTC calendar days, both inclusive. Defaults to the last 30 days."""
    now = clock.now()
    to_date = to_date or now.date()
    from_date = from_date or to_date - timedelta(days=29)
    if from_date > to_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="from must be on or before to")
    if (to_date - from_date).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Range is limited to {MAX_RANGE_DAYS} days")

    start = datetime.combine(from_date, time.min, UTC)
    end = datetime.combine(to_date + timedelta(days=1), time.min, UTC)
    window = {"start": start, "end": end}

    volume = [
        DayCount(date=r.day, count=r.n)
        for r in await session.execute(_VOLUME, {"from_date": from_date, "to_date": to_date})
    ]
    first_response = _stats((await session.execute(_FIRST_RESPONSE, window)).one())
    resolution = _stats((await session.execute(_RESOLUTION, window)).one())
    backlog_rows = {
        r.status: r.n
        for r in await session.execute(_BACKLOG, {"statuses": [s.value for s in _BACKLOG_STATUSES]})
    }
    breaches = (await session.execute(_BREACHES, {**window, "now": now})).one()

    return AnalyticsSummary(
        from_date=from_date,
        to_date=to_date,
        created=sum(d.count for d in volume),
        volume=volume,
        first_response=first_response,
        resolution=resolution,
        backlog=[StatusCount(status=s, count=backlog_rows.get(s.value, 0)) for s in _BACKLOG_STATUSES],
        sla_breaches=Breaches(total=breaches.total, response=breaches.response, resolution=breaches.resolution),
    )
