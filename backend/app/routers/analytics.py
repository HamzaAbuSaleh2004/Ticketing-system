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


class OrganizationCount(BaseModel):
    name: str
    count: int


class AnalyticsSummary(BaseModel):
    from_date: date
    to_date: date
    created: int
    volume: list[DayCount]
    first_response: DurationStats
    resolution: DurationStats
    backlog: list[StatusCount]
    backlog_by_organization: list[OrganizationCount]


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

_RESOLUTION = text("""
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY s) AS median, avg(s) AS mean, count(*) AS n
    FROM (
        SELECT extract(epoch FROM resolved_at - created_at) AS s
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

# Top 10 organisations by current open backlog, plus a fixed "no
# organisation" bucket (counted separately so a busy top 10 can't push it out).
_BACKLOG_BY_ORG = text("""
    SELECT o.name AS name, count(*) AS n
    FROM tickets t
    JOIN organizations o ON o.id = t.organization_id
    WHERE t.status::text = ANY(:statuses)
    GROUP BY o.name
    ORDER BY n DESC, o.name
    LIMIT 10
""")

_BACKLOG_NO_ORG = text("""
    SELECT count(*) AS n
    FROM tickets t
    WHERE t.status::text = ANY(:statuses) AND t.organization_id IS NULL
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
    backlog_statuses = {"statuses": [s.value for s in _BACKLOG_STATUSES]}
    backlog_rows = {r.status: r.n for r in await session.execute(_BACKLOG, backlog_statuses)}
    org_rows = list(await session.execute(_BACKLOG_BY_ORG, backlog_statuses))
    no_org_n = (await session.execute(_BACKLOG_NO_ORG, backlog_statuses)).scalar() or 0

    return AnalyticsSummary(
        from_date=from_date,
        to_date=to_date,
        created=sum(d.count for d in volume),
        volume=volume,
        first_response=first_response,
        resolution=resolution,
        backlog=[StatusCount(status=s, count=backlog_rows.get(s.value, 0)) for s in _BACKLOG_STATUSES],
        backlog_by_organization=[
            *(OrganizationCount(name=r.name, count=r.n) for r in org_rows),
            OrganizationCount(name="No organisation", count=no_org_n),
        ],
    )
